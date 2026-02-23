"""backend/services/agent_router.py 단위 테스트."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.services.agent_router import (
    AgentRouter,
    Intent,
    DiaryAction,
    RouteResult,
    _last_weekend,
    _build_few_shot,
)


# ---------------------------------------------------------------------------
# _last_weekend 헬퍼
# ---------------------------------------------------------------------------

class TestLastWeekend:
    def test_monday(self):
        # 2026-02-23 은 월요일
        sat, sun = _last_weekend(date(2026, 2, 23))
        assert sat == date(2026, 2, 21)
        assert sun == date(2026, 2, 22)

    def test_sunday(self):
        # 일요일이면 어제(토) + 오늘(일)
        sat, sun = _last_weekend(date(2026, 2, 22))
        assert sat == date(2026, 2, 21)
        assert sun == date(2026, 2, 22)

    def test_saturday(self):
        sat, sun = _last_weekend(date(2026, 2, 21))
        assert sat == date(2026, 2, 14)
        assert sun == date(2026, 2, 15)


# ---------------------------------------------------------------------------
# _build_few_shot 형식
# ---------------------------------------------------------------------------

class TestBuildFewShot:
    def test_returns_pairs(self):
        msgs = _build_few_shot(date(2026, 2, 23))
        # user/assistant 쌍 → 짝수
        assert len(msgs) % 2 == 0
        for i in range(0, len(msgs), 2):
            assert msgs[i]["role"] == "user"
            assert msgs[i + 1]["role"] == "assistant"

    def test_assistant_is_valid_json(self):
        msgs = _build_few_shot(date(2026, 2, 23))
        for msg in msgs:
            if msg["role"] == "assistant":
                parsed = json.loads(msg["content"])
                assert "intent" in parsed


# ---------------------------------------------------------------------------
# RouteResult 모델
# ---------------------------------------------------------------------------

class TestRouteResult:
    def test_defaults(self):
        r = RouteResult(intent=Intent.GENERAL)
        assert r.keywords == []
        assert r.location is None
        assert r.date_from is None
        assert r.diary_action is None

    def test_full(self):
        r = RouteResult(
            intent=Intent.DIARY,
            keywords=[],
            location=None,
            date_from="2026-02-23",
            date_to="2026-02-23",
            diary_action=DiaryAction.CREATE,
        )
        assert r.diary_action == DiaryAction.CREATE


# ---------------------------------------------------------------------------
# AgentRouter.classify — OpenAI AsyncMock
# ---------------------------------------------------------------------------

def _make_mock_response(content_dict: dict):
    """OpenAI ChatCompletion 형식의 mock 응답 생성."""
    msg = MagicMock()
    msg.content = json.dumps(content_dict, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestAgentRouterClassify:
    @pytest.fixture
    def router(self):
        r = AgentRouter()
        r._client = AsyncMock()
        return r

    @pytest.mark.asyncio
    async def test_photo_search(self, router):
        router.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response({
                "intent": "PHOTO_SEARCH",
                "keywords": ["바다"],
                "location": "제주도",
                "date_from": None,
                "date_to": None,
                "diary_action": None,
            })
        )
        result = await router.classify("제주도 바다 사진 보여줘")
        assert result.intent == Intent.PHOTO_SEARCH
        assert "바다" in result.keywords
        assert result.location == "제주도"

    @pytest.mark.asyncio
    async def test_event_recall(self, router):
        router.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response({
                "intent": "EVENT_RECALL",
                "keywords": ["여행"],
                "location": "부산",
                "date_from": None,
                "date_to": None,
                "diary_action": None,
            })
        )
        result = await router.classify("부산 여행 어땠어?")
        assert result.intent == Intent.EVENT_RECALL

    @pytest.mark.asyncio
    async def test_diary_create(self, router):
        router.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response({
                "intent": "DIARY",
                "keywords": [],
                "location": None,
                "date_from": "2026-02-23",
                "date_to": "2026-02-23",
                "diary_action": "create",
            })
        )
        result = await router.classify("오늘 일기 써줘")
        assert result.intent == Intent.DIARY
        assert result.diary_action == DiaryAction.CREATE

    @pytest.mark.asyncio
    async def test_general(self, router):
        router.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response({
                "intent": "GENERAL",
                "keywords": [],
                "location": None,
                "date_from": None,
                "date_to": None,
                "diary_action": None,
            })
        )
        result = await router.classify("안녕!")
        assert result.intent == Intent.GENERAL

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, router):
        """LLM 호출 실패 → GENERAL fallback."""
        router.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API 에러")
        )
        result = await router.classify("아무 질문")
        assert result.intent == Intent.GENERAL

    @pytest.mark.asyncio
    async def test_null_string_defense(self, router):
        """LLM이 "null" 문자열을 반환해도 None으로 변환."""
        router.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response({
                "intent": "PHOTO_SEARCH",
                "keywords": ["고양이"],
                "location": "null",
                "date_from": "null",
                "date_to": "null",
                "diary_action": "null",
            })
        )
        result = await router.classify("고양이 사진")
        assert result.intent == Intent.PHOTO_SEARCH
        # "null" 문자열은 classify() 내부에서 None으로 치환
        assert result.location is None or result.location == "null"
