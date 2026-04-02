from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from ..core.database import Base


class ImportTask(Base):
    __tablename__ = "import_tasks"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    status = Column(String(32), default="PENDING")  # PENDING/RUNNING/SUCCESS/FAILED

    total_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    warnings_count = Column(Integer, default=0)

    error_report_path = Column(String(512), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    message = Column(String(1024), nullable=True)
