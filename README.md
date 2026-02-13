# PicStory — 사진 기반 추억 검색 RAG 챗봇

사진의 EXIF 메타데이터(GPS, 촬영 시각)를 추출하고, 역지오코딩으로 장소 정보를 조회한 뒤, 벡터 임베딩 기반 시맨틱 검색으로 자연어 질문에 맞는 사진을 찾아주는 서비스입니다.








# PhotoDiary — Event Clustering 모듈

이 문서는 **이벤트 클러스터링 담당 업무 범위**만 정리합니다.
목표는 시간순 사진 메타데이터를 받아 의미 있는 이벤트 단위로 묶고,
결과를 DB `events` 스키마와 맞는 형태로 반환하는 것입니다.

## 담당 범위

- 구현 파일: `pipeline/event_clustering.py`
- 핵심 함수
  - `haversine_distance(lat1, lon1, lat2, lon2) -> float`
  - `cluster_events(photo_df, user_id=1, ...) -> list[dict]`
  - `build_mock_photo_data() -> pd.DataFrame`

## 클러스터링 규칙 (현재 기준)

사진을 `timestamp` 기준 오름차순 정렬한 뒤, `P_i`를 이전 데이터와 비교하여 이벤트 분리 여부를 판단합니다.

1. **시간 분리 (연속성 체크)**
   - `P_i.timestamp - P_{i-1}.timestamp >= 120분` 이면 분리

2. **공간 분리 (앵커 기준 체크)**
   - 이벤트의 첫 사진을 Anchor로 두고,
   - `distance(Anchor, P_i) >= 500m` 이면 분리

### 왜 Anchor 기준인가?

`distance(P_{i-1}, P_i)`만 쓰면, 100m씩 조금씩 이동하는 경우 누적 1km 이상 이동했어도 분리가 늦어지는
**creeping distance 문제**가 발생할 수 있습니다.
Anchor 기준은 누적 이동을 안정적으로 감지합니다.

## 입력/출력 스펙

### 입력 DataFrame 필수 컬럼

- `photo_id`
- `timestamp` (datetime 또는 파싱 가능한 문자열)
- `latitude` (float)
- `longitude` (float)

### 출력 스키마 (DB `events` 정합)

각 이벤트는 아래 키를 가집니다.

- `user_id` (int)
- `started_at` (datetime)
- `ended_at` (datetime)
- `primary_location` (str, `"lat,lon"`)
- `photo_count` (int)

디버깅/검증을 위해 현재는 아래 키도 함께 반환합니다.

- `photo_ids` (list)

## 실행 방법

### 1) 의존성 설치

```bash
pip install -r requirements.txt
```

### 2) Mock Data 테스트 실행

```bash
python -m pipeline.event_clustering
```

실행 시, 모의 사진 데이터를 클러스터링한 JSON 결과를 출력합니다.

## 예시 출력 (요약)

```json
[
  {
    "user_id": 1,
    "started_at": "2026-02-13T09:00:00+00:00",
    "ended_at": "2026-02-13T09:50:00+00:00",
    "primary_location": "37.498165,127.027637",
    "photo_count": 3,
    "photo_ids": ["p1", "p2", "p3"]
  }
]
```

## 파라미터 튜닝 포인트

- `TIME_SPLIT_MINUTES` 기본값: `120`
- `DISTANCE_SPLIT_METERS` 기본값: `500`

`cluster_events(...)` 호출 시 인자로 덮어쓸 수 있어 지역/도메인별 실험이 가능합니다.

<<<<<<< HEAD
```
├── db/                          — DB 스키마 + CRUD
│   ├── schema.py                — DDL 정의 & get_connection()
│   └── crud.py                  — photos CRUD + embedding 저장/검색
├── pipeline/                    — 사진 처리 파이프라인
│   ├── geocoder.py              — 역지오코딩 (Google/Naver/Nominatim)
│   ├── extract_gps.py           — EXIF GPS 추출 + 장소 조회
│   ├── save_to_db.py            — GPS 추출 → 역지오코딩 → DB 저장
│   ├── embedder.py              — 임베딩 모듈 (e5-base, 768차원)
│   ├── save_embeddings.py       — 사진 메타데이터 → 벡터 → DB 저장
│   └── search_test.py           — 시맨틱 검색 테스트 스크립트
├── docs/
│   ├── db-design.md             — DB 설계 문서
│   └── embedding-model.md       — 임베딩 모델 선정 이유
├── .env                         — API 키 & DB 접속 정보 (gitignore)
├── requirements.txt
└── README.md
```
=======
## 현재 가정/제약
>>>>>>> fd6532a (feat: 시공간 클러스터링 모듈 구현 및 문서화)

- 위치 좌표가 없는 행(`latitude/longitude` 결측)에 대한 별도 처리 로직은 아직 없습니다.
- `primary_location`은 이벤트 내 평균 좌표 문자열입니다.
  - 실제 주소/행정동 대표값이 필요하면 후처리(역지오코딩) 단계가 추가로 필요합니다.
- 이 모듈은 **클러스터링 결과 반환**까지 담당하며,
  DB INSERT 및 `photos.event_id` 업데이트는 별도 파이프라인에서 수행합니다.

