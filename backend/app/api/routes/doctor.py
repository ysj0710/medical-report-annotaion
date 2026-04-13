from typing import Optional
from datetime import datetime, timedelta, timezone
from anyio import from_thread
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, load_only
from ...core.database import get_db, SessionLocal
from ...core.collaboration_ws import (
    collaboration_socket_hub,
    CollaborationSocketClient,
    report_updates_socket_hub,
    ReportUpdatesSocketClient
)
from ...models.user import User
from ...models.report import Report
from ...models.annotation import Annotation
from ...models.collaboration import ReportCollaborationSession, ReportEditLock
from ...schemas.doctor import (
    DoctorReportResponse, DoctorReportListResponse, DoctorProgressResponse,
    DraftRequest, SubmitRequest, SaveDraftResponse, SubmitResponse,
    CollaborationHeartbeatRequest, CollaborationStateResponse, CollaborationParticipantResponse,
    CollaborationActivityPayload, CollaborationActivityResponse
)
from ..deps import get_current_user, get_current_user_from_token_value, require_role

router = APIRouter()

STATUS_IMPORTED = "IMPORTED"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_REVIEW_ASSIGNED = "REVIEW_ASSIGNED"
STATUS_REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
STATUS_DONE = "DONE"
COLLAB_VIEW_TTL_SECONDS = 15
COLLAB_LOCK_TTL_SECONDS = 8
COLLAB_ACTIVITY_LABEL_MAX_LENGTH = 120
COLLAB_SELECTION_TEXT_MAX_LENGTH = 96
ANNOTATION_DONE_STATUSES = {STATUS_SUBMITTED, STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS, STATUS_DONE}
REVIEW_ACTIVE_STATUSES = {STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS}


def _normalize_annotation_user_ids(raw_value) -> list[int]:
    if not isinstance(raw_value, list):
        return []

    normalized_ids: list[int] = []
    seen_ids: set[int] = set()
    for item in raw_value:
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in seen_ids:
            continue
        seen_ids.add(user_id)
        normalized_ids.append(user_id)
    return normalized_ids


def _append_annotation_user_id(annotation: Annotation, user_id: Optional[int]) -> None:
    if not user_id:
        return
    user_ids = _normalize_annotation_user_ids(annotation.annotation_user_ids)
    if user_id not in user_ids:
        user_ids.append(user_id)
    annotation.annotation_user_ids = user_ids


def _normalize_review_completed_user_ids(raw_value) -> list[int]:
    return _normalize_annotation_user_ids(raw_value)


def _append_review_completed_user_id(report: Report, user_id: Optional[int]) -> list[int]:
    if not user_id:
        return _normalize_review_completed_user_ids(report.review_completed_user_ids)
    user_ids = _normalize_review_completed_user_ids(report.review_completed_user_ids)
    if user_id not in user_ids:
        user_ids.append(user_id)
    report.review_completed_user_ids = user_ids
    return user_ids


def _read_field(source, name: str):
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _is_review_task(source) -> bool:
    return bool(
        _read_field(source, "status") in REVIEW_ACTIVE_STATUSES
        or _read_field(source, "reviewer_doctor_id")
        or _read_field(source, "review_assigned_at")
        or _normalize_review_completed_user_ids(_read_field(source, "review_completed_user_ids"))
    )


def _is_annotation_done(source) -> bool:
    return bool(
        _read_field(source, "status") in ANNOTATION_DONE_STATUSES
        or _read_field(source, "annotation_status") == "SUBMITTED"
    )


def _is_review_done(source) -> bool:
    return bool(
        _is_review_task(source)
        and (
            _read_field(source, "status") == STATUS_DONE
            or _read_field(source, "reviewed_at")
            or _normalize_review_completed_user_ids(_read_field(source, "review_completed_user_ids"))
        )
    )


def _annotation_owner_condition(current_user_id: int):
    return or_(
        Report.annotator_doctor_id == current_user_id,
        and_(
            Report.reviewer_doctor_id.is_(None),
            Report.assigned_doctor_id == current_user_id
        )
    )


def _review_owner_condition(current_user_id: int):
    return Report.reviewer_doctor_id == current_user_id


def _build_review_user_payload(user: Optional[User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "employee_id": user.employee_id
    }


def _build_review_completed_users(report: Report, user_by_id: dict[int, User]) -> list[dict]:
    results: list[dict] = []
    for user_id in _normalize_review_completed_user_ids(report.review_completed_user_ids):
        payload = _build_review_user_payload(user_by_id.get(user_id))
        if payload:
            results.append(payload)
    return results


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_accessible_report(db: Session, report_id: int, current_user: User) -> Optional[Report]:
    if current_user.role == "admin" or current_user.can_view_all:
        return db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    ownership_condition = or_(
        Report.assigned_doctor_id == current_user.id,
        Report.annotator_doctor_id == current_user.id,
        Report.reviewer_doctor_id == current_user.id
    )
    return db.query(Report).filter(
        Report.id == report_id,
        ownership_condition,
        Report.is_cancel == False
    ).first()


def _can_user_edit_report(report: Optional[Report], current_user: User) -> bool:
    if not report:
        return False
    if current_user.role == "admin":
        return True
    return report.assigned_doctor_id == current_user.id


def _build_view_only_message() -> str:
    return "该报告未分配给你，你当前仅支持查看，不能编辑或参与协同标注"


def _trim_collaboration_text(value: Optional[str], max_length: int) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:max_length]


def _apply_session_activity(
    session: ReportCollaborationSession,
    activity: Optional[CollaborationActivityPayload]
) -> None:
    if not activity or not str(activity.status or "").strip():
        session.active_status = None
        session.active_label = None
        session.active_content_type = None
        session.active_selection_start = None
        session.active_selection_end = None
        session.active_selection_text = None
        return

    session.active_status = str(activity.status or "").strip().lower() or None
    session.active_label = _trim_collaboration_text(activity.label, COLLAB_ACTIVITY_LABEL_MAX_LENGTH)
    session.active_content_type = str(activity.content_type or "").strip().lower() or None
    session.active_selection_start = activity.selection_start
    session.active_selection_end = activity.selection_end
    session.active_selection_text = _trim_collaboration_text(
        activity.selection_text,
        COLLAB_SELECTION_TEXT_MAX_LENGTH
    )


