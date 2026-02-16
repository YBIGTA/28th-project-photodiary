from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import sys
import os
import time
from datetime import datetime

from pipeline.geocoder import get_geocoder, PlaceInfo


def get_exif_data(image_path):
    """이미지에서 EXIF 데이터 추출"""
    image = Image.open(image_path)
    exif_data = image._getexif()
    if exif_data is None:
        return None
    return exif_data


def get_gps_info(exif_data):
    """EXIF 데이터에서 GPS 관련 정보만 추출"""
    gps_info = {}
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, tag_id)
        if tag_name == "GPSInfo":
            for gps_tag_id, gps_value in value.items():
                gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                gps_info[gps_tag_name] = gps_value
    return gps_info


def convert_to_degrees(value):
    """GPS 좌표를 도(degree) 단위로 변환"""
    d, m, s = value
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def get_lat_lon(gps_info):
    """GPS 정보에서 위도/경도 계산"""
    lat = None
    lon = None

    if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
        lat = convert_to_degrees(gps_info["GPSLatitude"])
        if gps_info["GPSLatitudeRef"] == "S":
            lat = -lat

    if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
        lon = convert_to_degrees(gps_info["GPSLongitude"])
        if gps_info["GPSLongitudeRef"] == "W":
            lon = -lon

    return lat, lon


def get_taken_at(exif_data):
    """EXIF DateTimeOriginal → datetime 객체 (없으면 None)"""
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, tag_id)
        if tag_name in ("DateTimeOriginal", "DateTime"):
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
            except (ValueError, TypeError):
                pass
    return None


def analyze_photo(image_path, geocoder=None):
    """사진 한 장 분석"""
    filename = os.path.basename(image_path)
    print(f"\n{'='*60}")
    print(f"📷 파일: {filename}")
    print(f"{'='*60}")

    exif_data = get_exif_data(image_path)
    if exif_data is None:
        print("  EXIF 데이터 없음!")
        return None

    # 촬영 시각
    taken_at = get_taken_at(exif_data)
    if taken_at:
        print(f"\n  [촬영 시각] {taken_at}")

    gps_info = get_gps_info(exif_data)
    if not gps_info:
        print("  GPS 데이터 없음!")
        return None

    print(f"\n  [GPS 원본 데이터]")
    for key, value in gps_info.items():
        print(f"    {key}: {value}")

    lat, lon = get_lat_lon(gps_info)
    place = None
    if lat is not None and lon is not None:
        print(f"\n  [변환된 좌표]")
        print(f"    위도(Latitude):  {lat:.6f}")
        print(f"    경도(Longitude): {lon:.6f}")
        print(f"    Google Maps: https://www.google.com/maps?q={lat},{lon}")

        if geocoder:
            try:
                place = geocoder.reverse_geocode(lat, lon)
                labels = {
                    "full_address": "전체 주소",
                    "country": "국가", "state": "시/도",
                    "city": "시/군/구", "district": "동/읍/면",
                    "road": "도로", "building": "건물/가게",
                    "postcode": "우편번호",
                }
                print(f"\n  [장소 이름]")
                for field_name, label in labels.items():
                    val = getattr(place, field_name, "")
                    if val:
                        print(f"    {label}: {val}")
            except Exception as e:
                print(f"\n  [장소 조회 실패] {e}")
            time.sleep(1)

    return {"gps_raw": gps_info, "lat": lat, "lon": lon, "place": place, "taken_at": taken_at}


if __name__ == "__main__":
    photo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    photos = [
        os.path.join(photo_dir, f)
        for f in os.listdir(photo_dir)
        if f.lower().endswith((".jpeg", ".jpg", ".png", ".heic"))
    ]

    if not photos:
        print("이미지 파일을 찾을 수 없습니다.")
        sys.exit(1)

    geocoder = get_geocoder()  # 환경변수 기반 자동 선택
    provider = type(geocoder).__name__
    print("사진 GPS 데이터 추출기")
    print(f"총 {len(photos)}개 사진 발견")
    print(f"역지오코딩: {provider}")

    for photo in sorted(photos):
        analyze_photo(photo, geocoder)

    print(f"\n{'='*60}")
    print("완료!")
