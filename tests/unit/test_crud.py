"""db/crud.py 단위 테스트 — 실제 PostgreSQL 연결 필요.

pytest -m db 로 실행. DATABASE_URL 환경변수 필요.
"""

from datetime import date, datetime

import numpy as np
import pytest

from db.crud import (
    # User
    create_user,
    get_user_by_email,
    get_user_by_id,
    # Photo
    insert_photo,
    get_photo,
    list_photos,
    list_unclustered_photos,
    # Caption
    update_caption,
    # Keywords
    insert_keyword,
    link_photo_keyword,
    bulk_insert_photo_keywords,
    get_photo_keywords_batch,
    delete_photo_keywords,
    get_photo_keyword_count,
    # Embedding
    insert_embedding,
    get_embedding,
    search_photos,
    search_photos_filtered,
    # Events
    insert_events,
    update_existing_event,
    get_last_event,
    # Diary
    insert_diary,
    get_diary,
    list_diaries,
)
from pipeline.utils.geocoder import PlaceInfo


pytestmark = pytest.mark.db


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

class TestUserCRUD:
    def test_create_and_get_by_email(self, db_conn):
        uid = create_user(db_conn, "alice@test.com", "alice", "hash123")
        assert uid > 0

        user = get_user_by_email(db_conn, "alice@test.com")
        assert user is not None
        assert user["email"] == "alice@test.com"
        assert user["username"] == "alice"

    def test_get_by_id(self, db_conn):
        uid = create_user(db_conn, "bob@test.com", "bob", "hash456")
        user = get_user_by_id(db_conn, uid)
        assert user is not None
        assert user["id"] == uid

    def test_duplicate_email_raises(self, db_conn):
        create_user(db_conn, "dup@test.com", "user1", "hash1")
        with pytest.raises(Exception):  # psycopg2 IntegrityError
            create_user(db_conn, "dup@test.com", "user2", "hash2")

    def test_get_nonexistent_email(self, db_conn):
        assert get_user_by_email(db_conn, "nobody@test.com") is None


# ---------------------------------------------------------------------------
# Photo CRUD
# ---------------------------------------------------------------------------

