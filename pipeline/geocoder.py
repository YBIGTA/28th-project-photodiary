"""역지오코딩 모듈 — Google Maps / Naver Maps / Nominatim"""

import json
import os
import urllib.request
import urllib.parse
from dataclasses import dataclass, fields


# ─── 공통 출력 클래스 ────────────────────────────────────

@dataclass
class PlaceInfo:
    """역지오코딩 결과"""
    full_address: str = ""
    country: str = ""      # 국가
    state: str = ""        # 시/도
    city: str = ""         # 시/군/구
    district: str = ""     # 동/읍/면
    road: str = ""         # 도로명
    building: str = ""     # 건물/가게 이름
    postcode: str = ""     # 우편번호


def _fetch_json(url, headers=None):
    hdrs = headers or {}
    hdrs.setdefault("User-Agent", "PhotoDiary/1.0")
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


# ─── Google Maps ─────────────────────────────────────────

class GoogleGeocoder:
    """
    Google Maps Reverse Geocoding + Places Nearby Search.
    환경변수: GOOGLE_MAPS_API_KEY
    """

    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GOOGLE_MAPS_API_KEY 환경변수를 설정하세요.\n"
                "  export GOOGLE_MAPS_API_KEY='your-key-here'"
            )

    def reverse_geocode(self, lat, lon):
        place = PlaceInfo()

        # 1) Reverse Geocoding — 주소
        geo_url = (
            f"https://maps.googleapis.com/maps/api/geocode/json"
            f"?latlng={lat},{lon}&language=ko&key={self.api_key}"
        )
        geo_data = _fetch_json(geo_url)

        if geo_data.get("results"):
            top = geo_data["results"][0]
            place.full_address = top.get("formatted_address", "")
            for comp in top.get("address_components", []):
                types = comp.get("types", [])
                name = comp.get("long_name", "")
                if "country" in types:
                    place.country = name
                elif "administrative_area_level_1" in types:
                    place.state = name
                elif "sublocality_level_1" in types or "locality" in types:
                    place.city = name
                elif "sublocality_level_2" in types:
                    place.district = name
                elif "route" in types:
                    place.road = name
                elif "postal_code" in types:
                    place.postcode = name

        # 2) Places API (New) — Nearby Search로 건물/가게 이름
        places_url = "https://places.googleapis.com/v1/places:searchNearby"
        body = json.dumps({
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": 50.0,
                }
            },
            "maxResultCount": 1,
            "languageCode": "ko",
        }).encode()
        places_req = urllib.request.Request(
            places_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.displayName",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(places_req, timeout=10) as resp:
                places_data = json.loads(resp.read().decode())
            places_list = places_data.get("places", [])
            if places_list:
                place.building = places_list[0].get("displayName", {}).get("text", "")
        except Exception:
            pass  # Places 실패해도 주소 결과는 유지

        return place


# ─── Naver Maps ──────────────────────────────────────────

class NaverGeocoder:
    """
    Naver Maps Reverse Geocoding.
    환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
    """

    def __init__(self):
        self.client_id = os.environ.get("NAVER_CLIENT_ID", "")
        self.client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 환경변수를 설정하세요.\n"
                "  export NAVER_CLIENT_ID='your-id'\n"
                "  export NAVER_CLIENT_SECRET='your-secret'"
            )

    def reverse_geocode(self, lat, lon):
        place = PlaceInfo()

        url = (
            f"https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc"
            f"?coords={lon},{lat}&output=json&orders=roadaddr,addr"
        )
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
        }
        data = _fetch_json(url, headers=headers)

        results = data.get("results", [])
        if not results:
            return place

        r = results[0]
        region = r.get("region", {})
        land = r.get("land", {})

        place.country = region.get("area0", {}).get("name", "")
        place.state = region.get("area1", {}).get("name", "")
        place.city = region.get("area2", {}).get("name", "")
        place.district = region.get("area3", {}).get("name", "")

        road_name = land.get("name", "")
        road_num = land.get("number1", "")
        if road_num:
            road_name = f"{road_name} {road_num}"
        place.road = road_name

        # 건물명은 addition0에 들어있음
        addition0 = land.get("addition0", {})
        place.building = addition0.get("value", "")

        # 전체 주소 조합
        parts = [place.state, place.city, place.district, place.road]
        if place.building:
            parts.append(f"({place.building})")
        place.full_address = " ".join(p for p in parts if p)

        return place


# ─── Nominatim (무료 fallback) ───────────────────────────

class NominatimGeocoder:
    """OpenStreetMap Nominatim — API 키 불필요"""

    def reverse_geocode(self, lat, lon):
        place = PlaceInfo()

        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&accept-language=ko"
        )
        data = _fetch_json(url)

        place.full_address = data.get("display_name", "")
        addr = data.get("address", {})
        place.country = addr.get("country", "")
        place.state = addr.get("state", "")
        place.city = addr.get("city", addr.get("county", ""))
        place.district = addr.get("suburb", addr.get("neighbourhood", ""))
        place.road = addr.get("road", "")
        place.postcode = addr.get("postcode", "")
        place.building = addr.get("building", addr.get("amenity", ""))

        return place


# ─── 팩토리 ──────────────────────────────────────────────

def get_geocoder(provider=None):
    """
    provider: "google", "naver", "nominatim"
    None이면 환경변수 기반 자동 선택 (google → naver → nominatim)
    """
    if provider == "google":
        return GoogleGeocoder()
    if provider == "naver":
        return NaverGeocoder()
    if provider == "nominatim":
        return NominatimGeocoder()

    # 자동 선택
    if os.environ.get("GOOGLE_MAPS_API_KEY"):
        return GoogleGeocoder()
    if os.environ.get("NAVER_CLIENT_ID"):
        return NaverGeocoder()
    return NominatimGeocoder()
