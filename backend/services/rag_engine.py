"""
rag_engine.py: 의도 분류 → 검색/조회 → 답변 생성을 조율하는 핵심 엔진.

흐름
----
1. AgentRouter 로 사용자 질문의 Intent + 파라미터 추출
2. Intent 에 따라 적절한 파이프라인 실행
   - PHOTO_SEARCH  : 메타필터 + 벡터 검색 → 사진 반환
   - EVENT_RECALL  : 이벤트 조회 → 관련 사진 수집 → 내러티브 생성
   - DIARY         : 일기 생성(create) 또는 조회(retrieve)
   - GENERAL       : LLM 직접 응답
3. 구조화된 JSON 응답 반환
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.services.agent_router import router, Intent, DiaryAction, RouteResult
from db.crud import search_photos, search_photos_filtered
from db.schema import get_connection
from pipeline.core.embedder import embed_query

logger = logging.getLogger(__name__)


class RAGEngine:
    """Router 결과를 받아 검색·생성 파이프라인을 실행하는 오케스트레이터."""

    async def answer(self, query: str, user_id: int) -> dict[str, Any]:
        """사용자 질문을 처리하여 최종 응답을 반환한다.

        Parameters
        ----------
        query : str
            사용자의 자연어 질문.
        user_id : int
            현재 사용자 ID.

        Returns
        -------
        dict
            {"intent": str, "params": dict, "answer": str, "photos": list}
        """
        # ── 1단계: 의도 분류 + 파라미터 추출 ──
        result: RouteResult = await router.classify(query)

        # ── 2단계: Intent 별 파이프라인 분기 ──
        if result.intent == Intent.PHOTO_SEARCH:
            return await self._handle_photo_search(query, user_id, result)

        if result.intent == Intent.EVENT_RECALL:
            return await self._handle_event_recall(query, user_id, result)

        if result.intent == Intent.DIARY:
            return await self._handle_diary(query, user_id, result)

        # GENERAL (기본)
        return await self._handle_general(query, result)

    # ──────────────────────────────────────────────
    #  PHOTO_SEARCH
    # ──────────────────────────────────────────────

    async def _handle_photo_search(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """사진 검색: 키워드 임베딩 + 메타데이터 필터 → 사진 리스트 반환."""

        # 검색 쿼리 구성: 키워드가 있으면 키워드 중심, 없으면 원본 쿼리
        search_text = " ".join(result.keywords) if result.keywords else query
        query_embedding = embed_query(search_text)

        # 날짜 문자열 → datetime 변환
        date_from = _parse_date(result.date_from)
        date_to = _parse_date(result.date_to)

        conn = get_connection()
        try:
            # 필터 조건이 하나라도 있으면 Hybrid Search
            if result.location or date_from or date_to:
                photos = search_photos_filtered(
                    conn,
                    query_embedding,
                    user_id,
                    limit=20,
                    city=result.location,
                    date_from=date_from,
                    date_to=date_to,
                )
            else:
                photos = search_photos(conn, query_embedding, user_id, limit=20)
        finally:
            conn.close()

        # TODO (Person 3): 검색된 사진 메타데이터를 LLM에 전달하여
        #   "제주도 바다에서 찍은 사진 5장을 찾았어요!" 같은 자연어 응답 생성
        answer_text = f"{len(photos)}장의 사진을 찾았습니다."

        return _build_response(result, answer_text, photos)

    # ──────────────────────────────────────────────
    #  EVENT_RECALL
    # ──────────────────────────────────────────────

    async def _handle_event_recall(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """이벤트 회상: events 테이블 조회 → 관련 사진 수집 → 내러티브 생성."""

        # 벡터 검색으로 관련 사진을 먼저 찾고, event_id 로 그룹핑
        search_text = " ".join(result.keywords) if result.keywords else query
        query_embedding = embed_query(search_text)

        date_from = _parse_date(result.date_from)
        date_to = _parse_date(result.date_to)

        conn = get_connection()
        try:
            photos = search_photos_filtered(
                conn,
                query_embedding,
                user_id,
                limit=30,
                city=result.location,
                date_from=date_from,
                date_to=date_to,
            )
        finally:
            conn.close()

        # event_id 별로 사진 그룹핑
        events_map: dict[int, list] = {}
        for photo in photos:
            eid = photo.get("event_id")
            if eid is not None:
                events_map.setdefault(eid, []).append(photo)

        # TODO (Person 3): 그룹핑된 이벤트별 사진 메타데이터(캡션, 장소, 시간)를
        #   LLM 컨텍스트로 전달하여 "뉴욕 여행에서는 센트럴파크를 갔고..." 같은
        #   내러티브 텍스트 생성
        event_count = len(events_map)
        answer_text = (
            f"{event_count}개의 이벤트에서 {len(photos)}장의 관련 사진을 찾았습니다."
        )

        return _build_response(result, answer_text, photos)

    # ──────────────────────────────────────────────
    #  DIARY
    # ──────────────────────────────────────────────

    async def _handle_diary(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """일기 생성 또는 조회."""

        if result.diary_action == DiaryAction.CREATE:
            # TODO (Person 3): 해당 날짜의 이벤트/사진 조회 → LLM 일기 생성
            #   → diaries 테이블 INSERT
            target_date = result.date_from or "지정되지 않음"
            answer_text = f"{target_date} 일기 생성 기능은 준비 중입니다."
            return _build_response(result, answer_text, [])

        # diary_action == RETRIEVE (또는 None → 기본 조회)
        # TODO (Person 3): diaries 테이블에서 date_from~date_to 범위 조회
        target_date = result.date_from or "지정되지 않음"
        answer_text = f"{target_date} 일기 조회 기능은 준비 중입니다."
        return _build_response(result, answer_text, [])

    # ──────────────────────────────────────────────
    #  GENERAL
    # ──────────────────────────────────────────────

    async def _handle_general(
        self, query: str, result: RouteResult,
    ) -> dict[str, Any]:
        """일반 대화 / 범위 밖 질문."""

        # TODO (Person 3): LLM 에게 직접 응답 생성 요청
        #   서비스 소개, 사용법 안내 등 포함
        answer_text = (
            "안녕하세요! 저는 사진 기반 일기 서비스 Pictrace 입니다. "
            "사진 검색, 추억 회상, 일기 작성을 도와드릴 수 있어요."
        )
        return _build_response(result, answer_text, [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  헬퍼 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_date(date_str: str | None) -> datetime | None:
    """YYYY-MM-DD 문자열을 datetime 으로 변환. 실패 시 None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.warning("날짜 파싱 실패: %s", date_str)
        return None


def _build_response(
    result: RouteResult, answer: str, photos: list,
) -> dict[str, Any]:
    """통일된 API 응답 포맷을 구성한다."""
    return {
        "intent": result.intent.value,
        "params": {
            "keywords": result.keywords,
            "location": result.location,
            "date_from": result.date_from,
            "date_to": result.date_to,
            "diary_action": (
                result.diary_action.value if result.diary_action else None
            ),
        },
        "answer": answer,
        "photos": photos,
    }


# 모듈 수준 싱글턴
engine = RAGEngine()
