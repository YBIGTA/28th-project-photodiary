"""pipeline/core/ram_tagger.py:categorize_tag() 단위 테스트.

RAM++ (ram/torch 패키지) 미설치 환경에서도 테스트 가능하도록
ram_tagger가 의존하는 무거운 모듈을 통째로 mock 처리한다.
"""

import sys
from unittest.mock import MagicMock

import pytest

# ram_tagger.py의 무거운 의존성을 mock (torch, ram, PIL)
_mock_torch = MagicMock()
sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("torch.nn", _mock_torch.nn)
sys.modules.setdefault("torch.nn.functional", _mock_torch.nn.functional)
sys.modules.setdefault("torch.backends", _mock_torch.backends)
sys.modules.setdefault("torch.backends.mps", _mock_torch.backends.mps)

_mock_ram = MagicMock()
sys.modules.setdefault("ram", _mock_ram)
sys.modules.setdefault("ram.models", _mock_ram.models)

sys.modules.setdefault("PIL", MagicMock())

# 이제 안전하게 ram_tagger import
from pipeline.core.ram_tagger import categorize_tag


# ---------------------------------------------------------------------------
# 카테고리별 태그 분류
# ---------------------------------------------------------------------------

class TestCategorizePerson:
    @pytest.mark.parametrize("tag", ["person", "woman", "man", "child", "baby", "crowd"])
    def test_person_tags(self, tag):
        assert categorize_tag(tag) == "person"

    def test_person_case_insensitive(self):
        assert categorize_tag("Person") == "person"
        assert categorize_tag("WOMAN") == "person"


class TestCategorizeActivity:
    @pytest.mark.parametrize("tag", ["walk", "swim", "run", "eat", "dance", "cook"])
    def test_activity_tags(self, tag):
        assert categorize_tag(tag) == "activity"


class TestCategorizePlace:
    @pytest.mark.parametrize("tag", ["beach", "mountain", "park", "restaurant", "cafe", "church"])
    def test_place_tags(self, tag):
        assert categorize_tag(tag) == "place"


class TestCategorizeObject:
    @pytest.mark.parametrize("tag", ["dog", "car", "pizza", "laptop", "guitar", "ball"])
    def test_object_fallback(self, tag):
        assert categorize_tag(tag) == "object"

    def test_empty_string(self):
        assert categorize_tag("") == "object"

    def test_unknown_tag(self):
        assert categorize_tag("xyzunknowntag") == "object"


class TestCategorizeEdgeCases:
    def test_whitespace_stripped(self):
        assert categorize_tag("  person  ") == "person"
        assert categorize_tag(" beach ") == "place"

    def test_mixed_case(self):
        assert categorize_tag("Beach") == "place"
        assert categorize_tag("SWIM") == "activity"