class TestPhotoCRUD:
    def test_insert_full_fields(self, db_conn, test_user):
        place = PlaceInfo(
            full_address="서울특별시 강남구 역삼동",
            state="서울특별시",
            city="강남구",
            district="역삼동",
            road="테헤란로",
            building="파르나스타워",
        )
        pid = insert_photo(
            db_conn, test_user, "s3://photos/test.jpg",
            lat=37.5081, lon=127.062,
            place_info=place,
            taken_at=datetime(2025, 12, 25, 14, 30),
        )
        assert pid > 0

        photo = get_photo(db_conn, pid)
        assert photo is not None
        assert photo["latitude"] == pytest.approx(37.5081)
        assert photo["city"] == "강남구"
        assert photo["building"] == "파르나스타워"

    def test_insert_partial_fields(self, db_conn, test_user):
        """GPS 없는 사진."""
        pid = insert_photo(
            db_conn, test_user, "s3://photos/no_gps.jpg",
            lat=None, lon=None,
        )
        photo = get_photo(db_conn, pid)
        assert photo["latitude"] is None
        assert photo["longitude"] is None
        assert photo["city"] is None

    def test_update_caption(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://photos/cap.jpg", None, None)
        update_caption(db_conn, pid, "아름다운 일몰")
        photo = get_photo(db_conn, pid)
        assert photo["caption"] == "아름다운 일몰"

    def test_list_unclustered(self, db_conn, test_user):
        pid = insert_photo(
            db_conn, test_user, "s3://photos/unclust.jpg", None, None,
            taken_at=datetime(2025, 12, 25),
        )
        unclustered = list_unclustered_photos(db_conn, test_user)
        ids = [p["photo_id"] for p in unclustered]
        assert pid in ids


# ---------------------------------------------------------------------------
# Keyword CRUD
# ---------------------------------------------------------------------------

class TestKeywordCRUD:
    def test_bulk_insert(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://kw.jpg", None, None)
        data = [
            ("person", "person", 0.95),
            ("beach", "place", 0.85),
            ("swim", "activity", 0.70),
        ]
        saved = bulk_insert_photo_keywords(db_conn, pid, data)
        assert saved == 3

        count = get_photo_keyword_count(db_conn, pid)
        assert count == 3

    def test_get_keywords_batch(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://kwb.jpg", None, None)
        bulk_insert_photo_keywords(db_conn, pid, [
            ("sunset", "object", 0.9),
            ("ocean", "place", 0.8),
        ])
        batch = get_photo_keywords_batch(db_conn, [pid])
        assert pid in batch
        assert "sunset" in batch[pid]

    def test_delete_keywords(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://kwdel.jpg", None, None)
        bulk_insert_photo_keywords(db_conn, pid, [("tag1", "object", 1.0)])
        assert get_photo_keyword_count(db_conn, pid) == 1

        delete_photo_keywords(db_conn, pid)
        assert get_photo_keyword_count(db_conn, pid) == 0

    def test_empty_keyword_data(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://empty.jpg", None, None)
        saved = bulk_insert_photo_keywords(db_conn, pid, [])
        assert saved == 0


# ---------------------------------------------------------------------------
# Embedding CRUD
# ---------------------------------------------------------------------------

class TestEmbeddingCRUD:
    def test_insert_and_get(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://emb.jpg", None, None)
        vec = np.random.randn(768).astype(np.float32)
        vec = vec / np.linalg.norm(vec)  # 정규화

        insert_embedding(db_conn, pid, vec)
        got = get_embedding(db_conn, pid)

        assert got is not None
        assert len(got) == 768

    def test_upsert(self, db_conn, test_user):
        """두 번 호출해도 에러 없음 (ON CONFLICT UPDATE)."""
        pid = insert_photo(db_conn, test_user, "s3://upsert.jpg", None, None)
        vec1 = np.random.randn(768).astype(np.float32)
        vec2 = np.random.randn(768).astype(np.float32)

        insert_embedding(db_conn, pid, vec1)
        insert_embedding(db_conn, pid, vec2)  # 에러 없이 갱신

        got = get_embedding(db_conn, pid)
        assert got is not None

    def test_get_nonexistent(self, db_conn):
        assert get_embedding(db_conn, 999999) is None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_cosine_search_order(self, db_conn, test_user):
        """유사도 높은 순서로 반환."""
        # 두 장의 사진에 서로 다른 임베딩 저장
        pid1 = insert_photo(db_conn, test_user, "s3://s1.jpg", None, None)
        pid2 = insert_photo(db_conn, test_user, "s3://s2.jpg", None, None)

        vec1 = np.zeros(768, dtype=np.float32)
        vec1[0] = 1.0  # 방향 1
        vec2 = np.zeros(768, dtype=np.float32)
        vec2[1] = 1.0  # 방향 2

        insert_embedding(db_conn, pid1, vec1)
        insert_embedding(db_conn, pid2, vec2)

        # vec1 방향 쿼리 → pid1이 먼저
        results = search_photos(db_conn, vec1, test_user, limit=10)
        if len(results) >= 2:
            assert results[0]["id"] == pid1

    def test_search_filtered_by_date(self, db_conn, test_user):
        pid = insert_photo(
            db_conn, test_user, "s3://dated.jpg", None, None,
            taken_at=datetime(2025, 6, 15, 12, 0),
        )
        vec = np.random.randn(768).astype(np.float32)
        insert_embedding(db_conn, pid, vec)

        # 날짜 범위 내
        results = search_photos_filtered(
            db_conn, vec, test_user,
            date_from=datetime(2025, 6, 1),
            date_to=datetime(2025, 6, 30),
        )
        ids = [r["id"] for r in results]
        assert pid in ids

        # 날짜 범위 밖
        results2 = search_photos_filtered(
            db_conn, vec, test_user,
            date_from=datetime(2025, 1, 1),
            date_to=datetime(2025, 1, 31),
        )
        ids2 = [r["id"] for r in results2]
        assert pid not in ids2


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------

class TestEventCRUD:
    def test_insert_events(self, db_conn, test_user):
        events = [{
            "event_ref": 0,
            "user_id": test_user,
            "started_at": datetime(2025, 12, 25, 10, 0),
            "ended_at": datetime(2025, 12, 25, 12, 0),
            "primary_location": "37.5665,126.9780",
            "photo_count": 5,
        }]
        id_map = insert_events(db_conn, events)
        assert 0 in id_map
        assert id_map[0] > 0

    def test_update_existing_event(self, db_conn, test_user):
        events = [{
            "event_ref": 0,
            "user_id": test_user,
            "started_at": datetime(2025, 12, 25, 10, 0),
            "ended_at": datetime(2025, 12, 25, 12, 0),
            "primary_location": "37.5665,126.9780",
            "photo_count": 3,
        }]
        id_map = insert_events(db_conn, events)
        eid = id_map[0]

        update_existing_event(
            db_conn, eid,
            ended_at=datetime(2025, 12, 25, 14, 0),
            primary_location="37.5700,126.9800",
            photo_count=7,
        )
        # 검증은 get_last_event로
        last = get_last_event(db_conn, test_user)
        assert last is not None
        assert last["photo_count"] == 7

    def test_insert_empty_events(self, db_conn):
        assert insert_events(db_conn, []) == {}


# ---------------------------------------------------------------------------
# Diary CRUD
# ---------------------------------------------------------------------------

class TestDiaryCRUD:
    def test_insert_and_get(self, db_conn, test_user):
        did = insert_diary(db_conn, test_user, date(2025, 12, 25), "크리스마스 일기입니다.")
        assert did > 0

        diary = get_diary(db_conn, test_user, date(2025, 12, 25))
        assert diary is not None
        assert diary["content"] == "크리스마스 일기입니다."

    def test_upsert_updates_content(self, db_conn, test_user):
        """같은 날짜 UPSERT → content 갱신."""
        insert_diary(db_conn, test_user, date(2025, 12, 25), "원본")
        insert_diary(db_conn, test_user, date(2025, 12, 25), "수정본")

        diary = get_diary(db_conn, test_user, date(2025, 12, 25))
        assert diary["content"] == "수정본"

    def test_list_diaries(self, db_conn, test_user):
        insert_diary(db_conn, test_user, date(2025, 12, 24), "12/24")
        insert_diary(db_conn, test_user, date(2025, 12, 25), "12/25")

        diaries = list_diaries(
            db_conn, test_user,
            date_from=date(2025, 12, 24),
            date_to=date(2025, 12, 25),
        )
        assert len(diaries) >= 2

    def test_get_nonexistent_diary(self, db_conn, test_user):
        assert get_diary(db_conn, test_user, date(2099, 1, 1)) is None