def _touch_collaboration_session(
    db: Session,
    report_id: int,
    current_user: User,
    now: datetime,
    *,
    with_activity: bool = False,
    activity: Optional[CollaborationActivityPayload] = None
) -> ReportCollaborationSession:
    session = db.query(ReportCollaborationSession).filter(
        ReportCollaborationSession.report_id == report_id,
        ReportCollaborationSession.user_id == current_user.id
    ).first()
    if not session:
        session = ReportCollaborationSession(report_id=report_id, user_id=current_user.id)
        db.add(session)
    session.last_seen_at = now
    if with_activity:
        session.last_activity_at = now
    _apply_session_activity(session, activity)
    return session


def _remove_collaboration_session(
    db: Session,
    report_id: int,
    current_user: User
) -> None:
    session = db.query(ReportCollaborationSession).filter(
        ReportCollaborationSession.report_id == report_id,
        ReportCollaborationSession.user_id == current_user.id
    ).first()
    if session:
        db.delete(session)


def _claim_edit_lock(db: Session, report_id: int, current_user: User, now: datetime) -> bool:
    lock = db.query(ReportEditLock).filter(
        ReportEditLock.report_id == report_id
    ).with_for_update().first()

    if not lock:
        lock = ReportEditLock(report_id=report_id)
        db.add(lock)
        db.flush()

    expires_at = _ensure_utc(lock.expires_at)
    active_other_editor = (
        lock.editor_user_id
        and lock.editor_user_id != current_user.id
        and expires_at
        and expires_at >= now
    )
    if active_other_editor:
        return False

    if lock.editor_user_id != current_user.id:
        lock.acquired_at = now
    lock.editor_user_id = current_user.id
    lock.last_activity_at = now
    lock.expires_at = now + timedelta(seconds=COLLAB_LOCK_TTL_SECONDS)
    return True


def _release_edit_lock(db: Session, report_id: int, current_user: User) -> None:
    lock = db.query(ReportEditLock).filter(
        ReportEditLock.report_id == report_id
    ).with_for_update().first()
    if not lock or lock.editor_user_id != current_user.id:
        return
    lock.editor_user_id = None
    lock.acquired_at = None
    lock.last_activity_at = None
    lock.expires_at = None


def _build_collaboration_state(
    db: Session,
    report_id: int,
    current_user: User,
    *,
    granted: Optional[bool] = None,
    report: Optional[Report] = None
) -> CollaborationStateResponse:
    now = _utcnow()
    active_cutoff = now - timedelta(seconds=COLLAB_VIEW_TTL_SECONDS)
    report = report or db.query(Report).options(
        load_only(Report.id, Report.assigned_doctor_id)
    ).filter(
        Report.id == report_id,
        Report.is_cancel == False
    ).first()
    user_can_edit = _can_user_edit_report(report, current_user)
    allowed_collaborator_filter = User.role == "admin"
    if report and report.assigned_doctor_id:
        allowed_collaborator_filter = or_(
            User.role == "admin",
            User.id == report.assigned_doctor_id
        )

    sessions = db.query(
        ReportCollaborationSession.user_id.label("user_id"),
        ReportCollaborationSession.last_seen_at.label("last_seen_at"),
        ReportCollaborationSession.last_activity_at.label("last_activity_at"),
        ReportCollaborationSession.active_status.label("active_status"),
        ReportCollaborationSession.active_label.label("active_label"),
        ReportCollaborationSession.active_content_type.label("active_content_type"),
        ReportCollaborationSession.active_selection_start.label("active_selection_start"),
        ReportCollaborationSession.active_selection_end.label("active_selection_end"),
        ReportCollaborationSession.active_selection_text.label("active_selection_text"),
        User.username.label("username"),
        User.role.label("role")
    ).join(
        User, User.id == ReportCollaborationSession.user_id
    ).filter(
        ReportCollaborationSession.report_id == report_id,
        ReportCollaborationSession.last_seen_at >= active_cutoff,
        User.is_cancel == False,
        User.enabled == True,
        allowed_collaborator_filter
    ).all()

    lock_row = db.query(
        ReportEditLock.editor_user_id.label("editor_user_id"),
        ReportEditLock.expires_at.label("expires_at")
    ).filter(
        ReportEditLock.report_id == report_id
    ).first()
    active_lock_user_id = None
    lock_expires_at = _ensure_utc(lock_row.expires_at) if lock_row else None
    if lock_row and lock_row.editor_user_id and lock_expires_at and lock_expires_at >= now:
        active_lock_user_id = lock_row.editor_user_id

    participant_items = []
    current_editor_user = None
    current_activity_owner = None
    current_activity = None
    for session in sessions:
        is_editor = bool(active_lock_user_id and active_lock_user_id == session.user_id)
        if is_editor:
            current_editor_user = session
        participant_items.append(CollaborationParticipantResponse(
            user_id=session.user_id,
            username=session.username,
            role=session.role,
            is_me=session.user_id == current_user.id,
            is_editor=is_editor,
            last_seen_at=session.last_seen_at,
            last_activity_at=session.last_activity_at
        ))

    participant_items.sort(key=lambda item: (
        0 if item.is_editor else 1,
        0 if item.is_me else 1,
        item.username
    ))

    def _activity_sort_key(session) -> tuple[datetime, datetime, int]:
        return (
            _ensure_utc(session.last_activity_at) or datetime.min.replace(tzinfo=timezone.utc),
            _ensure_utc(session.last_seen_at) or datetime.min.replace(tzinfo=timezone.utc),
            session.user_id
        )

    if current_editor_user:
        current_activity_owner = current_editor_user
    else:
        activity_candidates = [session for session in sessions if session.active_status]
        remote_activity_candidates = [
            session for session in activity_candidates
            if session.user_id != current_user.id
        ]
        prioritized_candidates = remote_activity_candidates or activity_candidates
        prioritized_candidates.sort(key=_activity_sort_key, reverse=True)
        current_activity_owner = prioritized_candidates[0] if prioritized_candidates else None

    if current_activity_owner and current_activity_owner.active_status:
        current_activity = CollaborationActivityResponse(
            status=current_activity_owner.active_status,
            label=current_activity_owner.active_label,
            content_type=current_activity_owner.active_content_type,
            selection_start=current_activity_owner.active_selection_start,
            selection_end=current_activity_owner.active_selection_end,
            selection_text=current_activity_owner.active_selection_text
        )

    annotation_updated_at = db.query(Annotation.updated_at).filter(
        Annotation.report_id == report_id
    ).scalar()
    current_editor_user_id = active_lock_user_id

    return CollaborationStateResponse(
        report_id=report_id,
        participants=participant_items,
        current_editor_user_id=current_editor_user_id,
        current_editor_username=current_editor_user.username if current_editor_user else None,
        current_editor_role=current_editor_user.role if current_editor_user else None,
        current_activity_user_id=current_activity_owner.user_id if current_activity_owner else None,
        current_activity_username=current_activity_owner.username if current_activity_owner else None,
        current_activity_role=current_activity_owner.role if current_activity_owner else None,
        current_activity_is_editor=bool(
            current_activity_owner
            and active_lock_user_id
            and current_activity_owner.user_id == active_lock_user_id
        ),
        current_activity=current_activity,
        is_edit_locked=bool(user_can_edit and active_lock_user_id and active_lock_user_id != current_user.id),
        can_edit=bool(user_can_edit and (not active_lock_user_id or active_lock_user_id == current_user.id)),
        granted=granted,
        expires_at=lock_expires_at if active_lock_user_id else None,
        annotation_updated_at=annotation_updated_at
    )


