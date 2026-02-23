"""pytest 공용 fixture — DB 격리, 인증, TestClient, 테스트 이미지 생성."""

from __future__ import annotations

import io
import os
import struct
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# 테스트 이미지 생성 헬퍼
# ---------------------------------------------------------------------------

def _rational(value: float) -> tuple:
    """float → EXIF GPS Rational tuple (IFDRational 객체 3개)."""
    from PIL.TiffImagePlugin import IFDRational

    d = int(value)
    m = int((value - d) * 60)
    s = (value - d - m / 60) * 3600
    return (IFDRational(d), IFDRational(m), IFDRational(int(s * 100), 100))


def _build_gps_ifd(lat: float, lon: float) -> dict:
    """Pillow Exif 형식의 GPSInfo IFD dict 생성."""
    gps_ifd = {
        1: "N" if lat >= 0 else "S",   # GPSLatitudeRef
        2: _rational(abs(lat)),          # GPSLatitude
        3: "E" if lon >= 0 else "W",    # GPSLongitudeRef
        4: _rational(abs(lon)),          # GPSLongitude
    }
    return gps_ifd


def create_test_jpeg_with_gps(
    lat: float = 37.5665,
    lon: float = 126.9780,
    taken_at: str = "2025:12:25 14:30:00",
) -> str:
    """GPS + 촬영시각 EXIF가 포함된 테스트 JPEG를 생성하여 경로를 반환한다."""
    img = Image.new("RGB", (100, 100), color="blue")
    exif = img.getexif()

    # DateTimeOriginal (tag 36867)
    exif[36867] = taken_at
    # DateTime (tag 306)
    exif[306] = taken_at

    # GPSInfo (tag 34853)
    gps_ifd = _build_gps_ifd(lat, lon)
    exif[34853] = gps_ifd

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img.save(path, "JPEG", exif=exif.tobytes())
    return path


def create_test_jpeg_no_gps(taken_at: str = "2025:12:25 14:30:00") -> str:
    """GPS 없이 촬영시각만 있는 JPEG."""
    img = Image.new("RGB", (100, 100), color="green")
    exif = img.getexif()
    exif[36867] = taken_at
    exif[306] = taken_at

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img.save(path, "JPEG", exif=exif.tobytes())
    return path


def create_test_png_no_exif() -> str:
    """EXIF 데이터가 없는 PNG."""
    img = Image.new("RGB", (100, 100), color="red")
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path, "PNG")
    return path


# ---------------------------------------------------------------------------
# 테스트 이미지 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_gps_jpg():
    """GPS+시각 포함 JPEG 경로."""
    path = create_test_jpeg_with_gps()
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_no_gps_jpg():
    """GPS 없는 JPEG 경로."""
    path = create_test_jpeg_no_gps()
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_no_exif_png():
    """EXIF 없는 PNG 경로."""
    path = create_test_png_no_exif()
    yield path
    if os.path.exists(path):
        os.unlink(path)


# ---------------------------------------------------------------------------
# DB fixture (PostgreSQL — SAVEPOINT 격리)
# ---------------------------------------------------------------------------

class _NoCommitConnection:
    """psycopg2 connection 래퍼 — commit()을 no-op으로 만들어 테스트 격리."""

    def __init__(self, real_conn):
        self._conn = real_conn

    def commit(self):
        """no-op: 테스트 중 실제 커밋 방지."""

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture
def db_conn():
    """테스트용 DB 연결 — commit 차단 + ROLLBACK 격리.

    환경변수 TEST_DATABASE_URL 또는 DATABASE_URL 필요.
    crud 함수들이 conn.commit()을 직접 호출하므로,
    테스트 중에는 commit을 no-op으로 만들고 teardown에서 전체 ROLLBACK.
    """
    import psycopg2

    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL 환경변수가 설정되지 않았습니다.")

    conn = psycopg2.connect(url)
    conn.autocommit = False

    from pgvector.psycopg2 import register_vector
    register_vector(conn)

    wrapper = _NoCommitConnection(conn)

    yield wrapper

    # 테스트 종료 시 모든 변경사항 롤백
    conn.rollback()
    conn.close()


@pytest.fixture
def test_user(db_conn):
    """테스트 사용자 생성 → user_id 반환 (commit 차단 상태이므로 teardown 시 자동 롤백)."""
    from db.crud import create_user

    user_id = create_user(
        db_conn,
        email="test@pictrace.dev",
        username="testuser",
        hashed_password="$2b$12$fakehash",
    )
    return user_id


# ---------------------------------------------------------------------------
# 인증 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_token():
    """테스트용 JWT 토큰."""
    from backend.services.auth import create_access_token
    return create_access_token(user_id=1, email="test@pictrace.dev")


@pytest.fixture
def auth_headers(auth_token):
    """Authorization 헤더 dict."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def client(auth_headers):
    """인증 헤더가 포함된 FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from backend.main import app

    c = TestClient(app)
    c.headers.update(auth_headers)
    return c
