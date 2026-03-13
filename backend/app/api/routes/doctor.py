from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...models.user import User
from ...models.report import Report
from ...models.annotation import Annotation
from ...schemas.doctor import (
    DoctorReportResponse, DoctorReportListResponse,
    DraftRequest, SubmitRequest, SaveDraftResponse, SubmitResponse
)
from ..deps import get_current_user, require_role

router = APIRouter()

STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_SUBMITTED = "SUBMITTED"
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"]))
):
    """医生端报告列表"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.can_view_all and not only_mine:
        # 可以查看所有报告
        query = db.query(Report).filter(Report.is_cancel == False)
    else:
        # 只能查看分配给自己的报告
        query = db.query(Report).filter(
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        )

    # 按 tab 筛选状态
    if tab == "unannotated":
        query = query.filter(Report.status.in_([STATUS_ASSIGNED, STATUS_IN_PROGRESS]))
    elif tab == "annotated":
        query = query.filter(Report.status.in_([STATUS_SUBMITTED, STATUS_DONE]))
    elif tab == "no_error":
        # 需要通过 annotation 判断 no_error
        query = query.filter(Report.status.in_([STATUS_SUBMITTED, STATUS_DONE]))

    if q:
        query = query.filter(
            (Report.ris_no.ilike(f"%{q}%")) |
            (Report.external_id.ilike(f"%{q}%")) |
            (Report.report_text.ilike(f"%{q}%"))
        )

    all_reports = query.all()

    # 获取每个报告的标注
    items = []
    for report in all_reports:
        annotation = db.query(Annotation).filter(
            Annotation.report_id == report.id,
            Annotation.doctor_id == current_user.id
        ).first()

        # tab == no_error 时过滤
        if tab == "no_error" and annotation:
            if not annotation.data.get("no_error", False):
                continue

        items.append(DoctorReportResponse(
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
            submitted_at=report.submitted_at,
            pre_annotations=report.pre_annotations,
            annotation=annotation
        ))

    def is_annotated(item: DoctorReportResponse) -> bool:
        return item.status in [STATUS_SUBMITTED, STATUS_DONE]

    # 全部列表中将已标注放到底部，未标注优先
    if tab == "all":
        items.sort(key=lambda x: (1 if is_annotated(x) else 0, x.id))
    else:
        items.sort(key=lambda x: x.id)

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = items[start:end]

    return DoctorReportListResponse(
        items=paged_items,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/reports/{report_id}", response_model=DoctorReportResponse)
def get_doctor_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"]))
):
    """医生获取报告详情"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    annotation = db.query(Annotation).filter(
        Annotation.report_id == report_id,
        Annotation.doctor_id == current_user.id
    ).first()

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
        submitted_at=report.submitted_at,
        pre_annotations=report.pre_annotations,
        annotation=annotation
    )


@router.post("/reports/{report_id}/annotation/draft", response_model=SaveDraftResponse)
def save_draft(
    report_id: int,
    request: DraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"]))
):
    """保存草稿"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status == STATUS_SUBMITTED:
        raise HTTPException(status_code=400, detail="Already submitted")

    now = datetime.utcnow()

    # 查找或创建标注
    annotation = db.query(Annotation).filter(
        Annotation.report_id == report_id,
        Annotation.doctor_id == current_user.id
    ).first()

    if not annotation:
        annotation = Annotation(
            report_id=report_id,
            doctor_id=current_user.id,
            status="DRAFT"
        )
        db.add(annotation)

    # 更新数据
    annotation.data = request.data.model_dump()
    annotation.draft_saved_at = now

    # 更新报告状态
    if report.status == STATUS_ASSIGNED:
        report.status = STATUS_IN_PROGRESS

    db.commit()
    db.refresh(annotation)

    return SaveDraftResponse(ok=True, saved_at=now)


@router.post("/reports/{report_id}/annotation/submit", response_model=SubmitResponse)
def submit_annotation(
    report_id: int,
    request: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"]))
):
    """提交标注"""
    # 根据 can_view_all 权限决定过滤条件
    if current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status == STATUS_SUBMITTED:
        raise HTTPException(status_code=400, detail="Already submitted")

    now = datetime.utcnow()

    # 查找或创建标注
    annotation = db.query(Annotation).filter(
        Annotation.report_id == report_id,
        Annotation.doctor_id == current_user.id
    ).first()

    if not annotation:
        annotation = Annotation(
            report_id=report_id,
            doctor_id=current_user.id
        )
        db.add(annotation)

    # 更新数据
    annotation.data = request.data.model_dump()
    annotation.status = "SUBMITTED"
    annotation.submitted_at = now

    # 更新报告状态
    report.status = STATUS_SUBMITTED
    report.submitted_at = now

    # 查找下一个报告
    next_report = db.query(Report).filter(
        Report.id != report_id,
        Report.assigned_doctor_id == current_user.id,
        Report.is_cancel == False,
        Report.status.in_([STATUS_ASSIGNED, STATUS_IN_PROGRESS])
    ).first()

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
    current_user: User = Depends(require_role(["doctor"]))
):
    """取消已提交标注，回到待标注状态"""
    if current_user.can_view_all:
        report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    else:
        report = db.query(Report).filter(
            Report.id == report_id,
            Report.assigned_doctor_id == current_user.id,
            Report.is_cancel == False
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    annotation = db.query(Annotation).filter(
        Annotation.report_id == report_id,
        Annotation.doctor_id == current_user.id
    ).first()

    if annotation:
        db.delete(annotation)

    report.status = STATUS_ASSIGNED
    report.submitted_at = None
    db.commit()
    return {"ok": True}
