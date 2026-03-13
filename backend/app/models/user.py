from sqlalchemy import Column, Integer, String, DateTime, func, Boolean
from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)  # admin/doctor/reviewer
    employee_id = Column(String(32), unique=True, index=True, nullable=True)  # 工号
    enabled = Column(Boolean, default=True)
    is_cancel = Column(Boolean, default=False, index=True)  # False=未删除, True=已删除
    can_view_all = Column(Boolean, default=False)
    view_all_requested = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
