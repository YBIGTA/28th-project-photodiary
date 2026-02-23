"""업로드 → 워커 E2E 통합 테스트.

ML 모델(RAM++, Moondream, E5)은 mock. DB는 실제 PostgreSQL.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from db.crud import (
    get_photo,
    get_photo_keyword_count,
    get_embedding,
    get_last_event,
    list_unclustered_photos,
    insert_photo,
)
from pipeline.utils.geocoder import PlaceInfo


pytestmark = pytest.mark.db


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_ram_result(file_path: str):
    """RAM++ extract_tags_batch 결과를 흉내낸다."""
    tag = MagicMock()
    tag.tag_en = "beach"
    tag.confidence = 0.92

    tag2 = MagicMock()
    tag2.tag_en = "person"
    tag2.confidence = 0.85

    result = MagicMock()
    result.file_path = file_path
    result.tags = [tag, tag2]
    return [result]


def _mock_caption_result(file_path: str):
    """Moondream generate_captions_batch 결과를 흉내낸다."""
    result = MagicMock()
    result.file_path = file_path
    result.caption = "A person standing on a beautiful beach"
    return [result]


def _mock_embed_photo(*args, **kwargs):
    """embed_photo 결과를 흉내낸다."""
    vec = np.random.randn(768).astype(np.float32)
    return vec / np.linalg.norm(vec)


# ---------------------------------------------------------------------------
# GPS 사진 워커 E2E
# ---------------------------------------------------------------------------

class TestWorkerWithGPS:
    @patch("pipeline.worker.download_from_s3")
    @patch("pipeline.worker.extract_tags_batch")
    @patch("pipeline.worker.generate_captions_batch")
    @patch("pipeline.worker.unload_moondream")
    @patch("pipeline.worker.embed_photo", side_effect=_mock_embed_photo)
    @patch("pipeline.worker.get_connection")
    def test_full_pipeline(
        self,
        mock_conn,
        mock_embed,
        mock_unload,
        mock_caption,
        mock_ram,
        mock_download,
        db_conn,
        test_user,
    ):
        """GPS 사진 → 워커 실행 → keywords, caption, embedding, event 모두 채워짐."""
        # DB 연결 mock → 실제 test db_conn 사용
        mock_conn.return_value = db_conn

        # 사진 DB에 먼저 삽입 (upload 라우터가 하는 일)
        place = PlaceInfo(
            state="부산광역시", city="해운대구",
            district="우동", full_address="부산 해운대",
        )
        photo_id = insert_photo(
            db_conn, test_user, "photos/1/test_beach.jpg",
            lat=35.158, lon=129.160,
            place_info=place,
            taken_at=datetime(2025, 12, 25, 14, 0),
        )

        # Mock 설정
        mock_download.return_value = "/tmp/fake_test.jpg"
        mock_ram.return_value = _mock_ram_result("/tmp/fake_test.jpg")
        mock_caption.return_value = _mock_caption_result("/tmp/fake_test.jpg")

        # ram_tagger 모듈 mock (VRAM 해제 관련)
        with patch("pipeline.worker.ram_mod", create=True) as mock_ram_mod, \
             patch("os.path.exists", return_value=False):
            mock_ram_mod._model = None

            from pipeline.worker import process_photo_pipeline
            process_photo_pipeline(photo_id, test_user, "photos/1/test_beach.jpg")

        # 검증: keywords
        kw_count = get_photo_keyword_count(db_conn, photo_id)
        assert kw_count >= 1, "키워드가 저장되어야 합니다"

        # 검증: caption
        photo = get_photo(db_conn, photo_id)
        assert photo["caption"] is not None

        # 검증: embedding
        emb = get_embedding(db_conn, photo_id)
        assert emb is not None
        assert len(emb) == 768


# ---------------------------------------------------------------------------
# GPS 없는 사진 워커
# ---------------------------------------------------------------------------

class TestWorkerNoGPS:
    @patch("pipeline.worker.download_from_s3")
    @patch("pipeline.worker.extract_tags_batch")
    @patch("pipeline.worker.generate_captions_batch")
    @patch("pipeline.worker.unload_moondream")
    @patch("pipeline.worker.embed_photo", side_effect=_mock_embed_photo)
    @patch("pipeline.worker.get_connection")
    def test_no_gps_pipeline(
        self,
        mock_conn,
        mock_embed,
        mock_unload,
        mock_caption,
        mock_ram,
        mock_download,
        db_conn,
        test_user,
    ):
        """GPS 없는 사진 → lat/lon=None, 나머지 정상 처리."""
        mock_conn.return_value = db_conn

        photo_id = insert_photo(
            db_conn, test_user, "photos/1/no_gps.jpg",
            lat=None, lon=None,
            taken_at=datetime(2025, 12, 25),
        )

        mock_download.return_value = "/tmp/fake_no_gps.jpg"
        mock_ram.return_value = _mock_ram_result("/tmp/fake_no_gps.jpg")
        mock_caption.return_value = _mock_caption_result("/tmp/fake_no_gps.jpg")

        with patch("pipeline.worker.ram_mod", create=True) as mock_ram_mod, \
             patch("os.path.exists", return_value=False):
            mock_ram_mod._model = None

            from pipeline.worker import process_photo_pipeline
            process_photo_pipeline(photo_id, test_user, "photos/1/no_gps.jpg")

        photo = get_photo(db_conn, photo_id)
        assert photo["latitude"] is None
        assert photo["longitude"] is None
        assert photo["caption"] is not None
