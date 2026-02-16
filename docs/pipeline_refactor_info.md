# 파이프라인 구조 재편 (Refactoring) 안내

파이프라인 코드의 가독성과 유지보수성을 높이기 위해 전체적인 폴더 구조를 재편하였습니다. 기존에 `pipeline/` 폴더 바로 아래에 있던 파일들이 역할에 따라 하위 폴더로 이동되었으니 확인 부탁드립니다.

## 1. 새로운 폴더 구조

```text
pipeline/
├── core/               # 핵심 AI 모델 관련 (Heavy Models)
│   ├── ram_tagger.py
│   ├── moondream.py    (기존 moondream_captioner.py)
│   └── embedder.py
├── utils/              # 유틸리티 및 헬퍼 함수
│   ├── exif_reader.py  (기존 extract_gps.py)
│   ├── geocoder.py
│   ├── save_to_db.py
│   └── search_test.py
└── steps/              # 파이프라인 순차 실행 단계
    ├── 01_ingestion.py (스켈레톤 - 데이터 수집)
    ├── 02_tagging.py   (기존 save_keywords.py)
    ├── 03_clustering.py(기존 event_clustering.py)
    └── 04_embedding.py (기존 save_embeddings.py)
```

## 2. 주요 변경 사항 (파일 이동 및 이름 변경)

| 기존 파일명 | 변경된 위치 및 파일명 | 역할 |
| :--- | :--- | :--- |
| `ram_tagger.py` | `pipeline/core/ram_tagger.py` | RAM++ 태깅 모델 |
| `moondream_captioner.py` | `pipeline/core/moondream.py` | Moondream 캡션 모델 |
| `embedder.py` | `pipeline/core/embedder.py` | E5 임베딩 생성 모델 |
| `extract_gps.py` | `pipeline/utils/exif_reader.py` | 사진 EXIF 데이터 추출 |
| `save_keywords.py` | `pipeline/steps/02_tagging.py` | 키워드 추출 실행 (2단계) |
| `event_clustering.py` | `pipeline/steps/03_clustering.py` | 이벤트 클러스터링 (3단계) |
| `save_embeddings.py` | `pipeline/steps/04_embedding.py` | 임베딩 벡터 저장 (4단계) |

## 3. 주의사항 (Import 업데이트)

파일 위치가 변경됨에 따라 내부 `import` 문도 모두 업데이트되었습니다. 새로 코드를 작성하실 때는 다음과 같이 경로를 지정해 주세요.

*   예: `from pipeline.core.ram_tagger import ...`
*   예: `from pipeline.steps.03_clustering import ...`

기존의 `pipeline.save_keywords`와 같은 경로는 더 이상 유효하지 않습니다. 