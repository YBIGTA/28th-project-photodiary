# DB 설계 문서

## 1. 왜 PostgreSQL + pgvector인가

### 비교

| 비교 항목 | PostgreSQL + pgvector (통합) | RDB + ChromaDB (분리) |
|---|---|---|
| 관리 포인트 | DB 1개 (운영 및 백업 용이) | DB 2개 (서로 다른 엔진 관리 필요) |
| 데이터 동기화 | 불필요 (한 테이블 내 존재) | 필요 (RDB 수정 시 ChromaDB도 갱신) |
| 쿼리 복잡도 | SQL 한 번에 메타데이터+벡터 검색 | RDB에서 ID 필터링 후 ChromaDB 조회 |
| 공간 검색 | PostGIS 활용 시 매우 강력 | 기본 좌표 저장 수준 |
| 배포 | PostgreSQL만 띄우면 끝 | 두 서비스 각각 배포·모니터링 |
| 트랜잭션 | 메타데이터와 임베딩을 하나의 트랜잭션으로 보장 | 분리되어 있어 정합성 보장 어려움 |

### 결론

우리 서비스는 사진 메타데이터(GPS, 장소, 시간)와 임베딩 벡터를 **항상 함께** 조회한다. 예를 들어 "송파구에서 찍은 사진 중 유사한 것 찾기" 같은 쿼리는 통합 DB에서 SQL 한 방이지만, 분리 구조에서는 RDB 필터링 → ChromaDB 검색 → 다시 RDB 조인이라는 3단계가 필요하다. 관리 비용과 쿼리 복잡도 모두 통합 구조가 유리하므로 **PostgreSQL + pgvector**를 선택했다.

---

## 2. 스키마 구조

### 테이블 관계도

```
photos ──< photo_keywords >── keywords
  │
  ├── photo_embeddings (1:1, vector 768차원)
  │
  └──> events (N:1)

diaries (독립, user_id + diary_date unique)
```

---

### photos — 핵심 테이블

사진 파일 경로, GPS 좌표, 역지오코딩 결과, 촬영 시각을 저장한다.
현재 `file_path`는 로컬 절대 경로이며, 배포 시 S3 URL로 전환 예정.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | SERIAL | PK | |
| user_id | INTEGER | NOT NULL | 사용자 ID |
| file_path | TEXT | NOT NULL | 이미지 파일 경로 (추후 S3 URL) |
| taken_at | TIMESTAMPTZ | | EXIF 촬영 시각 |
| latitude | DOUBLE PRECISION | | 위도 |
| longitude | DOUBLE PRECISION | | 경도 |
| state | TEXT | | 시/도 |
| city | TEXT | | 시/군/구 |
| district | TEXT | | 동/읍/면 |
| road | TEXT | | 도로명 |
| building | TEXT | | 건물/가게 이름 |
| full_address | TEXT | | 전체 주소 |
| event_id | INTEGER | FK → events(id), ON DELETE SET NULL | 소속 이벤트 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 레코드 생성 시각 |

---

### events — 이벤트(외출/여행 등) 그룹

시간 범위로 사진들을 하나의 이벤트로 묶는다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | SERIAL | PK | |
| user_id | INTEGER | NOT NULL | 사용자 ID |
| started_at | TIMESTAMPTZ | NOT NULL | 이벤트 시작 시각 |
| ended_at | TIMESTAMPTZ | | 이벤트 종료 시각 |
| primary_location | TEXT | | 대표 장소명 |
| photo_count | INTEGER | NOT NULL, DEFAULT 0 | 소속 사진 수 |

---

### keywords — 사진 키워드

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | SERIAL | PK | |
| name | TEXT | NOT NULL, UNIQUE | 키워드명 (예: "카페", "친구") |
| category | keyword_category | NOT NULL | person / activity / place / object |

---

### photo_keywords — 사진-키워드 연결 (N:N)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | SERIAL | PK | |
| photo_id | INTEGER | NOT NULL, FK → photos(id), ON DELETE CASCADE | |
| keyword_id | INTEGER | NOT NULL, FK → keywords(id), ON DELETE CASCADE | |
| importance | REAL | NOT NULL, DEFAULT 1.0 | 키워드 중요도 점수 |
| | | UNIQUE (photo_id, keyword_id) | 중복 방지 |

---

### diaries — 일기

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | SERIAL | PK | |
| user_id | INTEGER | NOT NULL | 사용자 ID |
| diary_date | DATE | NOT NULL | 일기 날짜 |
| content | TEXT | NOT NULL | 일기 내용 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 레코드 생성 시각 |
| | | UNIQUE (user_id, diary_date) | 하루에 한 개 |

---

### photo_embeddings — 사진 임베딩 벡터

pgvector의 `vector(768)` 타입을 사용하며, HNSW 인덱스로 cosine 유사도 검색을 지원한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | SERIAL | PK | |
| photo_id | INTEGER | NOT NULL, UNIQUE, FK → photos(id), ON DELETE CASCADE | photos와 1:1 |
| embedding | vector(768) | NOT NULL | 임베딩 벡터 |

---

## 3. 인덱스

| 인덱스 | 대상 | 용도 |
|---|---|---|
| idx_photos_user_taken | photos(user_id, taken_at) | 사용자별 시간순 조회 |
| idx_photos_user_district | photos(user_id, district) | 사용자별 지역 필터링 |
| idx_photos_event | photos(event_id) | 이벤트별 사진 조회 |
| idx_keywords_category | keywords(category) | 카테고리별 키워드 조회 |
| idx_photo_keywords_photo | photo_keywords(photo_id) | 사진별 키워드 조회 |
| idx_photo_keywords_keyword_imp | photo_keywords(keyword_id, importance DESC) | 키워드별 중요도순 조회 |
| idx_events_user_started | events(user_id, started_at) | 사용자별 이벤트 시간순 |
| idx_photo_embeddings_hnsw | photo_embeddings(embedding) HNSW cosine | 벡터 유사도 검색 |
