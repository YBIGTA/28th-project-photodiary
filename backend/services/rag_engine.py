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
from backend.services.llm import generate_response
from db.crud import (
    search_photos, search_photos_filtered,
    list_events_by_date_range, list_photos_by_event,
    insert_diary, get_diary, list_diaries, list_photos,
)
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

        # LLM 자연어 응답 생성
        answer_text = await self._generate_photo_search_answer(query, photos)

        return _build_response(result, answer_text, photos)

    async def _generate_photo_search_answer(self, query: str, photos: list) -> str:
        """검색된 사진 메타데이터를 기반으로 자연어 응답 생성."""
        if not photos:
            return "조건에 맞는 사진을 찾지 못했어요."

        photo_summaries = []
        for p in photos[:10]:
            parts = []
            if p.get("city") or p.get("district"):
                loc = " ".join(filter(None, [p.get("city"), p.get("district")]))
                parts.append(f"장소: {loc}")
            if p.get("taken_at"):
                parts.append(f"촬영일: {str(p['taken_at'])[:10]}")
            if p.get("caption"):
                parts.append(f"캡션: {p['caption']}")
            photo_summaries.append(" / ".join(parts) if parts else f"사진 ID {p['id']}")

        context = "\n".join(f"- {s}" for s in photo_summaries)
        system = (
            "당신은 사진 일기 서비스 Pictrace의 어시스턴트입니다. "
            "검색된 사진 정보를 바탕으로 사용자에게 친근하고 간결하게 답변하세요. "
            "2-3문장 이내로 답변하세요."
        )
        user_content = f"사용자 질문: {query}\n\n검색된 사진 {len(photos)}장:\n{context}"

        answer = await generate_response(system, user_content)
        return answer or f"{len(photos)}장의 사진을 찾았습니다."

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

        # LLM 내러티브 생성
        answer_text = await self._generate_event_narrative(query, events_map, photos)

        return _build_response(result, answer_text, photos)

    async def _generate_event_narrative(
        self, query: str, events_map: dict[int, list], all_photos: list,
    ) -> str:
        """이벤트별 그룹핑된 사진 정보를 바탕으로 내러티브 텍스트 생성."""
        if not all_photos:
            return "관련된 사진이나 이벤트를 찾지 못했어요."

        event_summaries = []
        for eid, photos in events_map.items():
            locations = set()
            dates = set()
            captions = []
            for p in photos:
                if p.get("city") or p.get("district"):
                    locations.add(" ".join(filter(None, [p.get("city"), p.get("district")])))
                if p.get("taken_at"):
                    dates.add(str(p["taken_at"])[:10])
                if p.get("caption"):
                    captions.append(p["caption"])

            summary = f"이벤트 {eid}: "
            if locations:
                summary += f"장소={', '.join(locations)} "
            if dates:
                summary += f"날짜={', '.join(sorted(dates))} "
            if captions:
                summary += f"캡션=[{', '.join(captions[:3])}]"
            event_summaries.append(summary)

        context = "\n".join(f"- {s}" for s in event_summaries)
        system = (
            "당신은 사진 일기 서비스 Pictrace의 어시스턴트입니다. "
            "사용자의 과거 이벤트 정보를 바탕으로, 추억을 회상하듯 따뜻하고 생생하게 이야기를 들려주세요. "
            "3-5문장 이내로 답변하세요."
        )
        user_content = (
            f"사용자 질문: {query}\n\n"
            f"관련 이벤트 {len(events_map)}개, 총 사진 {len(all_photos)}장:\n{context}"
        )

        answer = await generate_response(system, user_content)
        return answer or f"{len(events_map)}개의 이벤트에서 {len(all_photos)}장의 관련 사진을 찾았습니다."

    # ──────────────────────────────────────────────
    #  DIARY
    # ──────────────────────────────────────────────

    async def _handle_diary(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """일기 생성 또는 조회."""

        if result.diary_action == DiaryAction.CREATE:
            return await self._handle_diary_create(query, user_id, result)

        # diary_action == RETRIEVE (또는 None → 기본 조회)
        return await self._handle_diary_retrieve(user_id, result)

    async def _handle_diary_create(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """날짜의 이벤트/사진 조회 → LLM 일기 생성 → DB 저장."""
        target_date_str = result.date_from
        if not target_date_str:
            return _build_response(result, "어떤 날짜의 일기를 작성할까요? 예: '오늘 일기 써줘'", [])

        target_date = _parse_date(target_date_str)
        date_to = _parse_date(result.date_to) or target_date

        conn = get_connection()
        try:
            # 해당 날짜의 이벤트와 사진 조회
            events = list_events_by_date_range(conn, user_id, target_date, date_to)

            # 이벤트별 사진 수집
            all_photos = []
            for event in events:
                event_photos = list_photos_by_event(conn, event["id"])
                all_photos.extend(event_photos)

            # 이벤트가 없으면 해당 날짜 사진 직접 검색
            if not all_photos:
                all_user_photos = list_photos(conn, user_id, limit=200)
                all_photos = [
                    p for p in all_user_photos
                    if p.get("taken_at") and target_date
                    and str(p["taken_at"])[:10] == target_date_str
                ]

            if not all_photos:
                return _build_response(
                    result,
                    f"{target_date_str}에 해당하는 사진이 없어서 일기를 작성할 수 없어요.",
                    [],
                )

            # LLM으로 일기 생성
            diary_content = await self._generate_diary_content(target_date_str, all_photos)

            if diary_content:
                insert_diary(conn, user_id, target_date_str, diary_content)
                answer_text = f"{target_date_str} 일기를 작성했어요!\n\n{diary_content}"
            else:
                answer_text = "일기 생성에 실패했어요. 다시 시도해 주세요."

        finally:
            conn.close()

        return _build_response(result, answer_text, all_photos[:10])

    async def _generate_diary_content(self, date_str: str, photos: list) -> str:
        """사진 메타데이터를 기반으로 일기 내용 생성."""
        photo_details = []
        for p in photos[:20]:
            parts = []
            if p.get("taken_at"):
                parts.append(f"시간: {str(p['taken_at'])[:16]}")
            loc = " ".join(filter(None, [p.get("city"), p.get("district"), p.get("building")]))
            if loc:
                parts.append(f"장소: {loc}")
            if p.get("caption"):
                parts.append(f"캡션: {p['caption']}")
            photo_details.append(" / ".join(parts))

        context = "\n".join(f"- {d}" for d in photo_details)
        system = (
            "당신은 사진 일기 작성 어시스턴트입니다. "
            "사진의 메타데이터(시간, 장소, 캡션)를 바탕으로 "
            "그날 하루를 생생하게 기록하는 일기를 한국어로 작성하세요. "
            "따뜻하고 개인적인 톤으로, 5-10문장 정도로 작성하세요."
        )
        user_content = f"날짜: {date_str}\n\n사진 정보:\n{context}"

        return await generate_response(system, user_content)

    async def _handle_diary_retrieve(
        self, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """diaries 테이블에서 일기 조회."""
        date_from_str = result.date_from
        date_to_str = result.date_to

        conn = get_connection()
        try:
            if date_from_str and not date_to_str:
                # 특정 날짜 일기 조회
                diary = get_diary(conn, user_id, date_from_str)
                if diary:
                    answer_text = f"**{diary['diary_date']}의 일기**\n\n{diary['content']}"
                else:
                    answer_text = f"{date_from_str}에 작성된 일기가 없어요."
                return _build_response(result, answer_text, [])

            # 범위 조회
            diaries_list = list_diaries(
                conn, user_id,
                date_from=date_from_str,
                date_to=date_to_str,
            )
        finally:
            conn.close()

        if not diaries_list:
            answer_text = "해당 기간에 작성된 일기가 없어요."
        elif len(diaries_list) == 1:
            d = diaries_list[0]
            answer_text = f"**{d['diary_date']}의 일기**\n\n{d['content']}"
        else:
            entries = []
            for d in diaries_list:
                preview = d["content"][:80] + ("..." if len(d["content"]) > 80 else "")
                entries.append(f"**{d['diary_date']}**: {preview}")
            answer_text = f"총 {len(diaries_list)}개의 일기를 찾았어요.\n\n" + "\n\n".join(entries)

        return _build_response(result, answer_text, [])

    # ──────────────────────────────────────────────
    #  GENERAL
    # ──────────────────────────────────────────────

    async def _handle_general(
        self, query: str, result: RouteResult,
    ) -> dict[str, Any]:
        """일반 대화 / 범위 밖 질문."""

        system = (
            "당신은 사진 기반 일기 서비스 Pictrace의 어시스턴트입니다. "
            "사용자의 일반적인 질문에 친근하게 답변하세요. "
            "서비스 관련 질문이면 사진 검색, 추억 회상, 일기 작성 기능을 안내하세요. "
            "2-3문장 이내로 간결하게 답변하세요."
        )

        answer_text = await generate_response(system, query)
        if not answer_text:
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
