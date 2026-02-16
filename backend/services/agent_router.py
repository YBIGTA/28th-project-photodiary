"""
agent_router.py: 사용자 질문의 의도를 분류하는 모듈.
"""

class AgentRouter:
    def __init__(self, model_name="gpt-4o"):
        self.model = model_name

    def classify_intent(self, query: str) -> str:
        """
        사용자 쿼리를 분석하여 어떤 작업을 수행할지 결정.
        
        Returns:
            - 'SEARCH': 특정 사진 찾기
            - 'DIARY': 일기 생성/조회
            - 'SUMMARY': 특정 기간 요약
            - 'GENERAL': 일반 대화
            (변경될 수 있음, 구현하시는 분께서 정해주세요)
        """
        # TODO: Implement LLM-based classification
        return "SEARCH"

router = AgentRouter()
