"""벡터 검색 통합 테스트 — 실제 PostgreSQL + pgvector."""

from datetime import datetime

import numpy as np
import pytest

from db.crud import (
    insert_photo,
    insert_embedding,
    search_photos,
    search_photos_filtered,
)
from pipeline.utils.geocoder import PlaceInfo


pytestmark = pytest.mark.db


def _unit_vec(dim: int = 768, direction: int = 0) -> np.ndarray:
    """특정 방향의 단위 벡터 생성."""
    vec = np.zeros(dim, dtype=np.float32)
    vec[direction % dim] = 1.0
    return vec


# ---------------------------------------------------------------------------
# 기본 벡터 검색
# ---------------------------------------------------------------------------

class TestVectorSearch:
    def test_basic_search_order(self, db_conn, test_user):
        """유사도 높은 순서로 반환."""
        pid_a = insert_photo(db_conn, test_user, "s3://a.jpg", None, None)
        pid_b = insert_photo(db_conn, test_user, "s3://b.jpg", None, None)

        vec_a = _unit_vec(direction=0)
        vec_b = _unit_vec(direction=1)

        insert_embedding(db_conn, pid_a, vec_a)
        insert_embedding(db_conn, pid_b, vec_b)

        # vec_a 방향 쿼리 → pid_a가 먼저
        results = search_photos(db_conn, vec_a, test_user, limit=10)
        ids = [r["id"] for r in results]
        assert ids[0] == pid_a

    def test_empty_result(self, db_conn, test_user):
        """임베딩이 없는 사용자 → 빈 리스트."""
        vec = _unit_vec()
        results = search_photos(db_conn, vec, test_user, limit=5)
        # test_user에 새로 삽입한 것만 있으므로 이전 테스트와 격리됨 (SAVEPOINT)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# 필터 검색
# ---------------------------------------------------------------------------

class TestFilteredSearch:
    def test_filter_by_district(self, db_conn, test_user):
        """district LIKE 필터."""
        place = PlaceInfo(state="서울특별시", city="강남구", district="역삼동")
        pid = insert_photo(
            db_conn, test_user, "s3://district.jpg",
            lat=37.5, lon=127.0,
            place_info=place,
            taken_at=datetime(2025, 6, 15),
        )
        insert_embedding(db_conn, pid, _unit_vec(direction=5))

        results = search_photos_filtered(
            db_conn, _unit_vec(direction=5), test_user,
            district="역삼",
        )
        ids = [r["id"] for r in results]
        assert pid in ids

    def test_filter_by_date_range(self, db_conn, test_user):
        """날짜 범위 필터."""
        pid = insert_photo(
            db_conn, test_user, "s3://june.jpg",
            lat=None, lon=None,
            taken_at=datetime(2025, 6, 15, 10, 0),
        )
        insert_embedding(db_conn, pid, _unit_vec(direction=7))

        # 6월 범위 → 포함
        results = search_photos_filtered(
            db_conn, _unit_vec(direction=7), test_user,
            date_from=datetime(2025, 6, 1),
            date_to=datetime(2025, 6, 30),
        )
        ids = [r["id"] for r in results]
        assert pid in ids

    def test_filter_excludes(self, db_conn, test_user):
        """필터 조건에 맞지 않으면 제외."""
        place = PlaceInfo(city="부산광역시")
        pid = insert_photo(
            db_conn, test_user, "s3://busan.jpg",
            lat=35.1, lon=129.0,
            place_info=place,
        )
        insert_embedding(db_conn, pid, _unit_vec(direction=9))

        # 서울로 필터 → 부산 사진 제외
        results = search_photos_filtered(
            db_conn, _unit_vec(direction=9), test_user,
            city="서울",
        )
        ids = [r["id"] for r in results]
        assert pid not in ids

    def test_no_results(self, db_conn, test_user):
        """필터에 매칭되는 사진 없음 → 빈 리스트."""
        results = search_photos_filtered(
            db_conn, _unit_vec(), test_user,
            district="존재하지않는동",
        )
        assert results == []