def _build_ws_state_payload_for_client(
    db: Session,
    report_id: int,
    client: CollaborationSocketClient
) -> Optional[dict]:
    current_user = db.query(User).filter(
        User.id == client.user_id,
        User.is_cancel == False,
        User.enabled == True
    ).first()
    if not current_user:
        return None

    report = _get_accessible_report(db, report_id, current_user)
    if not report:
        return None

    state = _build_collaboration_state(
        db,
        report_id,
        current_user,
        granted=None,
        report=report
    )
    return state.model_dump(mode="json")


async def _close_websocket_client(
    client: CollaborationSocketClient,
    *,
    code: int = status.WS_1008_POLICY_VIOLATION,
    reason: str = ""
) -> None:
    try:
        await client.websocket.close(code=code, reason=reason)
    except Exception:
        pass


async def _send_collaboration_state_to_socket_client(
    client: CollaborationSocketClient,
    *,
    request_id: Optional[str] = None
) -> bool:
    db = SessionLocal()
    try:
        payload_state = _build_ws_state_payload_for_client(db, client.report_id, client)
    except Exception as exc:
        db.rollback()
        print(f"Collaboration websocket state send failed for report {client.report_id}: {exc}")
        payload_state = None
    finally:
        db.close()

    if payload_state is None:
        await _close_websocket_client(
            client,
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Report access revoked"
        )
        await collaboration_socket_hub.disconnect(client)
        return False

    payload = {
        "type": "state",
        "state": payload_state
    }
    if request_id:
        payload["request_id"] = request_id

    try:
        await client.websocket.send_json(payload)
        return True
    except Exception:
        await collaboration_socket_hub.disconnect(client)
        return False


async def _broadcast_collaboration_state(report_id: int) -> None:
    clients = await collaboration_socket_hub.get_clients(report_id)
    if not clients:
        return
    for client in clients:
        await _send_collaboration_state_to_socket_client(client)


def _schedule_collaboration_state_broadcast(report_id: int) -> None:
    try:
        from_thread.run(_broadcast_collaboration_state, report_id)
    except Exception as exc:
        print(f"Collaboration websocket broadcast skipped for report {report_id}: {exc}")


async def _broadcast_report_updates_event(event_payload: dict) -> None:
    clients = await report_updates_socket_hub.get_clients()
    if not clients:
        return

    for client in clients:
        try:
            await client.websocket.send_json(event_payload)
        except Exception:
            await report_updates_socket_hub.disconnect(client)


def _schedule_report_updates_broadcast(
    event: str,
    report_id: Optional[int] = None,
    *,
    status: Optional[str] = None,
    annotation_status: Optional[str] = None,
    review_completed_user_ids: Optional[list[int]] = None
) -> None:
    payload = {
        "type": "reports-updated",
        "event": event,
        "report_id": report_id,
        "status": status,
        "annotation_status": annotation_status,
        "review_completed_user_ids": review_completed_user_ids,
        "at": _utcnow().isoformat()
    }
    try:
        from_thread.run(_broadcast_report_updates_event, payload)
    except Exception as exc:
        print(f"Report updates websocket broadcast skipped for report {report_id}: {exc}")


def _build_lock_conflict_message(db: Session, report_id: int, current_user: User) -> str:
    try:
        state = _build_collaboration_state(db, report_id, current_user, granted=False)
        if state.current_editor_username:
            return f"{state.current_editor_username} 正在标注该报告，请稍后再试"
    except Exception as exc:
        db.rollback()
        print(f"Collaboration conflict message fallback activated for report {report_id}: {exc}")
    return "当前报告已被其他用户锁定，请稍后再试"