<<<<<<< HEAD
```
사진 파일 (.jpeg/.jpg/.png/.heic)
  │
  ▼
[1] extract_gps.py — EXIF에서 GPS 좌표 + 촬영 시각 추출
  │
  ▼
[2] geocoder.py — GPS 좌표 → 역지오코딩 → PlaceInfo (주소, 건물명 등)
  │
  ▼
[3] crud.py — photos 테이블에 INSERT (좌표, 장소, 촬영 시각)
  │
  ▼
[4] embedder.py — 키워드 + 장소 메타데이터 → e5-base → 768차원 벡터
  │
  ▼
[5] crud.py — photo_embeddings 테이블에 벡터 저장
  │
  ▼
[검색] 사용자 쿼리 → 벡터 변환 → pgvector cosine 유사도 → top-K 사진 반환
```

- `save_to_db.py`가 [1]~[3]을 실행합니다.
- `save_embeddings.py`가 [4]~[5]를 실행합니다.

> **참고: file_path**
> 현재는 로컬 절대 경로를 그대로 DB에 저장합니다.
> 배포 시에는 S3 등에 업로드 후 URL을 저장하도록 변경 예정이며,
> `save_to_db.py`에 업로드 단계만 추가하면 됩니다.

## 실행

### 1. GPS 추출만 (DB 저장 없이)
```bash
source .venv/bin/activate
python -m pipeline.extract_gps
```

### 2. GPS 추출 + DB 저장
```bash
source .venv/bin/activate
python -m pipeline.save_to_db
```

### 3. 임베딩 벡터 생성 + 저장
DB에 저장된 사진의 메타데이터를 벡터로 변환하여 `photo_embeddings` 테이블에 저장합니다.
```bash
source .venv/bin/activate
python -m pipeline.save_embeddings
```

### 4. 시맨틱 검색 테스트
자연어 쿼리로 사진을 검색합니다.
```bash
# 단발 검색
python -m pipeline.search_test "추어탕 먹은 사진"

# 메타데이터 필터 + 검색
python -m pipeline.search_test "피자 먹은 사진" --city 부산

# 대화형 모드
python -m pipeline.search_test
```

### DB 확인
```bash
psql -d photodiary -c "SELECT id, file_path, latitude, longitude, city, building FROM photos;"
psql -d photodiary -c "SELECT COUNT(*) FROM photo_embeddings;"
```

API 키 없이 실행하면 Nominatim(무료)으로 fallback됩니다. (건물/가게 이름 미지원)

## API 키 발급

### Google Maps (데모용)

1. [Google Cloud Console](https://console.cloud.google.com) 접속 & 로그인
2. 상단 프로젝트 선택 → **새 프로젝트** 생성
3. **결제** → 결제 계정 연결 (월 $200 무료 크레딧)
4. **API 및 서비스** → **라이브러리**에서 아래 2개 활성화:
   - **Geocoding API**
   - **Places API (New)**
5. **API 및 서비스** → **사용자 인증 정보** → **+ 사용자 인증 정보 만들기** → **API 키**
6. (권장) 생성된 키 클릭 → API 제한 → Geocoding API, Places API (New)만 선택

### Naver Maps (프로덕션용)

1. [Naver Cloud Platform](https://www.ncloud.com) 가입 & 로그인
2. 콘솔 → **AI·NAVER API** → **Application 등록**
3. **Maps** → **Reverse Geocoding** 선택 후 등록
4. 발급된 Client ID / Client Secret을 `.env`에 입력


## PostgreSQL 설치 방법
```bash
brew install postgresql@14  # 버전은 14 또는 최신 버전을 선택하세요.
brew services start postgresql@14
```

## DBeaver 설치 방법 (macOS)
DBeaver는 DB 내부 데이터를 표 형태로 편하게 보고 쿼리를 날릴 수 있게 해주는 도구입니다.
1. **DBeaver 공식 다운로드 페이지**에 접속합니다.
2. macOS (Apple Silicon / Intel) 중 건우님의 맥 프로세서(M1/M2/M3는 Apple Silicon)에 맞는 .dm g 파일을 다운로드합니다.
3. 다운로드된 파일을 실행하고 DBeaver 아이콘을 Applications 폴더로 드래그하여 설치를 완료합니다.

## DBeaver 연결 설정

### 새 연결 만들기
1. 상단 메뉴 **Database → New Database Connection** (또는 플러그 아이콘) 클릭
2. **PostgreSQL** 선택 → **Next**
3. 아래와 같이 입력:

| 항목 | 값 |
|------|-----|
| Host | `localhost` |
| Port | `5432` |
| Database | `photodiary` |
| Username | 본인 시스템 계정 (터미널에서 `whoami`로 확인) |
| Password | (비워두기) |

4. **Save password** 체크 → **Test Connection**으로 연결 확인 → **Finish**

### 테이블 확인 경로
```
photodiary → Schemas → public → Tables
```

> **주의**: 기본 `postgres` 데이터베이스가 아닌 **`photodiary`** 데이터베이스로 연결해야 테이블이 보입니다. `postgres` DB의 Tables에는 아무것도 없으니 헷갈리지 않도록 주의하세요.
=======
## 다음 작업 제안

- `events` INSERT + `photos.event_id` 매핑 트랜잭션 함수 추가
- 결측 좌표/이상치 좌표에 대한 방어 로직 추가
- 샘플 케이스 기반 단위 테스트 추가 (시간 경계, 거리 경계, creeping 케이스)
>>>>>>> fd6532a (feat: 시공간 클러스터링 모듈 구현 및 문서화)
