from __future__ import annotations
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

from typing import Optional

import logging
import os
from datetime import datetime, date
from typing import Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from backend.services.agent_router import router, Intent, DiaryAction, RouteResult
from db.crud import (
    search_photos,
    search_photos_filtered,
    get_photo_keywords_batch,
    insert_diary,
    get_diary,
    get_diaries_by_range,
)
from db.schema import get_connection
from pipeline.core.embedder import embed_query

load_dotenv()

logger = logging.getLogger(__name__)


class RAGEngine:
    """Router 결과를 받아 검색·생성 파이프라인을 실행하는 오케스트레이터."""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self.model = "gpt-4o"

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    async def _call_llm(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.7,
    ) -> str:
        """OpenAI Chat Completion 호출 공용 헬퍼."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("LLM 호출 실패: %s", e)
            return ""

    def _photos_to_context(
        self, photos: list[dict], keywords_map: dict[int, list[str]],
    ) -> str:
        """사진 메타데이터를 LLM 컨텍스트 문자열로 변환."""
        lines: list[str] = []
        for i, photo in enumerate(photos, 1):
            parts = [f"[사진 {i}]"]
            if photo.get("taken_at"):
                parts.append(f"날짜: {photo['taken_at']}")
            location_parts = [
                v for k in ("city", "district", "building", "road")
                if (v := photo.get(k))
            ]
            if location_parts:
                parts.append(f"장소: {' '.join(location_parts)}")
            if photo.get("caption"):
                parts.append(f"설명: {photo['caption']}")
            kws = keywords_map.get(photo.get("id"), [])
            if kws:
                parts.append(f"키워드: {', '.join(kws[:8])}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

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
        
        if date_to:
            date_to = date_to.replace(hour=23, minute=59, second=59)

        conn = get_connection()
        try:
            # 필터 조건이 하나라도 있으면 Hybrid Search
            state, city, district = _resolve_location(result.location)
            if state or city or district or date_from or date_to:
                photos = search_photos_filtered(
                    conn,
                    query_embedding,
                    user_id,
                    limit=20,
                    state=state,
                    city=city,
                    district=district,
                    date_from=date_from,
                    date_to=date_to,
                )
            else:
                photos = search_photos(conn, query_embedding, user_id, limit=20)
        finally:
            conn.close()

        if not photos:
            return _build_response(result, "조건에 맞는 사진을 찾지 못했어요.", [])

        photo_ids = [p["id"] for p in photos]
        conn2 = get_connection()
        try:
            keywords_map = get_photo_keywords_batch(conn2, photo_ids)
        finally:
            conn2.close()

        context = self._photos_to_context(photos, keywords_map)
        system_prompt = (
            "당신은 사진 앨범 도우미 'Pictrace'입니다. "
            "아래 검색된 사진 정보를 참고하여 사용자에게 친근하고 따뜻한 톤으로 "
            "검색 결과를 2~3문장으로 요약해주세요. "
            "사진 수, 주요 장소, 시기 등을 자연스럽게 언급하세요."
        )
        user_content = (
            f"사용자 질문: {query}\n\n"
            f"검색된 사진 {len(photos)}장:\n{context}"
        )
        answer_text = await self._call_llm(system_prompt, user_content)
        if not answer_text:
            answer_text = f"{len(photos)}장의 사진을 찾았습니다."

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
        
        if date_to:
            date_to = date_to.replace(hour=23, minute=59, second=59)

        conn = get_connection()
        try:
            state, city, district = _resolve_location(result.location)
            photos = search_photos_filtered(
                conn,
                query_embedding,
                user_id,
                limit=30,
                state=state,
                city=city,
                district=district,
                date_from=date_from,
                date_to=date_to,
            )
        finally:
            conn.close()

        if not photos:
            return _build_response(
                result, "해당 기간/장소의 기억을 찾지 못했어요.", [],
            )

        photo_ids = [p["id"] for p in photos]
        conn2 = get_connection()
        try:
            keywords_map = get_photo_keywords_batch(conn2, photo_ids)
        finally:
            conn2.close()

        # event_id 별로 사진 그룹핑
        events_map: dict[int, list] = {}
        ungrouped: list[dict] = []
        for photo in photos:
            eid = photo.get("event_id")
            if eid is not None:
                events_map.setdefault(eid, []).append(photo)
            else:
                ungrouped.append(photo)

        # 이벤트별 컨텍스트 구성
        event_context_parts: list[str] = []
        for eid, event_photos in events_map.items():
            sorted_photos = sorted(
                event_photos,
                key=lambda p: p.get("taken_at") or "",
            )
            ctx = self._photos_to_context(sorted_photos, keywords_map)
            event_context_parts.append(f"── 이벤트 {eid} ({len(sorted_photos)}장) ──\n{ctx}")
        if ungrouped:
            ctx = self._photos_to_context(ungrouped, keywords_map)
            event_context_parts.append(f"── 기타 ({len(ungrouped)}장) ──\n{ctx}")

        context = "\n\n".join(event_context_parts)
        system_prompt = (
            "당신은 사용자의 추억을 이야기해주는 'Pictrace'입니다. "
            "아래 이벤트별 사진 기록을 바탕으로, 사용자가 그때 어떤 경험을 했는지 "
            "따뜻한 회상 형태로 이야기해주세요. "
            "시간 순서대로, 장소·활동·분위기를 자연스럽게 엮어서 3~5문장으로 답하세요."
        )
        user_content = (
            f"사용자 질문: {query}\n\n"
            f"관련 사진 기록:\n{context}"
        )
        answer_text = await self._call_llm(system_prompt, user_content)
        if not answer_text:
            event_count = len(events_map)
            answer_text = (
                f"{event_count}개의 이벤트에서 "
                f"{len(photos)}장의 관련 사진을 찾았습니다."
            )

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
            return await self._create_diary(query, user_id, result)

        return await self._retrieve_diary(query, user_id, result)

    async def _create_diary(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """해당 날짜의 사진을 조회하여 LLM으로 일기를 생성하고 DB에 저장."""
        target_date_str = result.date_from or date.today().isoformat()
        target_date = _parse_date(target_date_str)
        if not target_date:
            return _build_response(result, "날짜를 인식하지 못했어요.", [])

        # 해당 날짜의 사진 조회 (벡터 검색 없이 날짜 필터만)
        dummy_embedding = embed_query("일기")
        conn = get_connection()
        try:
            photos = search_photos_filtered(
                conn,
                dummy_embedding,
                user_id,
                limit=30,
                date_from=target_date,
                date_to=target_date.replace(hour=23, minute=59, second=59),
            )
        finally:
            conn.close()

        if not photos:
            return _build_response(
                result,
                f"{target_date_str}에 찍은 사진이 없어서 일기를 쓸 수 없어요.",
                [],
            )

        photo_ids = [p["id"] for p in photos]
        conn2 = get_connection()
        try:
            keywords_map = get_photo_keywords_batch(conn2, photo_ids)
        finally:
            conn2.close()

        context = self._photos_to_context(photos, keywords_map)
        system_prompt = (
            "당신은 사용자의 하루를 사진 기록으로 일기를 써주는 'Pictrace'입니다. "
            "아래 사진 정보를 바탕으로 따뜻하고 개인적인 톤의 일기를 작성하세요. "
            "시간 순서대로 하루를 되돌아보는 형식으로, 5~10문장 정도로 써주세요. "
            "일기 본문만 출력하세요."
        )
        user_content = (
            f"날짜: {target_date_str}\n"
            f"사진 {len(photos)}장:\n{context}"
        )
        diary_content = await self._call_llm(system_prompt, user_content)
        if not diary_content:
            return _build_response(
                result, "일기 생성 중 오류가 발생했어요.", photos,
            )

        conn3 = get_connection()
        try:
            insert_diary(conn3, user_id, target_date.date(), diary_content)
        finally:
            conn3.close()

        answer_text = f"{target_date_str} 일기를 작성했어요!\n\n{diary_content}"
        return _build_response(result, answer_text, photos)

    async def _retrieve_diary(
        self, query: str, user_id: int, result: RouteResult,
    ) -> dict[str, Any]:
        """DB에서 일기를 조회하여 반환."""
        date_from = _parse_date(result.date_from)
        date_to = _parse_date(result.date_to)

        if not date_from:
            return _build_response(
                result, "어떤 날짜의 일기를 보고 싶으신지 알려주세요!", [],
            )

        conn = get_connection()
        try:
            if date_to and date_from != date_to:
                diaries = get_diaries_by_range(
                    conn, user_id, date_from.date(), date_to.date(),
                )
            else:
                single = get_diary(conn, user_id, date_from.date())
                diaries = [single] if single else []
        finally:
            conn.close()

        if not diaries:
            return _build_response(
                result,
                f"해당 기간에 작성된 일기가 없어요. '일기 써줘'라고 하면 만들어 드릴게요!",
                [],
            )

        parts = []
        for d in diaries:
            parts.append(f"📅 {d['diary_date']}\n{d['content']}")
        answer_text = "\n\n".join(parts)
        return _build_response(result, answer_text, [])

    # ──────────────────────────────────────────────
    #  GENERAL
    # ──────────────────────────────────────────────

    async def _handle_general(
        self, query: str, result: RouteResult,
    ) -> dict[str, Any]:
        """일반 대화 / 범위 밖 질문."""

        system_prompt = (
            "당신은 사진 기반 일기 서비스 'Pictrace'의 챗봇입니다. "
            "사용자와 친근하게 대화하세요. 서비스 기능(사진 검색, 추억 회상, "
            "일기 작성/조회)을 안내할 수 있고, 범위 밖 질문에는 정중하게 "
            "서비스 기능으로 안내해주세요. 2~3문장으로 답하세요."
        )
        answer_text = await self._call_llm(system_prompt, query)
        if not answer_text:
            answer_text = (
                "안녕하세요! 저는 사진 기반 일기 서비스 Pictrace입니다. "
                "사진 검색, 추억 회상, 일기 작성을 도와드릴 수 있어요."
            )
        return _build_response(result, answer_text, [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  헬퍼 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_STATE_SUFFIXES = ("도", "특별시", "광역시", "특별자치시", "특별자치도")
_DISTRICT_SUFFIXES = ("구", "동", "읍", "면", "리", "로", "길")


def _resolve_location(
    location: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """location 문자열을 (state, city, district) 로 분류.

    광역시/도 접미사로 끝나면 state, 한국 행정구역 접미사(구·동·읍·면 등)로
    끝나면 district, 그 외에는 city 로 판단한다.
    """
    if not location:
        return None, None, None
    if location.endswith(_STATE_SUFFIXES):
        return location, None, None
    if location.endswith(_DISTRICT_SUFFIXES):
        return None, None, location
    return None, location, None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
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