def _build_collaboration_fallback_state(
    db: Session,
    report_id: int,
    current_user: User,
    *,
    granted: Optional[bool] = None,
    report: Optional[Report] = None
) -> CollaborationStateResponse:
    annotation_updated_at = None
    user_can_edit = _can_user_edit_report(report, current_user)
    try:
        annotation_updated_at = db.query(Annotation.updated_at).filter(
            Annotation.report_id == report_id
        ).scalar()
    except SQLAlchemyError:
        db.rollback()

    participants = []
    current_editor_user_id = None
    current_editor_username = None
    current_editor_role = None
    if granted and user_can_edit:
        now = _utcnow()
        participants = [CollaborationParticipantResponse(
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            is_me=True,
            is_editor=True,
            last_seen_at=now,
            last_activity_at=now
        )]
        current_editor_user_id = current_user.id
        current_editor_username = current_user.username
        current_editor_role = current_user.role

    return CollaborationStateResponse(
        report_id=report_id,
        participants=participants,
        current_editor_user_id=current_editor_user_id,
        current_editor_username=current_editor_username,
        current_editor_role=current_editor_role,
        current_activity_user_id=current_user.id if granted and user_can_edit else None,
        current_activity_username=current_user.username if granted and user_can_edit else None,
        current_activity_role=current_user.role if granted and user_can_edit else None,
        current_activity_is_editor=bool(granted and user_can_edit),
        current_activity=CollaborationActivityResponse(
            status="editing",
            label="正在协同标注",
            content_type=None,
            selection_start=None,
            selection_end=None,
            selection_text=None
        ) if granted and user_can_edit else None,
        is_edit_locked=False,
        can_edit=user_can_edit,
        granted=granted,
        expires_at=None,
        annotation_updated_at=annotation_updated_at
    )


def _run_collaboration_intent(
    db: Session,
    report_id: int,
    current_user: User,
    now: datetime,
    *,
    intent: str,
    activity: Optional[CollaborationActivityPayload] = None
) -> tuple[bool, Optional[bool]]:
    try:
        granted = None
        if intent == "release":
            _release_edit_lock(db, report_id, current_user)
            _remove_collaboration_session(db, report_id, current_user)
        else:
            session_activity = activity if intent in {"view", "edit"} else None
            _touch_collaboration_session(
                db,
                report_id,
                current_user,
                now,
                with_activity=bool(session_activity) or intent == "edit",
                activity=session_activity
            )

        if intent == "edit":
            granted = _claim_edit_lock(db, report_id, current_user, now)

        db.flush()
        return True, granted
    except Exception as exc:
        db.rollback()
        print(f"Collaboration fallback activated for report {report_id}: {exc}")
        return False, (True if intent == "edit" else None)


def _best_effort_release_edit_lock(db: Session, report_id: int, current_user: User) -> None:
    try:
        _release_edit_lock(db, report_id, current_user)
        db.flush()
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"Collaboration lock release skipped for report {report_id}: {exc}")


