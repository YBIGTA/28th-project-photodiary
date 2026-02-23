from __future__ import annotations
"""
agent_router.py
===============
사용자 질문의 의도(Intent)를 분류하고, 후속 에이전트가 필요로 하는
파라미터를 구조화된 JSON 으로 추출하는 LLM 기반 라우터.

Intent Categories
-----------------
- PHOTO_SEARCH  : 사진을 찾아서 보여달라는 요청
- EVENT_RECALL  : 과거 경험을 회상·요약해달라는 요청
- DIARY         : 일기 생성 또는 조회 요청
- GENERAL       : 일반 대화, 서비스 범위 밖 질문
"""


import json
import logging
import os
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  카테고리 & 출력 스키마
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Intent(str, Enum):
    PHOTO_SEARCH = "PHOTO_SEARCH"
    EVENT_RECALL = "EVENT_RECALL"
    DIARY = "DIARY"
    GENERAL = "GENERAL"


class DiaryAction(str, Enum):
    CREATE = "create"
    RETRIEVE = "retrieve"


class RouteResult(BaseModel):
    """Router 의 분류 + 파라미터 추출 결과.

    Attributes
    ----------
    intent : Intent
        분류된 사용자 의도.
    keywords : list[str]
        검색에 사용할 내용 키워드 (장소·시간 표현 제외).
    location : Optional[str]
        사용자가 언급한 장소명 (예: "부산", "성수동").
    date_from : Optional[str]
        시작 날짜 (YYYY-MM-DD). DIARY 일 때는 대상 날짜.
    date_to : Optional[str]
        종료 날짜 (YYYY-MM-DD).
    diary_action : Optional[DiaryAction]
        DIARY 전용 — create(생성) / retrieve(조회).
    """
    intent: Intent
    keywords: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    diary_action: Optional[DiaryAction] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  System Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT = """\
당신은 사진 기반 자동 일기 서비스 "Pictrace"의 의도 분류 AI입니다.
사용자의 한국어 질문을 분석하여 4가지 카테고리 중 **정확히 하나**로 분류하고,
후속 처리에 필요한 파라미터를 추출하세요.
반드시 JSON 객체 하나만 출력하세요. 설명·마크다운·부가 텍스트는 절대 쓰지 마세요.

오늘 날짜: {today}

────────────────────────────
1. PHOTO_SEARCH — 사진 검색
────────────────────────────
사용자가 특정 조건의 **사진을 직접 보고 싶을 때**.
핵심 단서: "사진 보여줘", "사진 찾아줘", "사진 있어?", "~한 사진"

────────────────────────────
2. EVENT_RECALL — 이벤트 회상
────────────────────────────
사용자가 과거 경험을 **되돌아보고 이야기를 듣고 싶을 때**.
핵심 단서: "어땠어?", "뭐했지?", "기억나?", "얘기해줘", "알려줘"

────────────────────────────
3. DIARY — 일기
────────────────────────────
사용자가 **일기**를 써달라고 하거나, 기존 일기를 보여달라고 할 때.
핵심 단서: "일기", "다이어리"
· 생성 → diary_action = "create"  (써줘, 만들어줘, 작성해줘)
· 조회 → diary_action = "retrieve" (보여줘, 보고 싶어, 읽어줘)

────────────────────────────
4. GENERAL — 일반 대화
────────────────────────────
위 3가지에 해당하지 않는 일반 대화, 인사, 서비스 범위 밖 질문.

━━━━━━━━━━━━━━━━━━━━━━━━━━
★ PHOTO_SEARCH vs EVENT_RECALL 구분 가이드
━━━━━━━━━━━━━━━━━━━━━━━━━━
| 질문                        | Intent        | 이유                |
|-----------------------------|---------------|---------------------|
| "제주도 사진 보여줘"          | PHOTO_SEARCH  | 사진 자체를 원함      |
| "제주도 여행 어땠어?"         | EVENT_RECALL  | 경험 이야기를 원함    |
| "부산에서 뭐 먹었지?"         | EVENT_RECALL  | 활동 회상            |
| "부산 음식 사진"              | PHOTO_SEARCH  | 사진을 원함          |
| "엄마랑 찍은 사진 있어?"      | PHOTO_SEARCH  | 사진 존재 확인       |
| "엄마 생일에 뭐했더라?"       | EVENT_RECALL  | 이벤트 회상          |
| "크리스마스 때 찍은 거 보여줘" | PHOTO_SEARCH  | 사진을 원함          |
| "크리스마스 어떻게 보냈어?"    | EVENT_RECALL  | 경험을 원함          |

━━━━━━━━━━━━━━━━━━━━━━━━━━
파라미터 추출 규칙
━━━━━━━━━━━━━━━━━━━━━━━━━━
1. keywords — 장소·시간 표현을 제외한 순수 내용 키워드.
   "제주도 바다 사진" → ["바다"]   /   "고양이랑 놀았던 거" → ["고양이"]
   "맛있는 거 먹었던 사진" → ["음식"]

2. location — 언급된 장소명.
   "부산 여행" → "부산"   /   "성수동 카페" → "성수동"

3. date_from / date_to — YYYY-MM-DD 형식으로 변환.
   "작년 여름"   → "{last_year}-06-01" ~ "{last_year}-08-31"
   "지난 주말"   → "{last_sat}" ~ "{last_sun}"
   "3월"        → "{this_year}-03-01" ~ "{this_year}-03-31"
   "오늘"       → "{today}" ~ "{today}"
   날짜 정보 없으면 null.

4. diary_action — DIARY 인 경우에만.
   "써줘/만들어줘/작성해줘" → "create"
   "보여줘/읽어줘/보고 싶어" → "retrieve"
   DIARY 가 아니면 반드시 null.

━━━━━━━━━━━━━━━━━━━━━━━━━━
출력 JSON 스키마 (이 형식을 정확히 따르세요)
━━━━━━━━━━━━━━━━━━━━━━━━━━
※ 값이 없는 필드는 반드시 JSON null (문자열 "null" 절대 금지) 을 사용하세요.
{{
  "intent": "PHOTO_SEARCH | EVENT_RECALL | DIARY | GENERAL",
  "keywords": ["키워드1", "키워드2"],
  "location": "장소명" or null,
  "date_from": "YYYY-MM-DD" or null,
  "date_to": "YYYY-MM-DD" or null,
  "diary_action": "create" or "retrieve" or null
}}"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Few-shot 예시 빌더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _last_weekend(today: date) -> tuple[date, date]:
    """가장 최근 토요일~일요일을 반환한다.

    오늘이 일요일이면 어제(토) + 오늘(일)을 이번 주말로 반환한다.
    """
    weekday = today.weekday()
    if weekday == 6:  # 오늘이 일요일
        return today - timedelta(days=1), today
    days_since_sunday = (weekday + 1) % 7
    if days_since_sunday == 0:
        days_since_sunday = 7
    last_sun = today - timedelta(days=days_since_sunday)
    last_sat = last_sun - timedelta(days=1)
    return last_sat, last_sun


def _build_few_shot(today: date) -> list[dict[str, str]]:
    """동적 날짜가 반영된 few-shot 예시 메시지를 생성한다."""
    today_str = today.isoformat()
    last_sat, last_sun = _last_weekend(today)

    examples: list[tuple[str, dict]] = [
        # ① PHOTO_SEARCH — 장소 + 키워드
        (
            "제주도 바다 사진 보여줘",
            {
                "intent": "PHOTO_SEARCH",
                "keywords": ["바다"],
                "location": "제주도",
                "date_from": None,
                "date_to": None,
                "diary_action": None,
            },
        ),
        # ② EVENT_RECALL — 장소 + 여행
        (
            "뉴욕 여행 어땠어?",
            {
                "intent": "EVENT_RECALL",
                "keywords": ["여행"],
                "location": "뉴욕",
                "date_from": None,
                "date_to": None,
                "diary_action": None,
            },
        ),
        # ③ DIARY — 생성
        (
            "오늘 일기 써줘",
            {
                "intent": "DIARY",
                "keywords": [],
                "location": None,
                "date_from": today_str,
                "date_to": today_str,
                "diary_action": "create",
            },
        ),
        # ④ EVENT_RECALL — 시간 표현 (지난 주말)
        (
            "지난 주말에 뭐했지?",
            {
                "intent": "EVENT_RECALL",
                "keywords": [],
                "location": None,
                "date_from": last_sat.isoformat(),
                "date_to": last_sun.isoformat(),
                "diary_action": None,
            },
        ),
        # ⑤ GENERAL — 범위 밖
        (
            "맛집 추천해줘",
            {
                "intent": "GENERAL",
                "keywords": [],
                "location": None,
                "date_from": None,
                "date_to": None,
                "diary_action": None,
            },
        ),
        # ⑥ PHOTO_SEARCH — 사람 + 시간 (경계 사례)
        (
            "작년 크리스마스 때 친구들이랑 찍은 사진",
            {
                "intent": "PHOTO_SEARCH",
                "keywords": ["친구"],
                "location": None,
                "date_from": f"{today.year - 1}-12-24",
                "date_to": f"{today.year - 1}-12-25",
                "diary_action": None,
            },
        ),
        # ⑦ DIARY — 조회
        (
            "지난주 일기 보여줘",
            {
                "intent": "DIARY",
                "keywords": [],
                "location": None,
                "date_from": (today - timedelta(days=today.weekday() + 7)).isoformat(),
                "date_to": (today - timedelta(days=today.weekday() + 1)).isoformat(),
                "diary_action": "retrieve",
            },
        ),
    ]

    messages: list[dict[str, str]] = []
    for query, result in examples:
        messages.append({"role": "user", "content": query})
        messages.append({
            "role": "assistant",
            "content": json.dumps(result, ensure_ascii=False),
        })
    return messages


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AgentRouter
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentRouter:
    """LLM 기반 사용자 의도 분류 + 파라미터 추출 라우터."""

    def __init__(self, model_name: str = "gpt-4o"):
        self._client: Optional[AsyncOpenAI] = None
        self.model = model_name

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def _build_system_prompt(self) -> str:
        today = date.today()
        last_sat, last_sun = _last_weekend(today)
        return SYSTEM_PROMPT.format(
            today=today.isoformat(),
            this_year=today.year,
            last_year=today.year - 1,
            last_sat=last_sat.isoformat(),
            last_sun=last_sun.isoformat(),
        )

    async def classify(self, query: str) -> RouteResult:
        """사용자 쿼리를 분석하여 의도(Intent) + 파라미터를 추출한다.

        Parameters
        ----------
        query : str
            사용자의 자연어 질문.

        Returns
        -------
        RouteResult
            분류된 의도와 추출된 파라미터.
        """
        today = date.today()
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            *_build_few_shot(today),
            {"role": "user", "content": query},
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw = json.loads(response.choices[0].message.content)
            # LLM이 JSON null 대신 문자열 "null"을 반환하는 경우 방어
            for key in list(raw.keys()):
                if raw[key] == "null":
                    raw[key] = None
            return RouteResult(**raw)

        except Exception as e:
            logger.error("Agent Router 분류 실패: %s", e)
            return RouteResult(intent=Intent.GENERAL)


# 모듈 수준 싱글턴 — 다른 모듈에서 import 하여 사용
router = AgentRouter()
