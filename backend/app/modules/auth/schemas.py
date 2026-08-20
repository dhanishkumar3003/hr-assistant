from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "hr"


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    user: UserOut