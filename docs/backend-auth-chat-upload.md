# Backend v2: 인증 / Chat API / 사진 업로드

> 관련 이슈: `db-feedback.md` (멀티유저 + 로그인), `rag.md` (Agent Router → /chat API 연결)

---

## 1. 변경 개요

| 영역 | Before | After |
|------|--------|-------|
| 사용자 식별 | `USER_ID = 1` 하드코딩 | JWT Bearer 토큰 기반 인증 |
| Chat | RAG Engine 완성, API 미연결 | `POST /api/chat` 엔드포인트 연결 |
| RAG 응답 | 5개 핸들러 TODO (정적 텍스트) | LLM(gpt-4o-mini)이 자연어 응답 생성 |
| 사진 업로드 | 파이프라인 CLI만 존재 | `POST /api/photos/upload` REST API |
| DB | users 테이블 없음 | users 테이블 추가, CRUD 9개 함수 추가 |

---

## 2. API 엔드포인트

### 2-1. 인증 (공개)

#### `POST /api/auth/register`

회원가입 후 JWT 토큰 즉시 발급.

```json
// Request
{ "email": "user@example.com", "username": "홍길동", "password": "mypassword" }

// Response 200
{ "access_token": "eyJ...", "token_type": "bearer", "user_id": 1, "username": "홍길동" }

// Response 400
{ "detail": "이미 등록된 이메일입니다." }
```

#### `POST /api/auth/login`

```json
// Request
{ "email": "user@example.com", "password": "mypassword" }

// Response 200
{ "access_token": "eyJ...", "token_type": "bearer", "user_id": 1, "username": "홍길동" }

// Response 401
{ "detail": "이메일 또는 비밀번호가 올바르지 않습니다." }
```

### 2-2. 보호 엔드포인트 (Bearer 토큰 필수)

모든 요청에 헤더 필요:
```
Authorization: Bearer eyJ...
```

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/photos/` | 내 사진 목록 |
| `POST` | `/api/photos/search` | 시맨틱 사진 검색 |
| `GET` | `/api/photos/{id}/image` | 사진 파일 서빙 (소유권 검증) |
| `POST` | `/api/photos/upload` | 사진 업로드 (multipart) |
| `GET` | `/api/events/last` | 최근 이벤트 조회 |
| `POST` | `/api/chat` | 자연어 채팅 (RAG Engine) |

### 2-3. Chat API 상세

```json
// Request
{ "query": "제주도 바다 사진 보여줘" }

// Response
{
  "intent": "PHOTO_SEARCH",
  "params": {
    "keywords": ["바다"],
    "location": "제주도",
    "date_from": null,
    "date_to": null,
    "diary_action": null
  },
  "answer": "제주도에서 찍은 바다 사진 5장을 찾았어요! 협재 해수욕장과 ...",
  "photos": [ { "id": 1, "file_path": "...", "similarity": 0.87, ... }, ... ]
}
```

Chat이 지원하는 Intent:

| Intent | 예시 질문 | 동작 |
|--------|----------|------|
| `PHOTO_SEARCH` | "카페 사진 보여줘" | 벡터 검색 → 사진 + LLM 요약 |
| `EVENT_RECALL` | "부산 여행 어땠어?" | 이벤트 그룹핑 → LLM 내러티브 |
| `DIARY` (create) | "오늘 일기 써줘" | 사진 수집 → LLM 일기 생성 → DB 저장 |
| `DIARY` (retrieve) | "지난주 일기 보여줘" | diaries 테이블 조회 |
| `GENERAL` | "안녕" | LLM 직접 응답 |

### 2-4. 사진 업로드 상세

```bash
curl -X POST /api/photos/upload \
  -H "Authorization: Bearer eyJ..." \
  -F "file=@photo.jpg"
```

처리 흐름:
```
업로드 파일 → 임시 저장 → EXIF 추출 (GPS, 촬영시각)
                         → 역지오코딩 (장소 정보)
                         → S3 업로드
                         → DB INSERT (photos 테이블)
                         → 임시 파일 삭제
