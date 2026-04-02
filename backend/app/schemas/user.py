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
    role: Optional[str] = None
    employee_id: Optional[str] = None  # 工号
    enabled: Optional[bool] = None
    can_view_all: Optional[bool] = None
    view_all_requested: Optional[bool] = None


class UserListResponse(BaseModel):
    id: int
    username: str
    role: str
    employee_id: Optional[str] = None  # 工号
    enabled: bool
    can_view_all: bool = False
    view_all_requested: bool = False

    class Config:
        from_attributes = True
