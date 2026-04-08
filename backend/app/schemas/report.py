from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: int
    external_id: Optional[str]
    ris_no: Optional[str]  # 检查号
    report_text: str
    status: str
    imported_by: Optional[int]
    imported_at: Optional[datetime]
    assigned_doctor_id: Optional[int]
    assigned_at: Optional[datetime]
    annotator_doctor_id: Optional[int] = None
    reviewer_doctor_id: Optional[int] = None
    review_assigned_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    review_completed_at: Optional[datetime] = None
    review_completed_user_ids: List[int] = []
    review_completed_users: List[dict[str, Any]] = []
    submitted_at: Optional[datetime]

    # 扩展字段
    modality: Optional[str]  # 检查类型
    patient_name: Optional[str]  # 患者姓名
    patient_sex: Optional[str]  # 性别
    patient_age: Optional[str]  # 年龄
    exam_item: Optional[str]  # 检查项目
    exam_mode: Optional[str]  # 检查模式
    exam_group: Optional[str]  # 检查组
    description: Optional[str]  # 检查所见
    impression: Optional[str]  # 诊断意见

    # 预标注数据
    pre_annotations: Optional[List[Any]] = None  # 预标注错误列表

    # 医生信息（用于列表显示工号）
    doctor_employee_id: Optional[str] = None  # 医生工号
    doctor_username: Optional[str] = None  # 医生用户名
    reviewer_employee_id: Optional[str] = None
    reviewer_username: Optional[str] = None
    annotation_data: Optional[Any] = None
    annotation_status: Optional[str] = None
    annotation_submitted_at: Optional[datetime] = None
    is_review_task: bool = False

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    page: int
    page_size: int
    total: int


class ImportTaskResponse(BaseModel):
    id: int
    file_name: str
    status: str
    total_rows: int
    success_rows: int
    failed_rows: int
    warnings_count: int
    error_report_path: Optional[str]
    message: Optional[str]
    created_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class AssignRequest(BaseModel):
    mode: str  # selected / all
    report_ids: Optional[List[int]] = None
    assign_all: Optional[bool] = None
    q: Optional[str] = None
    status: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_ids: Optional[List[int]] = None
    dispatch_mode: Optional[str] = "auto"  # auto / annotation / review


class AssignResponse(BaseModel):
    assigned: int
    per_doctor: Optional[dict[str, int]] = None
    mode: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    report_ids: List[int]


class BatchDeleteResponse(BaseModel):
    ok: bool
    deleted: int
