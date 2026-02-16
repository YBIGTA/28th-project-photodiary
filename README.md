# PicTrace - Person 2 (Event Clustering)

이 문서는 **Person 2(이벤트 클러스터링)** 담당 구현 내용을 기준으로 작성한 최종 README입니다.
핵심 목표는 사진 메타데이터를 이벤트 단위로 묶고, DB와 안전하게 동기화하는 것입니다.

---

## 1) 담당한 범위

- 시공간 기반 이벤트 분리 로직 구현
- 증분 클러스터링(미처리 사진만 대상) 파이프라인 구현
- DB 반영(`events` INSERT + `photos.event_id` UPDATE) 연동

- Phase 2 품질 고도화
  - Config 기반 파라미터 관리
  - 병합 시 가중 평균 중심점(Weighted Centroid)
  - Stay(체류) 예외 규칙
  - Null Safety 및 트랜잭션 원자성 보강

`save_to_db.py`는 기존 데이터 수집 역할로 유지하고,
클러스터링은 별도 엔트리포인트 `pipeline/run_clustering.py`에서 수행합니다.

---

## 2) 파일별 구현 내용

### `pipeline/event_clustering.py`

이벤트 클러스터링 핵심 모듈입니다.

주요 구현:
- `ClusterConfig`
  - `time_split_minutes` (기본 120)
  - `distance_split_meters` (기본 500)
  - `stay_distance_meters` (기본 50)
  - `stay_time_split_minutes` (기본 720, 12시간)
- `haversine_distance(...)`
  - 지구 곡률을 고려한 거리 계산
- `_should_split(...)`
  - 거리 기준 분리: anchor 대비 `>= distance_split_meters`
  - Stay 판정: anchor 근처(`< stay_distance_meters`)면 시간 임계값 완화
  - GPS 결측 시 거리 계산 스킵, 시간 기준만 적용
- `cluster_events(...)`
  - 기본 클러스터링 + `last_event` 기반 증분 merge 판단
  - 반환 구조:
    - `events`: 이벤트 payload 리스트
    - `photo_event_links`: 사진-이벤트 매핑 리스트
- `resolve_photo_event_updates(...)`
  - `events` INSERT 결과와 매핑 정보를 결합해
    `photos.event_id` 업데이트용 튜플 생성

Phase 2 반영 포인트:
- 병합 시 중심점 계산은 기존 이벤트와 신규 이벤트를 **가중 평균**으로 결합
- 가중치는 GPS 유효 개수 기준(`gps_photo_count` 우선)
- `gps_photo_count=0`과 `None`을 구분해서 처리(Null Safety)

---

### `pipeline/run_clustering.py`

증분 이벤트 클러스터링 실행 스크립트입니다.

동작 순서:
1. `list_unclustered_photos()`로 `event_id IS NULL` 사진 조회
2. `get_last_event()`로 마지막 이벤트 조회
3. `cluster_events(..., last_event=...)` 실행
4. 신규 이벤트만 `insert_events()`로 `events` INSERT
5. 기존 이벤트 병합 건은 `update_existing_event()`로 메타데이터 갱신
6. `resolve_photo_event_updates()` + `update_photo_event_ids()`로 사진 event_id 일괄 업데이트
7. 로그 출력
   - `N개의 이벤트 생성, M개의 이벤트 병합, K개의 사진 업데이트 완료`

트랜잭션 처리:
- 쓰기 함수들을 `commit=False`로 호출
- 마지막에 `conn.commit()` 1회
- 오류 시 `rollback()`으로 부분 반영 방지

---

### `db/crud.py`

클러스터링 연동을 위해 아래 함수들을 추가/확장했습니다.

추가 함수:
- `list_unclustered_photos(conn, user_id, limit=1000)`
- `get_last_event(conn, user_id)`
  - `gps_photo_count` 계산 포함
- `insert_events(conn, events, commit=True)`
  - `event_ref -> event_id` 매핑 반환
- `update_existing_event(conn, event_id, ended_at, primary_location, photo_count, commit=True)`
- `update_photo_event_ids(conn, photo_event_updates, commit=True)`

개선:
- 주요 쓰기 함수에 `commit=True` 기본 파라미터를 두어
  단건 사용/배치 트랜잭션 모두 대응 가능하게 함

---

## 3) DB 스키마 제약 준수

- `events.primary_location`은 기존 스키마를 유지하여 문자열 `"lat,lon"` 형식으로 저장
- 새로운 DB 컬럼 추가 없이 구현
- 증분 merge를 위해 필요한 `gps_photo_count`는 조회 시 서브쿼리로 계산

---

## 4) 실행 방법

## 4-1. 환경 준비

```bash
pip install -r requirements.txt
```

필요 환경변수(`.env`):
- `DATABASE_URL` 또는
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

---

## 4-2. 클러스터링 로직 단독 테스트 (Mock)

```bash
python -m pipeline.event_clustering
```

출력:
- `events`
- `photo_event_links`

---

## 4-3. 실제 DB 증분 클러스터링 실행

```bash
python -m pipeline.run_clustering
```

예상 로그:
- `처리할 미클러스터 사진이 없습니다.`
- 또는
- `N개의 이벤트 생성, M개의 이벤트 병합, K개의 사진 업데이트 완료`

---

## 5) 입력/출력 계약 (핵심)

### `cluster_events` 입력 DataFrame 필수 컬럼
- `photo_id`
- `timestamp`
- `latitude`
- `longitude`

### `cluster_events` 반환 구조
- `events`: DB 반영용 이벤트 목록
  - `event_ref`, `existing_event_id`, `user_id`, `started_at`, `ended_at`, `primary_location`, `photo_count`, `photo_ids`
- `photo_event_links`: 사진-이벤트 연결 목록
  - `photo_id`, `event_ref`, `existing_event_id`

---

## 6) 구현 의사결정 요약

- Anchor 기준 거리 비교로 creeping distance 문제 완화
- Stay 규칙으로 장시간 체류를 불필요하게 분리하지 않음
- 증분 처리(`last_event`)로 전체 재클러스터링 비용 절감
- Null Safety(`None`/`0` 구분)로 극단 케이스 방어
- 트랜잭션 일원화로 DB 일관성 보장

---

## 7) 빠른 점검 체크리스트

- `python -m pipeline.event_clustering` 실행 성공
- `python -m pipeline.run_clustering` 실행 성공
- 오류 발생 시 부분 반영 없이 rollback 확인
- `events`와 `photos.event_id`가 동일 실행 단위로 동기화되는지 확인

---

## 8) 참고

프로젝트의 다른 파이프라인(`extract_gps.py`, `geocoder.py`, `save_to_db.py`, `save_embeddings.py`)은
다른 담당자 역할을 유지하고, 본 문서는 이벤트 클러스터링 구현 작업 결과 중심으로 작성했습니다.