```

```json
// Response 200
{ "photo_id": 42, "s3_url": "https://bucket.s3.ap-northeast-2.amazonaws.com/photos/1/..." }
```

> **알려진 제한**: S3에 업로드된 사진은 `GET /api/photos/{id}/image`로 직접 서빙되지 않음. S3 URL 또는 presigned URL 서빙은 향후 작업.

---

## 3. DB 변경: users 테이블

```sql
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    username        TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- 기존 테이블에 FK 소급 적용하지 않음 (기존 `user_id=1` 데이터 보호)
- 멀티유저 격리는 앱 레벨에서 `WHERE user_id = %s` 조건으로 수행

### 추가된 CRUD 함수

| 함수 | 용도 |
|------|------|
| `create_user` | 회원가입 |
| `get_user_by_email` | 로그인 시 조회 |
| `get_user_by_id` | 토큰 검증 시 |
| `insert_diary` | 일기 저장 (UPSERT) |
| `get_diary` | 특정 날짜 일기 조회 |
| `list_diaries` | 범위 일기 목록 |
| `update_caption` | 캡션 업데이트 |
| `list_events_by_date_range` | RAG Engine DIARY용 |
| `list_photos_by_event` | 이벤트별 사진 조회 |

---

## 4. 인증 아키텍처

```
Client                          Server
  │                               │
  │  POST /api/auth/login         │
  │  { email, password }          │
  │──────────────────────────────>│
  │                               │  bcrypt 비밀번호 검증
  │                               │  JWT 토큰 생성 (HS256, 24h)
  │  { access_token, user_id }    │
  │<──────────────────────────────│
  │                               │
  │  GET /api/photos              │
  │  Authorization: Bearer xxx    │
  │──────────────────────────────>│
  │                               │  dependencies.get_current_user_id()
  │                               │  토큰 디코딩 → user_id 추출
  │  [ photos... ]                │
  │<──────────────────────────────│
```

- 토큰 만료: 24시간
- 해싱: bcrypt (passlib)
- 서명: HS256 (python-jose)
- 환경변수: `JWT_SECRET_KEY` (`.env`에 설정 필요)

---

## 5. 추가된 의존성

```
python-jose[cryptography]>=3.3   # JWT
passlib[bcrypt]>=1.7             # 비밀번호 해싱
fastapi>=0.100                   # 웹 프레임워크
uvicorn>=0.20                    # ASGI 서버
python-multipart>=0.0.6          # multipart/form-data (업로드)
email-validator>=2.0             # Pydantic EmailStr
```

---

## 6. 파일 변경 요약

| 파일 | 액션 | 설명 |
|------|------|------|
| `db/schema.py` | 수정 | users 테이블 DDL 추가 |
| `db/crud.py` | 수정 | CRUD 함수 9개 추가 |
| `backend/services/auth.py` | **신규** | bcrypt + JWT 유틸 |
| `backend/services/llm.py` | **신규** | OpenAI gpt-4o-mini 호출 유틸 |
| `backend/dependencies.py` | **신규** | Bearer 토큰 → user_id 의존성 |
| `backend/routers/auth.py` | **신규** | 회원가입/로그인 |
| `backend/routers/chat.py` | **신규** | RAG Engine 채팅 |
| `backend/routers/upload.py` | **신규** | 사진 업로드 (EXIF→S3→DB) |
| `backend/routers/photos.py` | 수정 | USER_ID 제거, 인증 적용, 소유권 검증 |
| `backend/routers/events.py` | 수정 | USER_ID 제거, 인증 적용 |
| `backend/services/rag_engine.py` | 수정 | 5개 TODO → LLM 응답 생성 구현 |
| `backend/main.py` | 수정 | 라우터 등록 (auth, chat, upload) |
| `requirements.txt` | 수정 | 의존성 6개 추가 |
| `.env.example` | 수정 | JWT_SECRET_KEY 추가 |

**신규 6개, 수정 8개, 총 14개 파일 (+735 / -45 lines)**
