from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    enabled: bool
    can_view_all: bool = False
    view_all_requested: bool = False

    class Config:
        from_attributes = True
