"""pipeline/steps/02_tagging.py:categorize_tag() 단위 테스트.

RAM++ (ram/torch 패키지) 미설치 환경에서도 테스트 가능하도록
02_tagging 가 의존하는 무거운 모듈을 통째로 mock 처리한다.
"""

import importlib
import sys
from unittest.mock import MagicMock

import pytest

# ram_tagger 모듈 자체를 mock (torch, ram 등 무거운 의존성 우회)
_mock_ram_tagger = MagicMock()
_mock_ram_tagger.extract_tags_batch = MagicMock()
_mock_ram_tagger.ImageTagResult = MagicMock()
_mock_ram_tagger.TagResult = MagicMock()
sys.modules["pipeline.core.ram_tagger"] = _mock_ram_tagger

# 이제 안전하게 02_tagging import
tagging = importlib.import_module("pipeline.steps.02_tagging")
categorize_tag = tagging.categorize_tag


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
