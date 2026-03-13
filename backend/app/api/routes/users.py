from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...core.security import get_password_hash
from ...models.user import User
from ...models.report import Report
from ...models.annotation import Annotation
from ...models.import_task import ImportTask
from ...schemas.user import UserCreate, UserUpdate, UserListResponse
from ..deps import get_current_user, require_role

router = APIRouter()


@router.post("", response_model=UserListResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
        employee_id=user_data.employee_id,
        enabled=True,
        can_view_all=False  # 新用户默认不能查看所有报告
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=List[UserListResponse])
def list_users(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.id.asc()).all()


@router.get("/{user_id}", response_model=UserListResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserListResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_data.username is not None:
        user.username = user_data.username
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)
    if user_data.employee_id is not None:
        user.employee_id = user_data.employee_id
    if user_data.enabled is not None:
        user.enabled = user_data.enabled
    if user_data.can_view_all is not None:
        user.can_view_all = user_data.can_view_all
        if user_data.can_view_all:
            # 授权后清除申请标记
            user.view_all_requested = False
    if user_data.view_all_requested is not None:
        user.view_all_requested = user_data.view_all_requested
    db.commit()
    db.refresh(user)
    return user


@router.post("/view-all-request")
def request_view_all_access(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"]))
):
    """医生提交查看全部报告权限申请。"""
    if current_user.can_view_all:
        return {"ok": True, "requested": False, "message": "Already granted"}

    current_user.view_all_requested = True
    db.commit()
    return {"ok": True, "requested": True}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 不能删除自己，避免当前管理员会话异常
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    # 真删除前清理关联，避免外键约束导致删除失败
    db.query(Report).filter(Report.assigned_doctor_id == user.id).update(
        {Report.assigned_doctor_id: None, Report.assigned_at: None},
        synchronize_session=False
    )
    db.query(Report).filter(Report.imported_by == user.id).update(
        {Report.imported_by: None},
        synchronize_session=False
    )
    db.query(ImportTask).filter(ImportTask.created_by == user.id).update(
        {ImportTask.created_by: None},
        synchronize_session=False
    )
    db.query(Annotation).filter(Annotation.doctor_id == user.id).delete(
        synchronize_session=False
    )

    db.delete(user)
    db.commit()
    return {"ok": True}