@router.get("/reports", response_model=DoctorReportListResponse)
def list_doctor_reports(
    tab: str = Query("all"),  # all / unannotated / annotated / no_error
    only_mine: bool = Query(True),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    lite: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor", "admin"]))
):
    """医生端报告列表"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.role == "admin":
        query = db.query(Report).filter(Report.is_cancel == False)
    elif current_user.can_view_all and not only_mine:
        # 可以查看所有报告
        query = db.query(Report).filter(Report.is_cancel == False)
    else:
        ownership_condition = or_(
            Report.assigned_doctor_id == current_user.id,
            Report.annotator_doctor_id == current_user.id,
            Report.reviewer_doctor_id == current_user.id
        )
        # 只能查看分配给自己的报告
        query = db.query(Report).filter(
            ownership_condition,
            Report.is_cancel == False
        )

    if q:
        query = query.filter(
            (Report.ris_no.ilike(f"%{q}%")) |
            (Report.external_id.ilike(f"%{q}%")) |
            (Report.report_text.ilike(f"%{q}%"))
        )

    base_query = query
    review_task_condition = or_(
        Report.status.in_(list(REVIEW_ACTIVE_STATUSES)),
        Report.reviewer_doctor_id.is_not(None),
        Report.review_assigned_at.is_not(None),
        Report.review_completed_at.is_not(None),
        Report.reviewed_at.is_not(None)
    )
    review_done_condition = and_(
        review_task_condition,
        or_(
            Report.status == STATUS_DONE,
            Report.review_completed_at.is_not(None),
            Report.reviewed_at.is_not(None)
        )
    )
    annotation_done_condition = or_(
        Report.status.in_([STATUS_SUBMITTED, STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS, STATUS_DONE]),
        Annotation.status == "SUBMITTED"
    )

    annotation_total_condition = or_(
        Report.assigned_doctor_id.is_not(None),
        Report.annotator_doctor_id.is_not(None),
        Annotation.id.is_not(None)
    )

    annotation_total, annotation_done_total, review_total, review_done_total = base_query.outerjoin(
        Annotation, Annotation.report_id == Report.id
    ).with_entities(
        func.coalesce(func.sum(case((annotation_total_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((annotation_done_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((review_task_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((review_done_condition, 1), else_=0)), 0)
    ).order_by(None).one()

    annotation_progress = DoctorProgressResponse(
        done=annotation_done_total or 0,
        total=annotation_total or 0
    )
    review_progress = DoctorProgressResponse(
        done=review_done_total or 0,
        total=review_total or 0
    )

    annotation_owner_condition = _annotation_owner_condition(current_user.id)
    review_owner_condition = _review_owner_condition(current_user.id)

    # 按 tab 筛选状态
    if tab == "unannotated":
        query = query.filter(
            annotation_owner_condition,
            Report.status.in_([STATUS_IMPORTED, STATUS_ASSIGNED, STATUS_IN_PROGRESS]),
            Report.reviewer_doctor_id.is_(None)
        )
    elif tab == "annotated":
        query = query.filter(
            annotation_owner_condition,
            or_(
                Report.status.in_([STATUS_SUBMITTED, STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS, STATUS_DONE]),
                Annotation.status == "SUBMITTED"
            )
        )
    elif tab == "review":
        query = query.filter(
            review_owner_condition,
            Report.status.in_(list(REVIEW_ACTIVE_STATUSES))
        )
    elif tab == "no_error":
        query = query.join(Annotation, Annotation.report_id == Report.id).filter(
            Report.status.in_([STATUS_SUBMITTED, STATUS_DONE]),
            Annotation.data.contains({"no_error": True})
        ).distinct(Report.id)

    if tab == "all":
        query = query.order_by(
            case((Report.status.in_([STATUS_SUBMITTED, STATUS_DONE]), 1), else_=0),
            Report.id.asc()
        )
    else:
        query = query.order_by(Report.id.asc())

    total = query.order_by(None).count()
    user_by_id: dict[int, User] = {}
    if lite:
        paged_rows = query.outerjoin(
            Annotation, Annotation.report_id == Report.id
        ).with_entities(
            Report.id.label("id"),
            Report.external_id.label("external_id"),
            Report.ris_no.label("ris_no"),
            Report.imported_at.label("imported_at"),
            Report.modality.label("modality"),
            Report.patient_name.label("patient_name"),
            Report.patient_sex.label("patient_sex"),
            Report.patient_age.label("patient_age"),
            Report.exam_item.label("exam_item"),
            Report.exam_mode.label("exam_mode"),
            Report.exam_group.label("exam_group"),
            Report.status.label("status"),
            Report.assigned_doctor_id.label("assigned_doctor_id"),
            Report.assigned_at.label("assigned_at"),
            Report.annotator_doctor_id.label("annotator_doctor_id"),
            Report.reviewer_doctor_id.label("reviewer_doctor_id"),
            Report.review_assigned_at.label("review_assigned_at"),
            Report.reviewed_at.label("reviewed_at"),
            Report.review_completed_at.label("review_completed_at"),
            Report.review_completed_user_ids.label("review_completed_user_ids"),
            Report.submitted_at.label("submitted_at"),
            Annotation.status.label("annotation_status"),
            Annotation.submitted_at.label("annotation_submitted_at")
        ).offset((page - 1) * page_size).limit(page_size).all()
    else:
        query = query.options(load_only(
            Report.id,
            Report.external_id,
            Report.ris_no,
            Report.report_text,
            Report.imported_at,
            Report.modality,
            Report.patient_name,
            Report.patient_sex,
            Report.patient_age,
            Report.exam_item,
            Report.exam_mode,
            Report.exam_group,
            Report.description,
            Report.impression,
            Report.status,
            Report.assigned_doctor_id,
            Report.assigned_at,
            Report.annotator_doctor_id,
            Report.reviewer_doctor_id,
            Report.review_assigned_at,
            Report.reviewed_at,
            Report.review_completed_user_ids,
            Report.review_completed_at,
            Report.submitted_at,
            Report.pre_annotations,
        ))
        paged_rows = query.offset((page - 1) * page_size).limit(page_size).all()

    if paged_rows:
        related_user_ids = {
            user_id for user_id in [
                *(row.reviewer_doctor_id for row in paged_rows),
                *(
                    completed_user_id
                    for row in paged_rows
                    for completed_user_id in _normalize_review_completed_user_ids(row.review_completed_user_ids)
                )
            ] if user_id
        }
        if related_user_ids:
            user_rows = db.query(User).filter(
                User.id.in_(related_user_ids),
                User.is_cancel == False,
                User.enabled == True
            ).all()
            user_by_id = {user.id: user for user in user_rows}

    paged_items = []
    annotation_by_report_id = {}
    if not lite and paged_rows:
        report_ids = [report.id for report in paged_rows]
        annotation_rows = db.query(Annotation).filter(Annotation.report_id.in_(report_ids)).all()
        annotation_by_report_id = {annotation.report_id: annotation for annotation in annotation_rows}

    for report in paged_rows:
        annotation = None if lite else annotation_by_report_id.get(report.id)
        annotation_status = report.annotation_status if lite else annotation.status if annotation else None
        annotation_submitted_at = report.annotation_submitted_at if lite else annotation.submitted_at if annotation else None
        review_completed_user_ids = _normalize_review_completed_user_ids(report.review_completed_user_ids)
        paged_items.append(DoctorReportResponse(
            id=report.id,
            external_id=report.external_id,
            ris_no=report.ris_no,
            report_text=(report.report_text or "") if not lite else "",
            imported_at=report.imported_at,
            modality=report.modality,
            patient_name=report.patient_name,
            patient_sex=report.patient_sex,
            patient_age=report.patient_age,
            exam_item=report.exam_item,
            exam_mode=report.exam_mode,
            exam_group=report.exam_group,
            description=None if lite else report.description,
            impression=None if lite else report.impression,
            status=report.status,
            assigned_doctor_id=report.assigned_doctor_id,
            assigned_at=report.assigned_at,
            annotator_doctor_id=report.annotator_doctor_id,
            reviewer_doctor_id=report.reviewer_doctor_id,
            review_assigned_at=report.review_assigned_at,
            reviewed_at=report.reviewed_at,
            review_completed_at=report.review_completed_at,
            review_completed_user_ids=review_completed_user_ids,
            review_completed_users=_build_review_completed_users(report, user_by_id),
            submitted_at=report.submitted_at,
            annotation_status=annotation_status,
            annotation_submitted_at=annotation_submitted_at,
            is_review_task=_is_review_task(report),
            is_current_user_assigned_reviewer=bool(report.reviewer_doctor_id and report.reviewer_doctor_id == current_user.id),
            has_current_user_completed_review=current_user.id in review_completed_user_ids,
            pre_annotations=None if lite else report.pre_annotations,
            annotation=None if lite else annotation
        ))

    return DoctorReportListResponse(
        items=paged_items,
        page=page,
        page_size=page_size,
        total=total,
        progress=annotation_progress,
        annotation_progress=annotation_progress,
        review_progress=review_progress
    )


@router.get("/reports/{report_id}", response_model=DoctorReportResponse)
def get_doctor_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor", "admin"]))
):
    """医生获取报告详情"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.role == "admin" or current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        ownership_condition = or_(
            Report.assigned_doctor_id == current_user.id,
            Report.annotator_doctor_id == current_user.id,
            Report.reviewer_doctor_id == current_user.id
        )
        report = db.query(Report).filter(
            Report.id == report_id,
            ownership_condition,
            Report.is_cancel == False
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()
    related_user_ids = {
        user_id for user_id in [
            report.reviewer_doctor_id,
            *(_normalize_review_completed_user_ids(report.review_completed_user_ids))
        ] if user_id
    }
    user_by_id = {}
    if related_user_ids:
        user_rows = db.query(User).filter(
            User.id.in_(related_user_ids),
            User.is_cancel == False,
            User.enabled == True
        ).all()
        user_by_id = {user.id: user for user in user_rows}

    # 复核员打开待复核报告即进入“复核中”
    if report.status == STATUS_REVIEW_ASSIGNED and report.assigned_doctor_id == current_user.id:
        report.status = STATUS_REVIEW_IN_PROGRESS
        db.commit()
        db.refresh(report)
        _schedule_report_updates_broadcast(
            "review-started",
            report_id,
            status=report.status,
            annotation_status=annotation.status if annotation else None,
            review_completed_user_ids=_normalize_review_completed_user_ids(report.review_completed_user_ids)
        )

    review_completed_user_ids = _normalize_review_completed_user_ids(report.review_completed_user_ids)
    return DoctorReportResponse(
        id=report.id,
        external_id=report.external_id,
        ris_no=report.ris_no,
        report_text=report.report_text,
        imported_at=report.imported_at,
        modality=report.modality,
        patient_name=report.patient_name,
        patient_sex=report.patient_sex,
        patient_age=report.patient_age,
        exam_item=report.exam_item,
        exam_mode=report.exam_mode,
        exam_group=report.exam_group,
        description=report.description,
        impression=report.impression,
        status=report.status,
        assigned_doctor_id=report.assigned_doctor_id,
        assigned_at=report.assigned_at,
        annotator_doctor_id=report.annotator_doctor_id,
        reviewer_doctor_id=report.reviewer_doctor_id,
        review_assigned_at=report.review_assigned_at,
        reviewed_at=report.reviewed_at,
        review_completed_at=report.review_completed_at,
        review_completed_user_ids=review_completed_user_ids,
        review_completed_users=_build_review_completed_users(report, user_by_id),
        submitted_at=report.submitted_at,
        annotation_status=annotation.status if annotation else None,
        annotation_submitted_at=annotation.submitted_at if annotation else None,
        is_review_task=_is_review_task(report),
        is_current_user_assigned_reviewer=bool(report.reviewer_doctor_id and report.reviewer_doctor_id == current_user.id),
        has_current_user_completed_review=current_user.id in review_completed_user_ids,
        pre_annotations=report.pre_annotations,
        annotation=annotation
    )


@router.post("/reports/{report_id}/collaboration/heartbeat", response_model=CollaborationStateResponse)
def collaboration_heartbeat(
    report_id: int,
    request: CollaborationHeartbeatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor", "admin"]))
):
    report = _get_accessible_report(db, report_id, current_user)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    intent = str(request.intent or "view").strip().lower()
    if intent not in {"view", "edit", "release"}:
        raise HTTPException(status_code=400, detail="intent 仅支持 view / edit / release")

    if not _can_user_edit_report(report, current_user):
        if intent == "edit":
            state = _build_collaboration_state(
                db,
                report_id,
                current_user,
                granted=False,
                report=report
            )
            _schedule_collaboration_state_broadcast(report_id)
            return state
        state = _build_collaboration_state(
            db,
            report_id,
            current_user,
            granted=None,
            report=report
        )
        _schedule_collaboration_state_broadcast(report_id)
        return state

    now = _utcnow()
    supported, granted = _run_collaboration_intent(
        db,
        report_id,
        current_user,
        now,
        intent=intent,
        activity=request.activity
    )

    if not supported:
        state = _build_collaboration_fallback_state(db, report_id, current_user, granted=granted, report=report)
        _schedule_collaboration_state_broadcast(report_id)
        return state

    try:
        db.commit()
        state = _build_collaboration_state(db, report_id, current_user, granted=granted, report=report)
        _schedule_collaboration_state_broadcast(report_id)
        return state
    except Exception as exc:
        db.rollback()
        print(f"Collaboration state fallback activated for report {report_id}: {exc}")
        state = _build_collaboration_fallback_state(db, report_id, current_user, granted=granted, report=report)
        _schedule_collaboration_state_broadcast(report_id)
        return state


@router.websocket("/reports/updates/ws")
async def report_updates_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.headers.get("authorization")
    db = SessionLocal()
    current_user = None

    try:
        current_user = get_current_user_from_token_value(token, db)
        if current_user.role not in {"doctor", "admin"}:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient permissions")
            return
    except HTTPException as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc.detail))
        return
    finally:
        db.close()

    client = ReportUpdatesSocketClient(
        websocket=websocket,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )
    await report_updates_socket_hub.connect(client)

    try:
        await websocket.send_json({
            "type": "reports-updated-connected",
            "at": _utcnow().isoformat()
        })
        while True:
            try:
                payload_text = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                continue

            if str(payload_text or "").strip().lower() == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "at": _utcnow().isoformat()
                })
    except WebSocketDisconnect:
        pass
    finally:
        await report_updates_socket_hub.disconnect(client)


