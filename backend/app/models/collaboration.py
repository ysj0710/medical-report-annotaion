from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint, func, String, Text
from ..core.database import Base


class ReportCollaborationSession(Base):
    __tablename__ = "report_collaboration_sessions"
    __table_args__ = (
        UniqueConstraint("report_id", "user_id", name="uq_report_collaboration_session"),
    )

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    active_status = Column(String(32), nullable=True)
    active_label = Column(String(255), nullable=True)
    active_content_type = Column(String(32), nullable=True)
    active_selection_start = Column(Integer, nullable=True)
    active_selection_end = Column(Integer, nullable=True)
    active_selection_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ReportEditLock(Base):
    __tablename__ = "report_edit_locks"

    report_id = Column(Integer, ForeignKey("reports.id"), primary_key=True)
    editor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    acquired_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
