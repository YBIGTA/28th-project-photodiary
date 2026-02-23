## Summary
Person 2 (Agent Routing) 파트의 핵심인 사용자 의도 분석 및 라우팅 시스템을 구현했습니다.
사용자의 자연어 질문을 4가지 Intent로 분류하고, RAG Engine이 비동기적으로 동작하도록 인터페이스를 통합했습니다.

## Changes
1. Agent Router 구현 (backend/services/agent_router.py)
기능: GPT-4o 기반 사용자 질문 분류 (PHOTO_SEARCH, EVENT_RECALL, DIARY, GENERAL)
특징:
Pydantic 모델 도입으로 날짜/장소/키워드 등 구조화된 파라미터 추출 보장
Dynamic Few-shot: "지난 주말" 등을 오늘 날짜 기준으로 계산해 프롬프트에 주입 (정확도 향상)
AsyncOpenAI Lazy Init 적용으로 서버 초기화 시 안정성 확보
2. RAG Engine 리팩토링 (backend/services/rag_engine.py)
변경: 기존 동기 메서드(classify_intent)를 비동기(await router.classify)로 전면 교체
로직: 라우터가 반환한 RouteResult 객체를 받아, Intent별 전용 핸들러로 분기 처리
3. 기타 수정
db/crud.py: pipeline.utils.geocoder 임포트 경로 수정
requirements.txt: openai, pydantic 등 필수 의존성 추가
## Verification (테스트 결과)
로컬 환경에서 Mock 테스트(test_integration.py)를 통해 다음 항목을 검증했습니다.

인터페이스 호환성: Pass (Router ↔ Engine 데이터 흐름 정상)
의도 분류 정확도:
"제주도 바다 사진 보여줘" → PHOTO_SEARCH (Location="제주도")
"뉴욕 여행 어땠어?" → EVENT_RECALL (Location="뉴욕")
"오늘 일기 써줘" → DIARY (Action="create")

## To-Do
현재 로직은 완성되었으나, **API 엔드포인트(main.py)**는 구현하지 않았습니다.
백엔드 메인 서버 작업 시 rag_engine.engine.answer(query, user_id) 메서드를 호출하여 /chat API에 연결하면 됩니다.