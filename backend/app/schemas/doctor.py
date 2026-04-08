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
    process_method: Optional[str] = None
    replacement_content: Optional[str] = None
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
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DoctorReviewUserResponse(BaseModel):
    id: int
    username: str
    role: str
    employee_id: Optional[str] = None


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
    annotator_doctor_id: Optional[int] = None
    reviewer_doctor_id: Optional[int] = None
    review_assigned_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    review_completed_at: Optional[datetime] = None
    review_completed_user_ids: List[int] = []
    review_completed_users: List[DoctorReviewUserResponse] = []
    submitted_at: Optional[datetime]
    annotation_status: Optional[str] = None
    annotation_submitted_at: Optional[datetime] = None
    is_review_task: bool = False
    is_current_user_assigned_reviewer: bool = False
    has_current_user_completed_review: bool = False
    pre_annotations: Optional[List[Any]] = None  # 预标注错误列表
    annotation: Optional[AnnotationResponse] = None

    class Config:
        from_attributes = True


class DoctorProgressResponse(BaseModel):
    done: int = 0
    total: int = 0


class DoctorReportListResponse(BaseModel):
    items: List[DoctorReportResponse]
    page: int
    page_size: int
    total: int
    progress: DoctorProgressResponse
    annotation_progress: DoctorProgressResponse
    review_progress: DoctorProgressResponse


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


class CollaborationActivityPayload(BaseModel):
    status: Optional[str] = None
    label: Optional[str] = None
    content_type: Optional[str] = None
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    selection_text: Optional[str] = None


class CollaborationHeartbeatRequest(BaseModel):
    intent: str = "view"  # view / edit / release
    activity: Optional[CollaborationActivityPayload] = None


class CollaborationParticipantResponse(BaseModel):
    user_id: int
    username: str
    role: str
    is_me: bool = False
    is_editor: bool = False
    last_seen_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None


class CollaborationActivityResponse(BaseModel):
    status: Optional[str] = None
    label: Optional[str] = None
    content_type: Optional[str] = None
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    selection_text: Optional[str] = None


class CollaborationStateResponse(BaseModel):
    report_id: int
    participants: List[CollaborationParticipantResponse] = []
    current_editor_user_id: Optional[int] = None
    current_editor_username: Optional[str] = None
    current_editor_role: Optional[str] = None
    current_activity_user_id: Optional[int] = None
    current_activity_username: Optional[str] = None
    current_activity_role: Optional[str] = None
    current_activity_is_editor: bool = False
    current_activity: Optional[CollaborationActivityResponse] = None
    is_edit_locked: bool = False
    can_edit: bool = True
    granted: Optional[bool] = None
    expires_at: Optional[datetime] = None
    annotation_updated_at: Optional[datetime] = None
