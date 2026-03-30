from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...core.security import verify_password, create_access_token
from ...models.user import User
from ...schemas.auth import LoginRequest, TokenResponse, UserResponse
from ..deps import get_current_user

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.username == request.username,
        User.is_cancel == False
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="不存在的用户"
        )
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误"
        )
    if not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用，请联系管理员"
        )
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return TokenResponse(access_token=access_token, role=user.role)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        enabled=current_user.enabled,
        can_view_all=current_user.can_view_all,
        view_all_requested=current_user.view_all_requested
    )
