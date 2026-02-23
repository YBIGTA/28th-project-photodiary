"""채팅 → RAG 핸들러 통합 테스트.

AgentRouter(LLM)와 RAG Engine의 LLM 호출을 mock하고,
DB 검색/저장 흐름이 정상 동작하는지 검증.
"""

from __future__ import annotations

import json
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.services.agent_router import Intent, DiaryAction, RouteResult
from backend.services.rag_engine import RAGEngine, _build_response, _resolve_location, _parse_date
from db.crud import (
    insert_photo,
    insert_embedding,
    insert_diary,
    get_diary,
    bulk_insert_photo_keywords,
)


pytestmark = pytest.mark.db


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _unit_vec(d: int = 0, dim: int = 768) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    vec[d % dim] = 1.0
    return vec


def _seed_photo_with_embedding(db_conn, user_id, **kwargs):
    """사진 + 임베딩을 DB에 삽입하고 photo_id를 반환."""
    pid = insert_photo(
        db_conn, user_id,
        file_path=kwargs.get("file_path", "s3://test.jpg"),
        lat=kwargs.get("lat"),
        lon=kwargs.get("lon"),
        place_info=kwargs.get("place_info"),
        taken_at=kwargs.get("taken_at"),
    )
    vec = kwargs.get("embedding", _unit_vec(direction=pid))
    insert_embedding(db_conn, pid, vec)
    return pid


# ---------------------------------------------------------------------------
# _resolve_location / _parse_date 헬퍼 테스트
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_resolve_location_state(self):
        state, city, district = _resolve_location("서울특별시")
        assert state == "서울특별시"
        assert city is None

    def test_resolve_location_district(self):
        state, city, district = _resolve_location("강남구")
        assert district == "강남구"
        assert state is None

    def test_resolve_location_city(self):
        state, city, district = _resolve_location("부산")
        assert city == "부산"

    def test_resolve_location_none(self):
        assert _resolve_location(None) == (None, None, None)

    def test_parse_date_valid(self):
        dt = _parse_date("2025-12-25")
        assert dt.year == 2025
        assert dt.month == 12

    def test_parse_date_invalid(self):
        assert _parse_date("invalid") is None

    def test_parse_date_none(self):
        assert _parse_date(None) is None


# ---------------------------------------------------------------------------
# _build_response 형식
# ---------------------------------------------------------------------------

class TestBuildResponse:
    def test_structure(self):
        result = RouteResult(intent=Intent.PHOTO_SEARCH, keywords=["바다"])
        resp = _build_response(result, "테스트 답변", [{"id": 1}])

        assert resp["intent"] == "PHOTO_SEARCH"
        assert resp["answer"] == "테스트 답변"
        assert resp["photos"] == [{"id": 1}]
        assert resp["params"]["keywords"] == ["바다"]


# ---------------------------------------------------------------------------
# PHOTO_SEARCH 핸들러
# ---------------------------------------------------------------------------

class TestPhotoSearchHandler:
    @patch("backend.services.rag_engine.embed_query")
    @patch("backend.services.rag_engine.get_connection")
    async def test_photo_search_returns_photos(
        self, mock_conn, mock_embed, db_conn, test_user,
    ):
        """PHOTO_SEARCH → 사진 리스트 반환."""
        mock_conn.return_value = db_conn
        mock_embed.return_value = _unit_vec(0)

        # 테스트 사진 삽입
        pid = _seed_photo_with_embedding(db_conn, test_user, embedding=_unit_vec(0))

        engine = RAGEngine()
        engine._call_llm = AsyncMock(return_value="관련 사진을 찾았어요!")

        route = RouteResult(intent=Intent.PHOTO_SEARCH, keywords=["테스트"])
        with patch("backend.services.rag_engine.router") as mock_router:
            mock_router.classify = AsyncMock(return_value=route)
            resp = await engine.answer("테스트 사진 보여줘", test_user)

        assert resp["intent"] == "PHOTO_SEARCH"
        assert len(resp["photos"]) > 0


# ---------------------------------------------------------------------------
# GENERAL 핸들러
# ---------------------------------------------------------------------------

class TestGeneralHandler:
    async def test_general_empty_photos(self):
        """GENERAL → photos 빈 리스트."""
        engine = RAGEngine()
        engine._call_llm = AsyncMock(return_value="안녕하세요!")

        route = RouteResult(intent=Intent.GENERAL)
        with patch("backend.services.rag_engine.router") as mock_router:
            mock_router.classify = AsyncMock(return_value=route)
            resp = await engine.answer("안녕!", 1)

        assert resp["intent"] == "GENERAL"
        assert resp["photos"] == []
        assert resp["answer"]


# ---------------------------------------------------------------------------
# DIARY 핸들러
# ---------------------------------------------------------------------------

class TestDiaryHandler:
    def test_diary_retrieve(self, db_conn, test_user):
        """기존 일기 조회 → DB에서 content 반환."""
        insert_diary(db_conn, test_user, date(2025, 12, 25), "크리스마스 일기")

        diary = get_diary(db_conn, test_user, date(2025, 12, 25))
        assert diary is not None
        assert "크리스마스" in diary["content"]
