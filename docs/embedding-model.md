# Embedding 모델 선정: intfloat/multilingual-e5-base

## 선정 모델

**intfloat/multilingual-e5-base** (768차원)

## 왜 이 모델인가

### 1. 비대칭 검색(Asymmetric Retrieval)에 특화

이 프로젝트에서 검색 대상(document)과 사용자 질문(query)의 형태가 다르다:

```
문서(DB): "피자 크리스마스트리 사람 식사 부산 해운대구"   ← 키워드 나열
쿼리:    "부산에서 피자 먹은 사진 찾아줘"               ← 자연어 문장
```

e5 모델은 `"query: ..."` / `"passage: ..."` 접두사로 이 둘을 구분하도록 학습되어 있어서, 키워드 리스트(RAM++ 출력) ↔ 자연어 쿼리 간의 관계를 잘 찾는다.

반면 ko-sroberta 같은 대칭 유사도 모델은 문장 ↔ 문장 비교에 최적화되어 있어서, 키워드 나열 ↔ 자연어 문장 패턴에는 상대적으로 약하다.

### 2. 후보 모델 비교

| 모델 | 차원 | 검색 방식 | 한국어 | 비용 |
|------|-----|---------|--------|-----|
| **intfloat/multilingual-e5-base** | 768 | 비대칭 (query/passage) | 다국어 상위권 | 무료 (로컬) |
| jhgan/ko-sroberta-multitask | 768 | 대칭 (문장↔문장) | 한국어 특화 | 무료 (로컬) |
| openai text-embedding-3-small | 1536 | 비대칭 | 최상 | API 유료 |

### 3. 선정 이유 요약

- **RAM++ 키워드 → 자연어 쿼리** 검색 패턴에 가장 적합 (비대칭 검색)
- 768차원 = 성능/속도/저장공간 밸런스 (BERT-base 표준)
- 다국어 지원으로 한국어 + 영어 장소명 모두 처리 가능
- 로컬 실행 가능 (API 비용 없음)
- 접두사 처리는 `"query: "` / `"passage: "` 한 줄 추가로 해결

## 사용 방법

```python
from pipeline.embedder import embed_photo, embed_query

# 사진 임베딩 (DB 저장용)
vec = embed_photo(
    keywords=["피자", "사람", "식사"],
    place_parts={"city": "부산광역시", "district": "해운대구"}
)

# 쿼리 임베딩 (검색용)
q_vec = embed_query("부산에서 피자 먹은 사진")
```

## 참고: 768차원인 이유

| 차원 | 모델 크기 | 용도 |
|------|---------|-----|
| 384 | MiniLM (경량) | 속도 최우선, 영어 위주 |
| **768** | **BERT-base (표준)** | **성능/속도 밸런스, 대부분의 프로젝트에 적합** |
| 1024 | BERT-large | 정확도 우선, 리소스 많이 사용 |
| 1536+ | OpenAI 등 | API 기반, 비용 발생 |

사진 수백~수천 장 규모에서 768차원은 검색 속도와 저장 공간 모두 부담 없다.