@router.websocket("/reports/{report_id}/collaboration/ws")
async def collaboration_websocket(report_id: int, websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.headers.get("authorization")
    db = SessionLocal()
    client = None
    current_user = None

    try:
        current_user = get_current_user_from_token_value(token, db)
        if current_user.role not in {"doctor", "admin"}:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient permissions")
            return

        report = _get_accessible_report(db, report_id, current_user)
        if not report:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Report not found")
            return
    except HTTPException as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc.detail))
        return
    finally:
        db.close()

    client = CollaborationSocketClient(
        websocket=websocket,
        report_id=report_id,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )
    await collaboration_socket_hub.connect(client)

    db = SessionLocal()
    try:
        report = _get_accessible_report(db, report_id, current_user)
        if report and _can_user_edit_report(report, current_user):
            supported, _granted = _run_collaboration_intent(
                db,
                report_id,
                current_user,
                _utcnow(),
                intent="view"
            )
            if supported:
                db.commit()
    except Exception as exc:
        db.rollback()
        print(f"Collaboration websocket initial sync failed for report {report_id}: {exc}")
    finally:
        db.close()

    await _send_collaboration_state_to_socket_client(client)
    await _broadcast_collaboration_state(report_id)

    try:
        while True:
            payload = await websocket.receive_json()
            request_id = str(payload.get("request_id") or "").strip() or None
            try:
                request = CollaborationHeartbeatRequest.model_validate({
                    "intent": payload.get("intent", "view"),
                    "activity": payload.get("activity")
                })
            except Exception:
                await websocket.send_json({
                    "type": "error",
                    "request_id": request_id,
                    "message": "无效的协同消息"
                })
                continue

            db = SessionLocal()
            try:
                report = _get_accessible_report(db, report_id, current_user)
                if not report:
                    await websocket.send_json({
                        "type": "error",
                        "request_id": request_id,
                        "message": "报告不存在或无权限访问"
                    })
                    break

                intent = str(request.intent or "view").strip().lower()
                if intent not in {"view", "edit", "release"}:
                    await websocket.send_json({
                        "type": "error",
                        "request_id": request_id,
                        "message": "intent 仅支持 view / edit / release"
                    })
                    continue

                if not _can_user_edit_report(report, current_user):
                    if intent == "edit":
                        state = _build_collaboration_state(
                            db,
                            report_id,
                            current_user,
                            granted=False,
                            report=report
                        )
                    else:
                        state = _build_collaboration_state(
                            db,
                            report_id,
                            current_user,
                            granted=None,
                            report=report
                        )
                else:
                    supported, granted = _run_collaboration_intent(
                        db,
                        report_id,
                        current_user,
                        _utcnow(),
                        intent=intent,
                        activity=request.activity
                    )

                    if supported:
                        db.commit()
                        state = _build_collaboration_state(
                            db,
                            report_id,
                            current_user,
                            granted=granted,
                            report=report
                        )
                    else:
                        state = _build_collaboration_fallback_state(
                            db,
                            report_id,
                            current_user,
                            granted=granted,
                            report=report
                        )
                await websocket.send_json({
                    "type": "state",
                    "request_id": request_id,
                    "state": state.model_dump(mode="json")
                })
            except Exception as exc:
                db.rollback()
                print(f"Collaboration websocket message failed for report {report_id}: {exc}")
                await websocket.send_json({
                    "type": "error",
                    "request_id": request_id,
                    "message": "协同状态更新失败"
                })
                continue
            finally:
                db.close()

            await _broadcast_collaboration_state(report_id)
    except WebSocketDisconnect:
        pass
    finally:
        db = SessionLocal()
        try:
            refreshed_user = db.query(User).filter(
                User.id == client.user_id,
                User.is_cancel == False
            ).first()
            if refreshed_user:
                supported, _granted = _run_collaboration_intent(
                    db,
                    report_id,
                    refreshed_user,
                    _utcnow(),
                    intent="release"
                )
                if supported:
                    db.commit()
        except Exception as exc:
            db.rollback()
            print(f"Collaboration websocket release failed for report {report_id}: {exc}")
        finally:
            db.close()

        await collaboration_socket_hub.disconnect(client)
        await _broadcast_collaboration_state(report_id)


