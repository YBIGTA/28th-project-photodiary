"""RAG Engine (LLM 답변 생성) 모의 테스트.

DB·OpenAI 실제 호출 없이, mock 을 사용하여 RAGEngine 의 전체 흐름을 검증한다.
sentence_transformers, torch 등 무거운 의존성 없이도 실행 가능하다.

Run: python -m tests.test_rag_engine
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Windows UTF-8 출력 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

# ── 무거운 ML 의존성 mock (sentence_transformers, torch 등 없이 실행) ──
_STUB_EMBEDDING = [0.01] * 768

if "sentence_transformers" not in sys.modules:
    st_mod = types.ModuleType("sentence_transformers")
    st_mod.SentenceTransformer = MagicMock  # type: ignore[attr-defined]
    sys.modules["sentence_transformers"] = st_mod

if "pipeline.core.embedder" not in sys.modules:
    embedder_mod = types.ModuleType("pipeline.core.embedder")
    embedder_mod.embed_query = MagicMock(return_value=_STUB_EMBEDDING)  # type: ignore[attr-defined]
    embedder_mod.embed_photo = MagicMock(return_value=_STUB_EMBEDDING)  # type: ignore[attr-defined]
    sys.modules["pipeline.core.embedder"] = embedder_mod

if "pipeline.utils.geocoder" not in sys.modules:
    geo_mod = types.ModuleType("pipeline.utils.geocoder")
    geo_mod.PlaceInfo = MagicMock  # type: ignore[attr-defined]
    sys.modules["pipeline.utils.geocoder"] = geo_mod


def sep(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
#  테스트용 더미 데이터
# ============================================================

DUMMY_PHOTOS = [
    {
        "id": 1,
        "file_path": "photos/jeju_beach.jpg",
        "taken_at": datetime(2025, 7, 15, 14, 30),
        "state": "제주특별자치도",
        "city": "제주시",
        "district": "애월읍",
        "road": "협재로",
        "building": None,
        "full_address": "제주특별자치도 제주시 애월읍 협재로",
        "caption": "푸른 바다와 하얀 모래사장이 보이는 해변 풍경",
        "event_id": 1,
        "similarity": 0.92,
    },
    {
        "id": 2,
        "file_path": "photos/jeju_cafe.jpg",
        "taken_at": datetime(2025, 7, 15, 16, 0),
        "state": "제주특별자치도",
        "city": "제주시",
        "district": "애월읍",
        "road": None,
        "building": "카페 델문도",
        "full_address": "제주특별자치도 제주시 애월읍 카페 델문도",
        "caption": "오션뷰 카페에서 아이스 아메리카노를 마시는 모습",
        "event_id": 1,
        "similarity": 0.88,
    },
    {
        "id": 3,
        "file_path": "photos/seoul_park.jpg",
        "taken_at": datetime(2025, 8, 20, 10, 0),
        "state": "서울특별시",
        "city": None,
        "district": "마포구",
        "road": "월드컵로",
        "building": None,
        "full_address": "서울특별시 마포구 월드컵로",
        "caption": "공원에서 산책하는 사람들과 반려견",
        "event_id": 2,
        "similarity": 0.75,
    },
]

DUMMY_KEYWORDS_MAP = {
    1: ["바다", "해변", "모래", "파도", "하늘"],
    2: ["카페", "커피", "아메리카노", "오션뷰"],
    3: ["공원", "산책", "강아지", "나무", "잔디"],
}

DUMMY_EMBEDDING = [0.01] * 768

MOCK_LLM_RESPONSES = {
    "photo_search": "제주도 애월에서 찍은 사진 2장을 찾았어요! 2025년 7월에 협재 해변에서 바다를 즐기고, 근처 오션뷰 카페에서 여유로운 시간을 보내셨네요.",
    "event_recall": "제주도 여행이 정말 즐거웠던 것 같아요! 7월 15일에 협재 해변에서 푸른 바다를 감상하고, 근처 카페 델문도에서 시원한 아메리카노를 마시며 오션뷰를 즐기셨네요. 바다와 카페, 완벽한 제주 힐링 코스였어요!",
    "diary_create": "오늘은 제주도에서 멋진 하루를 보냈다. 오후에 협재 해변에 갔는데, 에메랄드빛 바다가 정말 아름다웠다. 모래사장을 걸으며 파도 소리를 들었다. 그 후 근처 카페 델문도에 들러 오션뷰를 보며 아이스 아메리카노를 마셨다. 바다를 바라보며 마시는 커피 한 잔의 여유가 이렇게 좋을 줄이야. 제주도의 자연과 함께한 하루가 참 행복했다.",
    "general": "안녕하세요! Pictrace와 함께 추억을 찾아볼까요? 사진 검색, 추억 회상, 일기 작성 등을 도와드릴 수 있어요.",
}


# ============================================================
#  헬퍼 함수 테스트
# ============================================================

def test_resolve_location():
    sep("1단계: _resolve_location() 테스트")

    from backend.services.rag_engine import _resolve_location

    cases = [
        ("제주도", ("제주도", None, None), "도 → state"),
        ("서울특별시", ("서울특별시", None, None), "특별시 → state"),
        ("부산광역시", ("부산광역시", None, None), "광역시 → state"),
        ("제주특별자치도", ("제주특별자치도", None, None), "특별자치도 → state"),
        ("마포구", (None, None, "마포구"), "구 → district"),
        ("성수동", (None, None, "성수동"), "동 → district"),
        ("애월읍", (None, None, "애월읍"), "읍 → district"),
        ("부산", (None, "부산", None), "기타 → city"),
        ("제주", (None, "제주", None), "기타 → city"),
        ("합정", (None, "합정", None), "기타 → city"),
        (None, (None, None, None), "None 입력"),
    ]

    all_ok = True
    for location, expected, desc in cases:
        result = _resolve_location(location)
        ok = result == expected
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] '{location}' → {result}  ({desc})")
        if not ok:
            print(f"         기대값: {expected}")
            all_ok = False

    return all_ok


def test_parse_date():
    sep("2단계: _parse_date() 테스트")

    from backend.services.rag_engine import _parse_date

    cases = [
        ("2025-07-15", datetime(2025, 7, 15), "정상 날짜"),
        ("2025-01-01", datetime(2025, 1, 1), "연초"),
        ("2025-12-31", datetime(2025, 12, 31), "연말"),
        (None, None, "None 입력"),
        ("", None, "빈 문자열"),
        ("invalid", None, "잘못된 형식"),
        ("2025/07/15", None, "슬래시 형식"),
    ]

    all_ok = True
    for date_str, expected, desc in cases:
        result = _parse_date(date_str)
        ok = result == expected
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] '{date_str}' → {result}  ({desc})")
        if not ok:
            print(f"         기대값: {expected}")
            all_ok = False

    return all_ok


def test_photos_to_context():
    sep("3단계: _photos_to_context() 테스트")

    from backend.services.rag_engine import RAGEngine

    engine = RAGEngine()
    context = engine._photos_to_context(DUMMY_PHOTOS[:2], DUMMY_KEYWORDS_MAP)

    print(f"  생성된 컨텍스트:\n")
    for line in context.split("\n"):
        print(f"    {line}")

    checks = [
        ("[사진 1]" in context, "사진 번호 포함"),
        ("[사진 2]" in context, "두 번째 사진 포함"),
        ("제주시" in context, "장소 정보 포함"),
        ("바다" in context, "키워드 포함"),
        ("푸른 바다" in context, "캡션 포함"),
        ("2025" in context, "날짜 포함"),
    ]

    all_ok = True
    print()
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    return all_ok


def test_build_response():
    sep("4단계: _build_response() 테스트")

    from backend.services.rag_engine import _build_response
    from backend.services.agent_router import RouteResult, Intent

    result = RouteResult(
        intent=Intent.PHOTO_SEARCH,
        keywords=["바다"],
        location="제주도",
        date_from="2025-07-01",
        date_to="2025-07-31",
    )

    response = _build_response(result, "테스트 응답입니다.", DUMMY_PHOTOS[:1])

    checks = [
        (response["intent"] == "PHOTO_SEARCH", "intent 값"),
        (response["answer"] == "테스트 응답입니다.", "answer 값"),
        (len(response["photos"]) == 1, "photos 개수"),
        (response["params"]["keywords"] == ["바다"], "params.keywords"),
        (response["params"]["location"] == "제주도", "params.location"),
        (response["params"]["date_from"] == "2025-07-01", "params.date_from"),
        (response["params"]["diary_action"] is None, "params.diary_action (None)"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    return all_ok


# ============================================================
#  RAGEngine 핸들러 통합 테스트 (mock)
# ============================================================

def _make_mock_openai(response_text: str):
    """AsyncOpenAI mock 생성."""
    mock_choice = MagicMock()
    mock_choice.message.content = response_text

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


def _make_mock_conn(photos=None, diary=None):
    """psycopg2 connection mock 생성."""
    mock_conn = MagicMock()
    mock_conn.close = MagicMock()
    return mock_conn


@patch("backend.services.rag_engine.get_connection")
@patch("backend.services.rag_engine.embed_query")
@patch("backend.services.rag_engine.search_photos_filtered")
@patch("backend.services.rag_engine.search_photos")
@patch("backend.services.rag_engine.get_photo_keywords_batch")
@patch("backend.services.rag_engine.router")
def test_photo_search(mock_router, mock_keywords, mock_search,
                      mock_search_filtered, mock_embed, mock_conn):
    sep("5단계: PHOTO_SEARCH 핸들러 테스트")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.PHOTO_SEARCH,
        keywords=["바다"],
        location="제주도",
        date_from="2025-07-01",
        date_to="2025-07-31",
    ))
    mock_embed.return_value = DUMMY_EMBEDDING
    mock_conn.return_value = _make_mock_conn()
    mock_search_filtered.return_value = DUMMY_PHOTOS[:2]
    mock_keywords.return_value = DUMMY_KEYWORDS_MAP

    engine = RAGEngine()
    engine._client = _make_mock_openai(MOCK_LLM_RESPONSES["photo_search"])

    response = asyncio.run(engine.answer("제주도 바다 사진 보여줘", user_id=1))

    checks = [
        (response["intent"] == "PHOTO_SEARCH", "intent = PHOTO_SEARCH"),
        (len(response["photos"]) == 2, f"photos 2장 반환 (실제: {len(response['photos'])})"),
        ("제주" in response["answer"], "응답에 '제주' 포함"),
        ("해변" in response["answer"] or "바다" in response["answer"], "응답에 바다/해변 언급"),
        (response["params"]["location"] == "제주도", "params.location = 제주도"),
        (mock_search_filtered.called, "search_photos_filtered 호출됨"),
        (engine._client.chat.completions.create.called, "LLM 호출됨"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    print(f"\n  LLM 응답: {response['answer'][:80]}...")
    return all_ok


@patch("backend.services.rag_engine.get_connection")
@patch("backend.services.rag_engine.embed_query")
@patch("backend.services.rag_engine.search_photos_filtered")
@patch("backend.services.rag_engine.get_photo_keywords_batch")
@patch("backend.services.rag_engine.router")
def test_event_recall(mock_router, mock_keywords, mock_search_filtered,
                      mock_embed, mock_conn):
    sep("6단계: EVENT_RECALL 핸들러 테스트")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.EVENT_RECALL,
        keywords=["여행"],
        location="제주도",
    ))
    mock_embed.return_value = DUMMY_EMBEDDING
    mock_conn.return_value = _make_mock_conn()
    mock_search_filtered.return_value = DUMMY_PHOTOS[:2]
    mock_keywords.return_value = DUMMY_KEYWORDS_MAP

    engine = RAGEngine()
    engine._client = _make_mock_openai(MOCK_LLM_RESPONSES["event_recall"])

    response = asyncio.run(engine.answer("제주도 여행 어땠어?", user_id=1))

    checks = [
        (response["intent"] == "EVENT_RECALL", "intent = EVENT_RECALL"),
        (len(response["photos"]) == 2, f"photos 2장 (실제: {len(response['photos'])})"),
        ("제주" in response["answer"], "응답에 '제주' 포함"),
        ("카페" in response["answer"] or "해변" in response["answer"], "장소 언급"),
        (engine._client.chat.completions.create.called, "LLM 호출됨"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    print(f"\n  LLM 응답: {response['answer'][:80]}...")
    return all_ok


@patch("backend.services.rag_engine.get_connection")
@patch("backend.services.rag_engine.embed_query")
@patch("backend.services.rag_engine.search_photos_filtered")
@patch("backend.services.rag_engine.get_photo_keywords_batch")
@patch("backend.services.rag_engine.insert_diary")
@patch("backend.services.rag_engine.router")
def test_diary_create(mock_router, mock_insert_diary, mock_keywords,
                      mock_search_filtered, mock_embed, mock_conn):
    sep("7단계: DIARY CREATE 핸들러 테스트")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent, DiaryAction

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.DIARY,
        keywords=[],
        date_from="2025-07-15",
        date_to="2025-07-15",
        diary_action=DiaryAction.CREATE,
    ))
    mock_embed.return_value = DUMMY_EMBEDDING
    mock_conn.return_value = _make_mock_conn()
    mock_search_filtered.return_value = DUMMY_PHOTOS[:2]
    mock_keywords.return_value = DUMMY_KEYWORDS_MAP
    mock_insert_diary.return_value = 1

    engine = RAGEngine()
    engine._client = _make_mock_openai(MOCK_LLM_RESPONSES["diary_create"])

    response = asyncio.run(engine.answer("오늘 일기 써줘", user_id=1))

    checks = [
        (response["intent"] == "DIARY", "intent = DIARY"),
        (response["params"]["diary_action"] == "create", "diary_action = create"),
        ("일기를 작성했어요" in response["answer"], "일기 작성 완료 메시지"),
        ("제주" in response["answer"] or "해변" in response["answer"], "일기 내용에 장소 포함"),
        (mock_insert_diary.called, "insert_diary 호출됨"),
        (engine._client.chat.completions.create.called, "LLM 호출됨"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    print(f"\n  LLM 응답: {response['answer'][:80]}...")
    return all_ok


@patch("backend.services.rag_engine.get_connection")
@patch("backend.services.rag_engine.get_diary")
@patch("backend.services.rag_engine.router")
def test_diary_retrieve(mock_router, mock_get_diary, mock_conn):
    sep("8단계: DIARY RETRIEVE 핸들러 테스트")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent, DiaryAction

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.DIARY,
        keywords=[],
        date_from="2025-07-15",
        date_to="2025-07-15",
        diary_action=DiaryAction.RETRIEVE,
    ))
    mock_conn.return_value = _make_mock_conn()
    mock_get_diary.return_value = {
        "id": 1,
        "user_id": 1,
        "diary_date": "2025-07-15",
        "content": "오늘은 제주도에서 멋진 하루를 보냈다. 협재 해변에서 바다를 보고...",
        "created_at": datetime(2025, 7, 15, 23, 0),
    }

    engine = RAGEngine()

    response = asyncio.run(engine.answer("7월 15일 일기 보여줘", user_id=1))

    checks = [
        (response["intent"] == "DIARY", "intent = DIARY"),
        (response["params"]["diary_action"] == "retrieve", "diary_action = retrieve"),
        ("2025-07-15" in response["answer"], "날짜 포함"),
        ("제주" in response["answer"] or "해변" in response["answer"], "일기 내용 포함"),
        (mock_get_diary.called, "get_diary 호출됨"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    print(f"\n  응답: {response['answer'][:80]}...")
    return all_ok


@patch("backend.services.rag_engine.router")
def test_general(mock_router):
    sep("9단계: GENERAL 핸들러 테스트")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.GENERAL,
        keywords=[],
    ))

    engine = RAGEngine()
    engine._client = _make_mock_openai(MOCK_LLM_RESPONSES["general"])

    response = asyncio.run(engine.answer("안녕하세요!", user_id=1))

    checks = [
        (response["intent"] == "GENERAL", "intent = GENERAL"),
        (len(response["photos"]) == 0, "photos 비어있음"),
        (len(response["answer"]) > 0, "응답이 비어있지 않음"),
        ("Pictrace" in response["answer"] or "사진" in response["answer"], "서비스 관련 내용"),
        (engine._client.chat.completions.create.called, "LLM 호출됨"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    print(f"\n  LLM 응답: {response['answer'][:80]}...")
    return all_ok


# ============================================================
#  엣지 케이스 테스트
# ============================================================

@patch("backend.services.rag_engine.get_connection")
@patch("backend.services.rag_engine.embed_query")
@patch("backend.services.rag_engine.search_photos_filtered")
@patch("backend.services.rag_engine.search_photos")
@patch("backend.services.rag_engine.router")
def test_empty_results(mock_router, mock_search, mock_search_filtered,
                       mock_embed, mock_conn):
    sep("10단계: 검색 결과 없음 엣지 케이스")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.PHOTO_SEARCH,
        keywords=["유니콘"],
        location="화성",
    ))
    mock_embed.return_value = DUMMY_EMBEDDING
    mock_conn.return_value = _make_mock_conn()
    mock_search_filtered.return_value = []

    engine = RAGEngine()

    response = asyncio.run(engine.answer("화성에서 유니콘 사진 보여줘", user_id=1))

    checks = [
        (response["intent"] == "PHOTO_SEARCH", "intent = PHOTO_SEARCH"),
        (len(response["photos"]) == 0, "photos 비어있음"),
        ("찾지 못했" in response["answer"], "검색 실패 메시지"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            all_ok = False

    return all_ok


@patch("backend.services.rag_engine.get_connection")
@patch("backend.services.rag_engine.embed_query")
@patch("backend.services.rag_engine.search_photos_filtered")
@patch("backend.services.rag_engine.get_photo_keywords_batch")
@patch("backend.services.rag_engine.router")
def test_llm_failure_fallback(mock_router, mock_keywords, mock_search_filtered,
                              mock_embed, mock_conn):
    sep("11단계: LLM 호출 실패 시 폴백 테스트")

    from backend.services.rag_engine import RAGEngine
    from backend.services.agent_router import RouteResult, Intent

    mock_router.classify = AsyncMock(return_value=RouteResult(
        intent=Intent.PHOTO_SEARCH,
        keywords=["바다"],
    ))
    mock_embed.return_value = DUMMY_EMBEDDING
    mock_conn.return_value = _make_mock_conn()
    mock_search_filtered.return_value = []
    from backend.services.rag_engine import search_photos as _sp
    with patch("backend.services.rag_engine.search_photos", return_value=DUMMY_PHOTOS[:2]):
        mock_keywords.return_value = DUMMY_KEYWORDS_MAP

        engine = RAGEngine()
        # LLM이 빈 문자열 반환 (실패 시뮬레이션)
        engine._client = _make_mock_openai("")

        response = asyncio.run(engine.answer("바다 사진 보여줘", user_id=1))

    checks = [
        (len(response["answer"]) > 0, "폴백 응답 존재"),
        ("2장" in response["answer"], "사진 수 폴백 메시지"),
    ]

    all_ok = True
    for condition, desc in checks:
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {desc}")
        if not condition:
            print(f"         실제 응답: {response['answer']}")
            all_ok = False

    return all_ok


# ============================================================
#  메인
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("  RAG Engine (LLM 답변 생성) 모의 테스트")
    print("=" * 60)

    results = {}

    # 헬퍼 함수 테스트
    results["resolve_location"] = test_resolve_location()
    results["parse_date"] = test_parse_date()
    results["photos_to_context"] = test_photos_to_context()
    results["build_response"] = test_build_response()

    # 핸들러 통합 테스트
    results["photo_search"] = test_photo_search()
    results["event_recall"] = test_event_recall()
    results["diary_create"] = test_diary_create()
    results["diary_retrieve"] = test_diary_retrieve()
    results["general"] = test_general()

    # 엣지 케이스
    results["empty_results"] = test_empty_results()
    results["llm_fallback"] = test_llm_failure_fallback()

    # 결과 요약
    sep("테스트 결과 요약")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  {passed}/{total} 통과")

    if passed == total:
        print("\n  모든 테스트 통과!")
    else:
        print("\n  일부 테스트 실패 — 위 로그를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
