from pydantic import BaseModel, EmailStr

from app.models.user import ROLES


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str

    def validate_role(self):
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")


class UserResponse(BaseModel):
    id: str
    email: str
    role: str

    class Config:
        from_attributes = True
