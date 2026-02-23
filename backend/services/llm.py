"""OpenAI LLM 호출 중앙화 유틸리티.

응답 생성에는 gpt-4o-mini를 사용하여 비용을 절감한다.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None

MODEL = "gpt-4o-mini"


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


async def generate_response(system_prompt: str, user_content: str) -> str:
    """LLM에게 system + user 메시지를 보내고 응답 텍스트를 반환한다.

    Parameters
    ----------
    system_prompt : str
        시스템 프롬프트 (역할 설정).
    user_content : str
        사용자 컨텍스트 / 질문.

    Returns
    -------
    str
        LLM 응답 텍스트. 실패 시 빈 문자열.
    """
    try:
        response = await _get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.7,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as e:
        logger.error("LLM 응답 생성 실패: %s", e)
        return ""