@router.post("/reports/{report_id}/annotation/draft", response_model=SaveDraftResponse)
def save_draft(
    report_id: int,
    request: DraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor", "admin"]))
):
    """保存草稿"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.role == "admin" or current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not _can_user_edit_report(report, current_user):
        raise HTTPException(status_code=403, detail=_build_view_only_message())
    if current_user.role == "admin" and report.status == STATUS_IMPORTED:
        raise HTTPException(status_code=400, detail="请先分发报告给用户，再开始协同标注")

    now = _utcnow()
    collaboration_supported, granted = _run_collaboration_intent(
        db,
        report_id,
        current_user,
        now,
        intent="edit"
    )
    if collaboration_supported and not granted:
        db.commit()
        raise HTTPException(status_code=409, detail=_build_lock_conflict_message(db, report_id, current_user))

    # 查找或创建标注
    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()
    if report.status in [STATUS_SUBMITTED, STATUS_DONE] or (
        report.status == STATUS_IMPORTED and annotation and annotation.status == "SUBMITTED"
    ):
        raise HTTPException(status_code=400, detail="Already submitted")

    if not annotation:
        annotation_owner_id = report.assigned_doctor_id or current_user.id
        annotation = Annotation(
            report_id=report_id,
            doctor_id=annotation_owner_id,
            status="DRAFT",
            annotation_user_ids=[]
        )
        db.add(annotation)

    # 更新数据
    annotation.data = request.data.model_dump()
    annotation.status = "DRAFT"
    annotation.draft_saved_at = now
    annotation.submitted_at = None

    # 更新报告状态
    if report.status == STATUS_ASSIGNED:
        report.status = STATUS_IN_PROGRESS
    elif report.status == STATUS_REVIEW_ASSIGNED:
        report.status = STATUS_REVIEW_IN_PROGRESS

    db.commit()
    db.refresh(annotation)
    _schedule_collaboration_state_broadcast(report_id)
    _schedule_report_updates_broadcast(
        "draft-saved",
        report_id,
        status=report.status,
        annotation_status=annotation.status,
        review_completed_user_ids=_normalize_review_completed_user_ids(report.review_completed_user_ids)
    )

    return SaveDraftResponse(ok=True, saved_at=now)


@router.post("/reports/{report_id}/annotation/submit", response_model=SubmitResponse)
def submit_annotation(
    report_id: int,
    request: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor", "admin"]))
):
    """提交标注"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.role == "admin" or current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not _can_user_edit_report(report, current_user):
        raise HTTPException(status_code=403, detail=_build_view_only_message())
    if current_user.role == "admin" and report.status == STATUS_IMPORTED:
        raise HTTPException(status_code=400, detail="请先分发报告给用户，再开始协同标注")
    if report.status == STATUS_DONE:
        raise HTTPException(status_code=400, detail="Already done")

    is_review_mode = report.status in [STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS]
    is_admin_imported_annotation = current_user.role == "admin" and report.status == STATUS_IMPORTED
    now = _utcnow()
    collaboration_supported, granted = _run_collaboration_intent(
        db,
        report_id,
        current_user,
        now,
        intent="edit"
    )
    if collaboration_supported and not granted:
        db.commit()
        raise HTTPException(status_code=409, detail=_build_lock_conflict_message(db, report_id, current_user))

    # 查找或创建标注
    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()
    if (
        not is_review_mode and (
            report.status == STATUS_SUBMITTED or
            (report.status == STATUS_IMPORTED and annotation and annotation.status == "SUBMITTED")
        )
    ):
        raise HTTPException(status_code=400, detail="Already submitted")

    if not annotation:
        annotation_owner_id = report.annotator_doctor_id or report.assigned_doctor_id or current_user.id
        annotation = Annotation(
            report_id=report_id,
            doctor_id=annotation_owner_id,
            annotation_user_ids=[]
        )
        db.add(annotation)

    # 更新数据
    annotation.data = request.data.model_dump()
    annotation.status = "SUBMITTED"
    annotation.submitted_at = now
    if not is_review_mode:
        _append_annotation_user_id(annotation, current_user.id)

    # 更新报告状态
    if is_review_mode:
        _append_review_completed_user_id(report, current_user.id)
        report.status = STATUS_DONE
        report.reviewed_at = now
        report.review_completed_at = now
        if not report.reviewer_doctor_id:
            report.reviewer_doctor_id = current_user.id
    elif is_admin_imported_annotation:
        # 管理员可直接标注待分发报告，但不能改变该报告的分发状态。
        report.submitted_at = None
    else:
        report.status = STATUS_SUBMITTED
        report.submitted_at = now
        if not report.annotator_doctor_id:
            report.annotator_doctor_id = current_user.id

    # 查找下一个报告
    next_statuses = [STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS] if is_review_mode else [STATUS_ASSIGNED, STATUS_IN_PROGRESS]
    next_report_query = db.query(Report).filter(
        Report.id != report_id,
        Report.is_cancel == False,
        Report.status.in_(next_statuses)
    )
    if current_user.role != "admin":
        next_report_query = next_report_query.filter(Report.assigned_doctor_id == current_user.id)
    next_report = next_report_query.first()

    db.commit()
    if collaboration_supported:
        _best_effort_release_edit_lock(db, report_id, current_user)
    _schedule_collaboration_state_broadcast(report_id)
    _schedule_report_updates_broadcast(
        "submitted",
        report_id,
        status=report.status,
        annotation_status=annotation.status,
        review_completed_user_ids=_normalize_review_completed_user_ids(report.review_completed_user_ids)
    )

    return SubmitResponse(
        ok=True,
        submitted_at=now,
        next_report_id=next_report.id if next_report else None
    )


