from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session, load_only
from ...core.database import get_db
from ...models.user import User
from ...models.report import Report
from ...models.annotation import Annotation
from ...schemas.doctor import (
    DoctorReportResponse, DoctorReportListResponse, DoctorProgressResponse,
    DraftRequest, SubmitRequest, SaveDraftResponse, SubmitResponse
)
from ..deps import get_current_user, require_role

router = APIRouter()

STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_REVIEW_ASSIGNED = "REVIEW_ASSIGNED"
STATUS_REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
STATUS_DONE = "DONE"


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
    annotated_statuses = [STATUS_SUBMITTED, STATUS_DONE]

    # 根据 can_view_all 权限决定过滤条件
    if current_user.role == "admin":
        query = db.query(Report).filter(Report.is_cancel == False)
    elif current_user.can_view_all and not only_mine:
        # 可以查看所有报告
        query = db.query(Report).filter(Report.is_cancel == False)
    else:
        # 只能查看分配给自己的报告
        query = db.query(Report).filter(
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        )

    if lite:
        query = query.options(load_only(
            Report.id,
            Report.external_id,
            Report.ris_no,
            Report.imported_at,
            Report.modality,
            Report.patient_name,
            Report.patient_sex,
            Report.patient_age,
            Report.exam_item,
            Report.exam_mode,
            Report.exam_group,
            Report.status,
            Report.assigned_doctor_id,
            Report.assigned_at,
            Report.annotator_doctor_id,
            Report.reviewer_doctor_id,
            Report.review_assigned_at,
            Report.reviewed_at,
            Report.submitted_at,
        ))

    if q:
        query = query.filter(
            (Report.ris_no.ilike(f"%{q}%")) |
            (Report.external_id.ilike(f"%{q}%")) |
            (Report.report_text.ilike(f"%{q}%"))
        )

    base_query = query
    progress_total, progress_done = base_query.with_entities(
        func.count(Report.id),
        func.coalesce(
            func.sum(case((Report.status.in_(annotated_statuses), 1), else_=0)),
            0
        )
    ).one()

    # 按 tab 筛选状态
    if tab == "unannotated":
        query = query.filter(Report.status.in_([STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS]))
    elif tab == "annotated":
        query = query.filter(Report.status.in_(annotated_statuses))
    elif tab == "no_error":
        query = query.join(Annotation, Annotation.report_id == Report.id).filter(
            Report.status.in_(annotated_statuses),
            Annotation.data.contains({"no_error": True})
        ).distinct(Report.id)

    if tab == "all":
        query = query.order_by(
            case((Report.status.in_(annotated_statuses), 1), else_=0),
            Report.id.asc()
        )
    else:
        query = query.order_by(Report.id.asc())

    total = query.count()
    paged_reports = query.offset((page - 1) * page_size).limit(page_size).all()

    annotation_by_report_id = {}
    if paged_reports and not lite:
        report_ids = [report.id for report in paged_reports]
        annotation_rows = db.query(Annotation).filter(Annotation.report_id.in_(report_ids)).all()
        annotation_by_report_id = {annotation.report_id: annotation for annotation in annotation_rows}

    paged_items = []
    for report in paged_reports:
        annotation = annotation_by_report_id.get(report.id) if not lite else None
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
            submitted_at=report.submitted_at,
            pre_annotations=None if lite else report.pre_annotations,
            annotation=annotation
        ))

    return DoctorReportListResponse(
        items=paged_items,
        page=page,
        page_size=page_size,
        total=total,
        progress=DoctorProgressResponse(done=progress_done or 0, total=progress_total or 0)
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
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # 复核员打开待复核报告即进入“复核中”
    if report.status == STATUS_REVIEW_ASSIGNED and report.assigned_doctor_id == current_user.id:
        report.status = STATUS_REVIEW_IN_PROGRESS
        db.commit()
        db.refresh(report)

    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()

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
        submitted_at=report.submitted_at,
        pre_annotations=report.pre_annotations,
        annotation=annotation
    )


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
    if report.status in [STATUS_SUBMITTED, STATUS_DONE]:
        raise HTTPException(status_code=400, detail="Already submitted")

    now = datetime.utcnow()

    # 查找或创建标注
    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()

    if not annotation:
        annotation_owner_id = report.assigned_doctor_id or current_user.id
        annotation = Annotation(
            report_id=report_id,
            doctor_id=annotation_owner_id,
            status="DRAFT"
        )
        db.add(annotation)

    # 更新数据
    annotation.data = request.data.model_dump()
    annotation.draft_saved_at = now

    # 更新报告状态
    if report.status == STATUS_ASSIGNED:
        report.status = STATUS_IN_PROGRESS
    elif report.status == STATUS_REVIEW_ASSIGNED:
        report.status = STATUS_REVIEW_IN_PROGRESS

    db.commit()
    db.refresh(annotation)

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
    if report.status == STATUS_DONE:
        raise HTTPException(status_code=400, detail="Already done")

    is_review_mode = report.status in [STATUS_REVIEW_ASSIGNED, STATUS_REVIEW_IN_PROGRESS]
    if report.status == STATUS_SUBMITTED and not is_review_mode:
        raise HTTPException(status_code=400, detail="Already submitted")

    now = datetime.utcnow()

    # 查找或创建标注
    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()

    if not annotation:
        annotation_owner_id = report.annotator_doctor_id or report.assigned_doctor_id or current_user.id
        annotation = Annotation(
            report_id=report_id,
            doctor_id=annotation_owner_id
        )
        db.add(annotation)

    # 更新数据
    annotation.data = request.data.model_dump()
    annotation.status = "SUBMITTED"
    annotation.submitted_at = now

    # 更新报告状态
    if is_review_mode:
        report.status = STATUS_DONE
        report.reviewed_at = now
        if not report.reviewer_doctor_id:
            report.reviewer_doctor_id = current_user.id
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

    annotation = db.query(Annotation).filter(Annotation.report_id == report_id).first()

    if annotation:
        annotation.status = "DRAFT"
        annotation.submitted_at = None

    if report.status == STATUS_REVIEW_ASSIGNED:
        report.status = STATUS_REVIEW_IN_PROGRESS
        report.reviewed_at = None
    else:
        report.status = STATUS_IN_PROGRESS if annotation else STATUS_ASSIGNED
        report.submitted_at = None
    db.commit()
    return {"ok": True}
