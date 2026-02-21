"""
chat.py
=======
사용자 자연어 질문을 RAGEngine 에 전달하고
구조화된 응답을 반환하는 라우터.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.rag_engine import engine

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    user_id: int = 1  # 프로토타입용 기본값


@router.post("/")
async def chat(request: ChatRequest):
    """사용자 질문을 분류하고 적절한 파이프라인 결과를 반환한다.

    Returns
    -------
    dict
        {"intent": str, "params": dict, "answer": str, "photos": list}
    """
    return await engine.answer(request.query, request.user_id)
