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
    report_ids: Optional[List[int]] = None
    doctor_id: Optional[int] = None
    doctor_ids: Optional[List[int]] = None


class AssignResponse(BaseModel):
    assigned: int
    per_doctor: Optional[dict[str, int]] = None
