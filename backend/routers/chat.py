"""채팅 라우터 — RAG Engine을 통한 자연어 질의응답."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.dependencies import get_current_user_id
from backend.services.rag_engine import engine

router = APIRouter()


class ChatRequest(BaseModel):
    query: str


@router.post("/")
async def chat(req: ChatRequest, user_id: int = Depends(get_current_user_id)):
    result = await engine.answer(req.query, user_id)
    return result
