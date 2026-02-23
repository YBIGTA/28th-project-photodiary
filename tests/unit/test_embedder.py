"""pipeline/core/embedder.py 단위 테스트.

sentence_transformers 미설치 환경에서도 순수 함수 테스트 가능하도록
무거운 의존성을 mock 처리한다.
"""

import sys
from unittest.mock import MagicMock

import pytest

# sentence_transformers mock (build_*_text 순수 함수 테스트용)
_mock_st = MagicMock()
sys.modules.setdefault("sentence_transformers", _mock_st)

from pipeline.core.embedder import (
    build_photo_text,
    build_query_text,
    EMBEDDING_DIM,
)


# ---------------------------------------------------------------------------
# build_photo_text — 순수 함수, mock 불필요
# ---------------------------------------------------------------------------

class TestBuildPhotoText:
    def test_full_input(self):
        text = build_photo_text(
            keywords=["kw1", "kw2"],
            place_parts={"city": "서울", "district": "강남구"},
            caption="사람들이 식사하는 장면",
        )
        assert text.startswith("passage: ")
        assert "kw1 kw2" in text
        assert "사람들이 식사하는 장면" in text
        assert "서울 강남구" in text
        # 구분자 | 확인
        assert " | " in text

    def test_keywords_only(self):
        text = build_photo_text(keywords=["beach", "sunset"])
        assert text == "passage: beach sunset"

    def test_caption_only(self):
        text = build_photo_text(keywords=[], caption="A beautiful sunset")
        assert text == "passage: A beautiful sunset"

    def test_place_only(self):
        text = build_photo_text(
            keywords=[],
            place_parts={"state": "부산광역시", "district": "해운대구"},
        )
        assert "부산광역시 해운대구" in text

    def test_empty_input(self):
        text = build_photo_text(keywords=[])
        assert text == "passage: "

    def test_partial_place_parts(self):
        """일부 장소 필드만 있는 경우."""
        text = build_photo_text(
            keywords=["pizza"],
            place_parts={"city": "부산", "building": "이재모피자", "state": None},
        )
        assert "부산" in text
        assert "이재모피자" in text

    def test_caption_whitespace_stripped(self):
        text = build_photo_text(keywords=[], caption="  caption with spaces  ")
        assert "caption with spaces" in text

    def test_none_caption_ignored(self):
        text = build_photo_text(keywords=["tag1"], caption=None)
        assert text == "passage: tag1"


# ---------------------------------------------------------------------------
# build_query_text
# ---------------------------------------------------------------------------

class TestBuildQueryText:
    def test_basic(self):
        assert build_query_text("부산 피자") == "query: 부산 피자"

    def test_empty_query(self):
        assert build_query_text("") == "query: "

    def test_korean_query(self):
        result = build_query_text("제주도에서 바다 사진")
        assert result.startswith("query: ")
        assert "제주도" in result


# ---------------------------------------------------------------------------
# embed_photo / embed_query — 실제 모델 로드 필요 (slow 마킹)
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestEmbedWithModel:
    def test_embed_photo_shape(self):
        import numpy as np
        from pipeline.core.embedder import embed_photo

        vec = embed_photo(
            keywords=["피자", "크리스마스트리"],
            place_parts={"city": "부산광역시"},
        )
        assert vec.shape == (EMBEDDING_DIM,)

    def test_embed_photo_normalized(self):
        import numpy as np
        from pipeline.core.embedder import embed_photo

        vec = embed_photo(keywords=["test"])
        norm = np.linalg.norm(vec)
        assert norm == pytest.approx(1.0, abs=0.01)

    def test_embed_query_shape(self):
        import numpy as np
        from pipeline.core.embedder import embed_query

        vec = embed_query("부산 피자")
        assert vec.shape == (EMBEDDING_DIM,)

    def test_similarity_ranking(self):
        """관련 쿼리가 비관련 쿼리보다 유사도가 높아야 함."""
        import numpy as np
        from pipeline.core.embedder import embed_photo, embed_query

        photo_vec = embed_photo(
            keywords=["피자", "식사"],
            place_parts={"city": "부산광역시"},
        )
        related = embed_query("부산에서 피자 먹은 사진")
        unrelated = embed_query("제주도에서 수영한 사진")

        sim_related = np.dot(photo_vec, related)
        sim_unrelated = np.dot(photo_vec, unrelated)
        assert sim_related > sim_unrelated
