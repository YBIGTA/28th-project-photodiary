"""pipeline/utils/geocoder.py 단위 테스트."""

import os
from dataclasses import fields
from unittest.mock import patch, MagicMock

import pytest

from pipeline.utils.geocoder import (
    PlaceInfo,
    GoogleGeocoder,
    NaverGeocoder,
    NominatimGeocoder,
    get_geocoder,
)


# ---------------------------------------------------------------------------
# PlaceInfo dataclass
# ---------------------------------------------------------------------------

class TestPlaceInfo:
    def test_field_count(self):
        assert len(fields(PlaceInfo)) == 8

    def test_default_values(self):
        p = PlaceInfo()
        for f in fields(p):
            assert getattr(p, f.name) == ""

    def test_partial_init(self):
        p = PlaceInfo(city="서울특별시", district="강남구")
        assert p.city == "서울특별시"
        assert p.district == "강남구"
        assert p.country == ""


# ---------------------------------------------------------------------------
# get_geocoder 팩토리
# ---------------------------------------------------------------------------

class TestGetGeocoder:
    def test_nominatim_when_no_keys(self):
        """API 키 없으면 NominatimGeocoder."""
        env = {
            "GOOGLE_MAPS_API_KEY": "",
            "NAVER_CLIENT_ID": "",
            "NAVER_CLIENT_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=False):
            # 환경변수에서 키를 비움
            os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            os.environ.pop("NAVER_CLIENT_ID", None)
            geocoder = get_geocoder()
            assert isinstance(geocoder, NominatimGeocoder)

    def test_explicit_nominatim(self):
        geocoder = get_geocoder("nominatim")
        assert isinstance(geocoder, NominatimGeocoder)

    def test_explicit_google_requires_key(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}, clear=False):
            os.environ.pop("GOOGLE_MAPS_API_KEY", None)
            with pytest.raises(ValueError):
                get_geocoder("google")

    def test_explicit_naver_requires_keys(self):
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": ""}, clear=False):
            os.environ.pop("NAVER_CLIENT_ID", None)
            os.environ.pop("NAVER_CLIENT_SECRET", None)
            with pytest.raises(ValueError):
                get_geocoder("naver")


# ---------------------------------------------------------------------------
# Google Geocoder mock 응답 파싱
# ---------------------------------------------------------------------------

class TestGoogleGeocoderParsing:
    @patch("pipeline.utils.geocoder._fetch_json")
    def test_reverse_geocode(self, mock_fetch):
        mock_fetch.side_effect = [
            # Geocoding API 응답
            {
                "results": [{
                    "formatted_address": "대한민국 서울특별시 종로구 세종로 1-68",
                    "address_components": [
                        {"long_name": "대한민국", "types": ["country"]},
                        {"long_name": "서울특별시", "types": ["administrative_area_level_1"]},
                        {"long_name": "종로구", "types": ["sublocality_level_1"]},
                        {"long_name": "세종대로", "types": ["route"]},
                        {"long_name": "03154", "types": ["postal_code"]},
                    ],
                }]
            },
        ]

        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
            gc = GoogleGeocoder()

        # Places API 호출을 mock — urllib.request.urlopen 패치
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("pipeline.utils.geocoder._fetch_json", mock_fetch):
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"places":[]}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            place = gc.reverse_geocode(37.5665, 126.9780)

        assert place.country == "대한민국"
        assert place.state == "서울특별시"
        assert "세종대로" in place.road or place.road == "세종대로"
        assert place.postcode == "03154"


# ---------------------------------------------------------------------------
# Naver Geocoder mock 응답 파싱
# ---------------------------------------------------------------------------

class TestNaverGeocoderParsing:
    @patch("pipeline.utils.geocoder._fetch_json")
    def test_reverse_geocode(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [{
                "region": {
                    "area0": {"name": "kr"},
                    "area1": {"name": "서울특별시"},
                    "area2": {"name": "강남구"},
                    "area3": {"name": "역삼동"},
                },
                "land": {
                    "name": "테헤란로",
                    "number1": "521",
                    "addition0": {"value": "파르나스타워"},
                },
            }]
        }

        with patch.dict(os.environ, {
            "NAVER_CLIENT_ID": "test-id",
            "NAVER_CLIENT_SECRET": "test-secret",
        }):
            gc = NaverGeocoder()

        place = gc.reverse_geocode(37.5081, 127.0620)

        assert place.state == "서울특별시"
        assert place.city == "강남구"
        assert place.district == "역삼동"
        assert "테헤란로" in place.road
        assert place.building == "파르나스타워"


# ---------------------------------------------------------------------------
# Nominatim Geocoder mock 응답 파싱
# ---------------------------------------------------------------------------

class TestNominatimGeocoderParsing:
    @patch("pipeline.utils.geocoder._fetch_json")
    def test_reverse_geocode(self, mock_fetch):
        mock_fetch.return_value = {
            "display_name": "경복궁, 세종로, 종로구, 서울특별시, 03045, 대한민국",
            "address": {
                "country": "대한민국",
                "state": "서울특별시",
                "city": "종로구",
                "suburb": "세종로",
                "road": "사직로",
                "postcode": "03045",
                "amenity": "경복궁",
            },
        }

        gc = NominatimGeocoder()
        place = gc.reverse_geocode(37.5796, 126.9770)

        assert place.country == "대한민국"
        assert place.state == "서울특별시"
        assert place.city == "종로구"
        assert place.district == "세종로"
        assert place.building == "경복궁"
        assert place.postcode == "03045"
