from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from ..core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(128), index=True)  # 兼容旧字段，也可存 RIS_NO
    ris_no = Column(String(128), index=True)  # 检查号
    report_text = Column(Text, nullable=False)  # 报告全文（DESCRIPTION + IMPRESSION）
    status = Column(String(32), default="IMPORTED", index=True)
    is_cancel = Column(Boolean, default=False, index=True)  # False=未删除, True=已删除

    # 扩展字段
    modality = Column(String(64))  # 检查类型
    patient_name = Column(String(64))  # 患者姓名
    patient_sex = Column(String(16))  # 性别
    patient_age = Column(String(32))  # 年龄
    exam_item = Column(String(256))  # 检查项目
    exam_mode = Column(String(128))  # 检查模式（可选）
    exam_group = Column(String(128))  # 检查组（可选）
    description = Column(Text)  # 检查所见
    impression = Column(Text)  # 诊断意见

    # 预标注数据
    pre_annotations = Column(JSONB, nullable=True, default=list)  # 预标注错误列表

    imported_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

    assigned_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
