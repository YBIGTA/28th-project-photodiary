# PhotoDiary — 사진 GPS 추출 & 장소 조회

사진의 EXIF 데이터에서 GPS 좌표를 추출하고, 역지오코딩으로 장소 이름(건물/가게 포함)을 조회합니다.

## 환경 설정

### 1. 가상환경 생성 & 의존성 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 API 키 및 DB 접속 정보 입력
```

### 3. DB 세팅 (PostgreSQL + pgvector)

```bash
# PostgreSQL 설치 (아래 "PostgreSQL 설치 방법" 참고)

# DB 생성
createdb photodiary

# pgvector 확장 설치
# brew install pgvector 로 설치된 버전이 PostgreSQL 버전과 맞지 않을 수 있음
# 그 경우 소스 빌드:
cd /tmp
git clone --branch v0.8.1 https://github.com/pgvector/pgvector.git
cd pgvector
PG_CONFIG=$(brew --prefix postgresql@14)/bin/pg_config make && make install

# 테이블 생성
source .venv/bin/activate
python db/schema.py
```

`.env`에 DB 접속 정보를 설정합니다:
```env
# 방법 A: DATABASE_URL 한 줄로
DATABASE_URL=postgresql://postgres:password@localhost:5432/photodiary

# 방법 B: 개별 변수
DB_HOST=localhost
DB_PORT=5432
DB_NAME=photodiary
DB_USER=postgres  # or 사용자 id (whoami로 확인 가능)
DB_PASSWORD=password
```

## 프로젝트 구조

```
├── db/                  — DB 스키마 + CRUD
│   ├── schema.py        — DDL 정의 & get_connection()
│   └── crud.py          — photos 테이블 CRUD 함수
├── pipeline/            — 사진 처리 파이프라인
│   ├── geocoder.py      — 역지오코딩 (Google/Naver/Nominatim)
│   ├── extract_gps.py   — EXIF GPS 추출 + 장소 조회
│   └── save_to_db.py    — GPS 추출 → 역지오코딩 → DB 저장
├── .env                 — API 키 & DB 접속 정보 (gitignore)
├── requirements.txt
└── README.md
```

## 파이프라인 흐름

```
사진 파일 (.jpeg/.jpg/.png/.heic)
  │
  ▼
extract_gps.py — EXIF에서 GPS 좌표 + 촬영 시각(taken_at) 추출
  │
  ▼
geocoder.py — GPS 좌표 → 역지오코딩 → PlaceInfo (주소, 건물명 등)
  │
  ▼
crud.py — photos 테이블에 INSERT (좌표, 장소, 촬영 시각)
```

`save_to_db.py`가 위 세 단계를 순서대로 실행하는 진입점입니다.

> **참고: file_path**
> 현재는 로컬 절대 경로를 그대로 DB에 저장합니다.
> 배포 시에는 S3 등에 업로드 후 URL을 저장하도록 변경 예정이며,
> `save_to_db.py`에 업로드 단계만 추가하면 됩니다. (`crud.py`, `extract_gps.py` 변경 없음)

## 실행

### GPS 추출만 (DB 저장 없이)
```bash
source .venv/bin/activate
python -m pipeline.extract_gps
```

### GPS 추출 + DB 저장
```bash
source .venv/bin/activate
python -m pipeline.save_to_db
```

DB에 저장된 결과 확인:
```bash
psql -d photodiary -c "SELECT id, file_path, latitude, longitude, city, building FROM photos;"
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