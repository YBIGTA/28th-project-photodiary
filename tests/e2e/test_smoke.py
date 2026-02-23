"""E2E Smoke Test — 실제 환경 전체 검증.

@pytest.mark.e2e 마커. 실행: pytest tests/e2e/ -v -m e2e

실제 DB + (mock ML) + S3 환경이 필요합니다.
"""

from __future__ import annotations

import os
from datetime import datetime, date
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pytest

from db.crud import (
    create_user,
    insert_photo,
    get_photo,
    get_photo_keyword_count,
    get_embedding,
    get_last_event,
    insert_events,
    update_photo_event_ids,
    bulk_insert_photo_keywords,
    insert_embedding,
    insert_diary,
    get_diary,
    search_photos,
)
from pipeline.utils.geocoder import PlaceInfo


pytestmark = [pytest.mark.e2e, pytest.mark.db]


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _rand_vec(dim: int = 768) -> np.ndarray:
    v = np.random.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
# 1. GPS 사진 전체 흐름
# ---------------------------------------------------------------------------

class TestGPSPhotoSmoke:
    def test_full_flow(self, db_conn, test_user):
        """GPS 사진 → DB 전체 테이블 확인."""
        place = PlaceInfo(
            full_address="서울특별시 강남구 역삼동 테헤란로",
            state="서울특별시",
            city="강남구",
            district="역삼동",
        )

        # 1) 사진 INSERT
        photo_id = insert_photo(
            db_conn, test_user, "s3://smoke/gps.jpg",
            lat=37.508, lon=127.062,
            place_info=place,
            taken_at=datetime(2025, 12, 25, 14, 30),
        )

        # 2) photos: lat, lon, state, city, taken_at 존재
        photo = get_photo(db_conn, photo_id)
        assert photo["latitude"] == pytest.approx(37.508, abs=0.01)
        assert photo["longitude"] == pytest.approx(127.062, abs=0.01)
        assert photo["state"] == "서울특별시"
        assert photo["city"] == "강남구"
        assert photo["taken_at"] is not None

        # 3) keywords 저장
        kw_data = [
            ("person", "person", 0.95),
            ("restaurant", "place", 0.88),
            ("food", "object", 0.82),
        ]
        bulk_insert_photo_keywords(db_conn, photo_id, kw_data)
        assert get_photo_keyword_count(db_conn, photo_id) == 3

        # 4) embedding 저장 (768차원)
        vec = _rand_vec()
        insert_embedding(db_conn, photo_id, vec)
        emb = get_embedding(db_conn, photo_id)
        assert emb is not None
        assert len(emb) == 768

        # 5) events 저장
        events = [{
            "event_ref": 0,
            "user_id": test_user,
            "started_at": datetime(2025, 12, 25, 14, 0),
            "ended_at": datetime(2025, 12, 25, 16, 0),
            "primary_location": "37.508000,127.062000",
            "photo_count": 1,
        }]
        id_map = insert_events(db_conn, events)
        event_id = id_map[0]
        update_photo_event_ids(db_conn, [(event_id, photo_id)])

        photo2 = get_photo(db_conn, photo_id)
        assert photo2["event_id"] == event_id


# ---------------------------------------------------------------------------
# 2. GPS 없는 사진
# ---------------------------------------------------------------------------

class TestNoGPSPhotoSmoke:
    def test_no_gps_flow(self, db_conn, test_user):
        photo_id = insert_photo(
            db_conn, test_user, "s3://smoke/no_gps.jpg",
            lat=None, lon=None,
            taken_at=datetime(2025, 12, 25),
        )
        photo = get_photo(db_conn, photo_id)
        assert photo["latitude"] is None
        assert photo["longitude"] is None

        # 나머지 (keywords, embedding)는 정상
        bulk_insert_photo_keywords(db_conn, photo_id, [("sunset", "object", 0.9)])
        assert get_photo_keyword_count(db_conn, photo_id) == 1

        insert_embedding(db_conn, photo_id, _rand_vec())
        assert get_embedding(db_conn, photo_id) is not None


# ---------------------------------------------------------------------------
# 3. 데이터 무결성 체크
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_embedding_dimension(self, db_conn, test_user):
        """embedding 차원 == 768."""
        pid = insert_photo(db_conn, test_user, "s3://dim.jpg", None, None)
        insert_embedding(db_conn, pid, _rand_vec())
        emb = get_embedding(db_conn, pid)
        assert len(emb) == 768

    def test_keyword_category_values(self, db_conn, test_user):
        """keyword_category는 person/activity/place/object만."""
        pid = insert_photo(db_conn, test_user, "s3://cat.jpg", None, None)
        data = [
            ("person_tag", "person", 0.9),
            ("walk_tag", "activity", 0.8),
            ("beach_tag", "place", 0.7),
            ("car_tag", "object", 0.6),
        ]
        saved = bulk_insert_photo_keywords(db_conn, pid, data)
        assert saved == 4

    def test_importance_range(self, db_conn, test_user):
        """importance 범위: 0 < importance <= 1."""
        pid = insert_photo(db_conn, test_user, "s3://imp.jpg", None, None)
        data = [("tag1", "object", 0.5)]
        bulk_insert_photo_keywords(db_conn, pid, data)
        # DB에서 직접 검증
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT importance FROM photo_keywords WHERE photo_id = %s",
                (pid,),
            )
            rows = cur.fetchall()
            for (imp,) in rows:
                assert 0 < imp <= 1


# ---------------------------------------------------------------------------
# 4. 일기 CRUD smoke
# ---------------------------------------------------------------------------

class TestDiarySmoke:
    def test_diary_create_and_read(self, db_conn, test_user):
        insert_diary(db_conn, test_user, date(2025, 12, 25), "크리스마스 일기!")
        diary = get_diary(db_conn, test_user, date(2025, 12, 25))
        assert diary is not None
        assert "크리스마스" in diary["content"]

    def test_diary_upsert(self, db_conn, test_user):
        insert_diary(db_conn, test_user, date(2025, 12, 26), "원래 내용")
        insert_diary(db_conn, test_user, date(2025, 12, 26), "수정된 내용")
        diary = get_diary(db_conn, test_user, date(2025, 12, 26))
        assert diary["content"] == "수정된 내용"


# ---------------------------------------------------------------------------
# 5. 벡터 검색 smoke
# ---------------------------------------------------------------------------

class TestSearchSmoke:
    def test_vector_search_returns_results(self, db_conn, test_user):
        pid = insert_photo(db_conn, test_user, "s3://search.jpg", None, None)
        vec = _rand_vec()
        insert_embedding(db_conn, pid, vec)

        results = search_photos(db_conn, vec, test_user, limit=5)
        assert len(results) > 0
        assert results[0]["id"] == pid
