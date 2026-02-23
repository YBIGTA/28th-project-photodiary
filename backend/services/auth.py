from __future__ import annotations
"""JWT 인증 유틸리티 — 비밀번호 해싱 + 토큰 생성/검증."""

from typing import Optional

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """평문 비밀번호 → bcrypt 해시."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """평문과 해시된 비밀번호 비교."""
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, email: str) -> str:
    """JWT access token 생성 (HS256, 24시간 만료)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """JWT 토큰 디코딩. 유효하면 payload dict, 아니면 None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
