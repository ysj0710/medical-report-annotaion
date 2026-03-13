from typing import Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    role: str  # admin/doctor/reviewer
    employee_id: Optional[str] = None  # 工号


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    employee_id: Optional[str] = None  # 工号
    enabled: Optional[bool] = None
    can_view_all: Optional[bool] = None  # 是否可以查看所有报告
    view_all_requested: Optional[bool] = None  # 是否已申请查看全部


class UserListResponse(BaseModel):
    id: int
    username: str
    role: str
    employee_id: Optional[str] = None  # 工号
    enabled: bool
    can_view_all: bool = False  # 是否可以查看所有报告
    view_all_requested: bool = False  # 是否已申请查看全部

    class Config:
        from_attributes = True