@router.post("/reports/{report_id}/annotation/cancel")
def cancel_annotation(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor", "admin"]))
):
    """取消已提交标注，回到待标注状态"""
    if current_user.role == "admin" or current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not _can_user_edit_report(report, current_user):
        raise HTTPException(status_code=403, detail=_build_view_only_message())

    now = _utcnow()
    collaboration_supported, granted = _run_collaboration_intent(
        db,
        report_id,
        current_user,
        now,
        intent="edit"
    )
    if collaboration_supported and not granted:
        db.commit()
        raise HTTPException(status_code=409, detail=_build_lock_conflict_message(db, report_id, current_user))

    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()
    is_review_workflow = _is_review_task(report)

    if is_review_workflow:
        is_current_review_user = bool(
            report.reviewer_doctor_id == current_user.id
            or current_user.id in _normalize_review_completed_user_ids(report.review_completed_user_ids)
        )
        if not is_current_review_user:
            raise HTTPException(status_code=400, detail="该报告已被二次分发复核，无法取消标注")

    if annotation:
        annotation.status = "DRAFT"
        annotation.submitted_at = None

    review_completed_user_ids = _normalize_review_completed_user_ids(report.review_completed_user_ids)
    if current_user.id in review_completed_user_ids:
        report.review_completed_user_ids = [
            user_id for user_id in review_completed_user_ids
            if user_id != current_user.id
        ]

    if report.status == STATUS_IMPORTED:
        report.submitted_at = None
    elif is_review_workflow:
        report.status = STATUS_REVIEW_IN_PROGRESS if annotation else STATUS_REVIEW_ASSIGNED
        report.reviewed_at = None
        if not _normalize_review_completed_user_ids(report.review_completed_user_ids):
            report.review_completed_at = None
    else:
        report.status = STATUS_IN_PROGRESS if annotation else STATUS_ASSIGNED
        report.submitted_at = None
    db.commit()
    _schedule_collaboration_state_broadcast(report_id)
    _schedule_report_updates_broadcast(
        "canceled",
        report_id,
        status=report.status,
        annotation_status=annotation.status if annotation else None,
        review_completed_user_ids=_normalize_review_completed_user_ids(report.review_completed_user_ids)
    )
    return {"ok": True}
