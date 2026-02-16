# 이미지 키워드 추출 

## 1. 간단 설명

- 사진에서 키워드(태그)와 장면 캡션을 자동 추출하는 파이프라인
- RAM++ (태그 + confidence) + Moondream 2 (자연어 캡션) 하이브리드 구조
- 추출 결과를 DB에 저장하고, e5 임베딩에 통합하여 의미 검색 정확도 향상

## 2. 기술 스택

- Python 3.10+
- RAM++ (Recognize Anything Plus Plus) — Swin-Large, 4585개 태그, FP16
- Moondream 2 (2025-01-09) — 2B VLM, FP16, HuggingFace Transformers
- PyTorch 2.6 + CUDA 12.4
- PostgreSQL + pgvector (키워드/임베딩 저장)
- intfloat/multilingual-e5-base (768차원 임베딩)

## 3. 파이프라인 구조

### 전체 흐름

```
사진 파일
  ├── RAM++        → 태그 + confidence score → keywords / photo_keywords 테이블
  └── Moondream 2  → 장면 캡션 (영어)       → photos.caption 컬럼
                                                ↓
                          embedder.py: "passage: tag1 tag2 | caption | 장소"
                                                ↓
                          e5-base → 768차원 벡터 → photo_embeddings 테이블
```

### RAM++ 키워드 추출

- 4585개 사전 정의 태그에서 이미지에 해당하는 태그를 confidence score와 함께 추출
- confidence 기반 내림차순 정렬, 태그별 최적 threshold 적용
- GPU FP16 최적화, 배치 처리 지원 (배치당 0.12초/장)
- 태그 카테고리 자동 분류: person / activity / place / object

### Moondream 2 캡션 생성

- 이미지를 보고 자연어 장면 설명을 생성하는 2B VLM
- 옷 색상, 자세, 배경 가구, 분위기 등 문맥 정보까지 서술
- VQA(Visual Q&A)로 추가 태그 추출도 가능
- 이미지 인코딩 1회로 캡션 + 태그 동시 추출

### 임베딩 통합

- `build_photo_text()`에서 RAM++ 태그 + Moondream 캡션 + 장소 메타데이터를 `|` 구분자로 결합
- e5 모델이 자연어 문장에서 더 풍부한 의미를 추출하므로, 캡션 추가로 검색 품질 향상
- 예시: `"passage: laptop man smartphone businessman | A person sitting in a modern lounge holding a phone with a laptop on the table | 서울특별시"`

## 4. 세부 사항

### 모델 성능 (RTX 4070 Laptop 8GB 기준)

| 모델 | 체크포인트 | VRAM | 로드 시간 | 추론 시간 |
| --- | --- | --- | --- | --- |
| RAM++ (FP16) | ~5GB (HF 자동 다운로드) | ~3-4GB | 11초 | 0.78초/장 (단일), 0.12초/장 (배치) |
| Moondream 2 (FP16) | ~3.7GB (HF 자동 다운로드) | ~2.5GB | 10초 | 6.5초/장 |

### VRAM 관리

- 두 모델 동시 로드 시 ~6GB → 8GB VRAM에 적재 가능하지만 여유 부족
- `save_keywords.py`에서 RAM++ 추론 완료 후 VRAM 해제 → Moondream 로드 순차 실행
- 각 모델에 `unload_model()` 함수 제공

### DB 스키마 변경

- `photos` 테이블에 `caption TEXT` 컬럼 추가 (기존 테이블 마이그레이션 DDL 포함)
- `keywords` 테이블: RAM++ 태그 저장 (name + category ENUM)
- `photo_keywords` 테이블: 사진-키워드 N:N 관계 + importance (confidence score)

### 환경 호환성 패치 (transformers 4.57)

- RAM++ `bert.py`: `apply_chunking_to_forward` import 경로 변경 (`modeling_utils` → `pytorch_utils`)
- Moondream `image_crops.py`: `pyvips` 의존성을 PIL로 대체 (Windows libvips 불필요)
- `pyvips` stub 모듈로 transformers import 체크 우회

### 알려진 한계

- 카메라 앵글이 위에서 내려다보는 구도일 때 두 모델 모두 자세 오인 가능 (앉아있는데 누워있다고 판단)
- 단일 태그 오류가 발생해도 나머지 15+ 태그와 캡션이 정확하므로 임베딩 검색에 큰 영향 없음
- Moondream 캡션은 영어로만 생성 (e5 multilingual 모델이 영어도 처리하므로 문제 없음)

## 5. 파일 구조

### 새로 생성

| 파일 | 역할 |
| --- | --- |
| `pipeline/ram_tagger.py` | RAM++ 모델 로드, FP16 최적화, 단일/배치 추론, confidence 포함 태그 추출 |
| `pipeline/moondream_captioner.py` | Moondream 2 캡션/VQA 생성, 싱글톤 로드/언로드 |
| `pipeline/save_keywords.py` | 통합 파이프라인 CLI (`--with-caption`, `--caption-only`, `--force`) |
| `tests/test_ram_tagger.py` | RAM++ 7단계 자동 테스트 (import → 디바이스 → 카테고리 → 모델 로드 → 단일 추론 → 배치 추론) |

### 수정

| 파일 | 변경 내용 |
| --- | --- |
| `db/schema.py` | photos 테이블에 `caption TEXT` 컬럼 + ALTER TABLE 마이그레이션 |
| `db/crud.py` | `update_caption()`, `bulk_insert_photo_keywords()`, `delete_photo_keywords()`, `get_photo_keyword_count()` 추가, SELECT에 caption 포함 |
| `pipeline/embedder.py` | `build_photo_text(caption=)` 파라미터 추가, 키워드 + 캡션 + 장소 `\|` 구분 결합 |
| `pipeline/save_embeddings.py` | DB에서 caption 읽어서 `embed_photo(caption=)` 전달 |
| `requirements.txt` | torch, torchvision, timm, fairscale, ram, transformers, accelerate, einops 추가 |

## 6. 실행 방법

```bash
# RAM++ 키워드만 추출
python -m pipeline.save_keywords

# RAM++ + Moondream 하이브리드 (추천)
python -m pipeline.save_keywords --with-caption

# Moondream 캡션만 추출
python -m pipeline.save_keywords --caption-only

# 기존 데이터 삭제 후 재추출
python -m pipeline.save_keywords --with-caption --force

# 임베딩 생성 (키워드 + 캡션 + 장소 자동 통합)
python -m pipeline.save_embeddings

# RAM++ 단독 테스트
python -m pipeline.ram_tagger --image tests/sample_images/test_dog.jpg

# Moondream 단독 테스트
python -m pipeline.moondream_captioner --image tests/sample_images/test_dog.jpg --with-tags

# 전체 테스트
python -m tests.test_ram_tagger
```