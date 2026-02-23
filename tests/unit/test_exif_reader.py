"""pipeline/utils/exif_reader.py 단위 테스트."""

import os
from datetime import datetime

import pytest

from pipeline.utils.exif_reader import (
    get_exif_data,
    get_gps_info,
    get_lat_lon,
    get_taken_at,
    convert_to_degrees,
)


# ---------------------------------------------------------------------------
# convert_to_degrees
# ---------------------------------------------------------------------------

class TestConvertToDegrees:
    def test_simple(self):
        # (37도, 30분, 0초) → 37.5
        assert convert_to_degrees((37, 30, 0)) == pytest.approx(37.5)

    def test_with_seconds(self):
        # (37도, 33분, 57.6초)
        expected = 37 + 33 / 60 + 57.6 / 3600
        assert convert_to_degrees((37, 33, 57.6)) == pytest.approx(expected)

    def test_zero(self):
        assert convert_to_degrees((0, 0, 0)) == 0.0


# ---------------------------------------------------------------------------
# get_exif_data
# ---------------------------------------------------------------------------

class TestGetExifData:
    def test_jpeg_with_exif(self, sample_gps_jpg):
        exif = get_exif_data(sample_gps_jpg)
        assert exif is not None

    def test_png_no_exif(self, sample_no_exif_png):
        exif = get_exif_data(sample_no_exif_png)
        assert exif is None


# ---------------------------------------------------------------------------
# get_gps_info + get_lat_lon
# ---------------------------------------------------------------------------

class TestGPSExtraction:
    def test_gps_present(self, sample_gps_jpg):
        exif = get_exif_data(sample_gps_jpg)
        gps_info = get_gps_info(exif)
        assert gps_info, "GPS 정보가 추출되어야 합니다"

        lat, lon = get_lat_lon(gps_info)
        assert lat is not None
        assert lon is not None
        # 서울 근처 좌표인지 대략 확인
        assert 37.0 < lat < 38.0
        assert 126.0 < lon < 128.0

    def test_no_gps(self, sample_no_gps_jpg):
        exif = get_exif_data(sample_no_gps_jpg)
        gps_info = get_gps_info(exif)
        # GPS 정보 없음 → 빈 dict
        assert not gps_info

    def test_south_west_hemisphere(self):
        """남반구/서반구 좌표 → 음수 값."""
        gps_info = {
            "GPSLatitude": (33, 51, 54),
            "GPSLatitudeRef": "S",
            "GPSLongitude": (151, 12, 36),
            "GPSLongitudeRef": "W",
        }
        lat, lon = get_lat_lon(gps_info)
        assert lat < 0, "남반구는 음수"
        assert lon < 0, "서반구는 음수"

    def test_north_east_hemisphere(self):
        """북반구/동반구 좌표 → 양수 값."""
        gps_info = {
            "GPSLatitude": (37, 33, 57),
            "GPSLatitudeRef": "N",
            "GPSLongitude": (126, 58, 40),
            "GPSLongitudeRef": "E",
        }
        lat, lon = get_lat_lon(gps_info)
        assert lat > 0
        assert lon > 0


# ---------------------------------------------------------------------------
# get_taken_at
# ---------------------------------------------------------------------------

class TestGetTakenAt:
    def test_taken_at_present(self, sample_gps_jpg):
        exif = get_exif_data(sample_gps_jpg)
        taken_at = get_taken_at(exif)
        assert taken_at is not None
        assert isinstance(taken_at, datetime)
        assert taken_at.year == 2025
        assert taken_at.month == 12

    def test_taken_at_no_gps_jpg(self, sample_no_gps_jpg):
        """GPS가 없어도 촬영시각은 존재."""
        exif = get_exif_data(sample_no_gps_jpg)
        taken_at = get_taken_at(exif)
        assert taken_at is not None
