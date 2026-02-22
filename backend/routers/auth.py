"""인증 라우터 — 회원가입 / 로그인."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from db.schema import get_connection
from db.crud import create_user, get_user_by_email
from backend.services.auth import hash_password, verify_password, create_access_token

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    conn = get_connection()
    try:
        existing = get_user_by_email(conn, req.email)
        if existing:
            raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

        hashed = hash_password(req.password)
        user_id = create_user(conn, req.email, req.username, hashed)
        token = create_access_token(user_id, req.email)

        return AuthResponse(
            access_token=token,
            user_id=user_id,
            username=req.username,
        )
    finally:
        conn.close()


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    conn = get_connection()
    try:
        user = get_user_by_email(conn, req.email)
        if not user or not verify_password(req.password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

        token = create_access_token(user["id"], user["email"])

        return AuthResponse(
            access_token=token,
            user_id=user["id"],
            username=user["username"],
        )
    finally:
        conn.close()
