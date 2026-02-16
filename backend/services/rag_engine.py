"""
rag_engine.py: 의도 분류, 검색, 답변 생성을 조율하는 핵심 엔진.
"""

from backend.services.agent_router import router
from pipeline.core.embedder import embed_query
from db.crud import search_photos

class RAGEngine:
    def __init__(self):
        pass

    async def answer(self, query: str, user_id: int):
        """
        1. 의도 분류 (Router)
        2. 의도에 따른 작업 수행:
           - SEARCH: 벡터 검색 -> 사진 반환 + 설명 생성
           - DIARY: 이벤트 데이터 조회 -> 텍스트 생성
        3. 최종 답변 구조화
        """
        intent = router.classify_intent(query)
        
        if intent == "SEARCH":
            # TODO: Implement LLM-based search
            # 1. Embed and search
            # 2. Re-rank or Filter (Optional)
            # 3. Generate response with photo metadata
            pass
            
        return {
            "intent": intent,
            "answer": "...",
            "photos": []
        }

engine = RAGEngine()
