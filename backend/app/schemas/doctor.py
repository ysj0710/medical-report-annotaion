from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime


class ErrorItem(BaseModel):
    error_type: Optional[str] = None
    severity: Optional[str] = None
    location: Optional[str] = None
    evidence_text: Optional[str] = None
    description: Optional[str] = None
    suggestion: Optional[str] = None
    anchor: Optional[dict] = None


class AnnotationData(BaseModel):
    no_error: bool = False
    error_items: List[ErrorItem] = []
    note: Optional[str] = ""


class AnnotationResponse(BaseModel):
    id: int
    report_id: int
    doctor_id: int
    data: dict
    status: str
    draft_saved_at: Optional[datetime]
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True


class DoctorReportResponse(BaseModel):
    id: int
    external_id: Optional[str]
    ris_no: Optional[str] = None
    report_text: str
    imported_at: Optional[datetime] = None
    modality: Optional[str] = None
    patient_name: Optional[str] = None
    patient_sex: Optional[str] = None
    patient_age: Optional[str] = None
    exam_item: Optional[str] = None
    exam_mode: Optional[str] = None
    exam_group: Optional[str] = None
    description: Optional[str] = None
    impression: Optional[str] = None
    status: str
    assigned_doctor_id: Optional[int] = None
    assigned_at: Optional[datetime]
    submitted_at: Optional[datetime]
    pre_annotations: Optional[List[Any]] = None  # 预标注错误列表
    annotation: Optional[AnnotationResponse] = None

    class Config:
        from_attributes = True


class DoctorReportListResponse(BaseModel):
    items: List[DoctorReportResponse]
    page: int
    page_size: int
    total: int


class DraftRequest(BaseModel):
    data: AnnotationData


class SubmitRequest(BaseModel):
    data: AnnotationData


class SaveDraftResponse(BaseModel):
    ok: bool
    saved_at: datetime


class SubmitResponse(BaseModel):
    ok: bool
    submitted_at: datetime
    next_report_id: Optional[int] = None
