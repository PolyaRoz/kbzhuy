from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
