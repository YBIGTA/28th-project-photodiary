"""
시계열 사진 메타데이터를 이벤트 단위로 분리하는 모듈.

주의:
    파일명이 숫자(03_)로 시작하여 Python 네이밍 규칙상 단독 모듈 실행이 불가능합니다.
    반드시 아래 방법 중 하나로 실행하세요.

    1) pipeline/run_clustering.py 를 통한 실행 (권장):
           python -m pipeline.run_clustering

    2) importlib 동적 로딩:
           import importlib
           mod = importlib.import_module("pipeline.steps.03_clustering")

입력 DataFrame 필수 컬럼:
    - photo_id
    - timestamp
    - latitude
    - longitude

출력 스키마(events 테이블 기준):
    - user_id
    - started_at
    - ended_at
    - primary_location
    - photo_count

참고로 디버깅/검증을 위해 photo_ids를 함께 반환한다.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# 타임스탬프 이상값 기준
_TS_FUTURE_TOLERANCE = pd.Timedelta(days=1)   # 현재 시각 + 1일 초과면 미래 오류로 간주
_TS_ANCIENT_THRESHOLD = pd.Timestamp("1990-01-01", tz="UTC")  # 디지털 카메라 보급 이전


EARTH_RADIUS_METERS = 6_371_000


@dataclass(frozen=True)
class ClusterConfig:
    """클러스터링 파라미터 설정.

    Attributes
    ----------
    time_split_minutes : int
        이벤트를 분리하는 기본 시간 임계값(분). 기본값 120.
    distance_split_meters : float
        이벤트를 분리하는 거리 임계값(m). 기본값 500.
    stay_distance_meters : float
        '체류(Stay)'로 판단하는 거리 임계값(m). 기본값 50.
        anchor로부터 이 거리 이내면 체류 중으로 보고 시간 임계값을 완화한다.
    stay_time_split_minutes : int
        체류 중일 때 적용하는 완화된 시간 임계값(분). 기본값 720(12시간).
    """

    time_split_minutes: int = 120
    distance_split_meters: float = 500
    stay_distance_meters: float = 50
    stay_time_split_minutes: int = 720


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 좌표 사이의 거리(m)를 Haversine 공식으로 계산한다."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c


def _is_missing_coord(value: Any) -> bool:
    return value is None or pd.isna(value)


def _has_valid_coords(photo: dict) -> bool:
    return not _is_missing_coord(photo.get("latitude")) and not _is_missing_coord(photo.get("longitude"))


def _find_anchor(event_photos: list[dict]) -> dict:
    """이벤트 내 GPS 좌표가 있는 첫 번째 사진을 anchor 로 반환.

    GPS 사진이 한 장도 없으면 첫 번째 사진을 반환한다.
    이벤트 첫 사진에 GPS 가 없더라도 이후 GPS 사진을 anchor 로 활용할 수 있어
    거리 기반 분리 판정의 정확도가 높아진다.
    """
    for photo in event_photos:
        if _has_valid_coords(photo):
            return photo
    return event_photos[0]


def _parse_primary_location(primary_location: str | None) -> tuple[float | None, float | None]:
    if not primary_location:
        return None, None

    try:
        lat_str, lon_str = primary_location.split(",", 1)
        return float(lat_str), float(lon_str)
    except (TypeError, ValueError):
        return None, None


def _validate_input(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"photo_id", "timestamp", "latitude", "longitude"}
    missing = required_columns - set(df.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"입력 DataFrame에 필수 컬럼이 없습니다: {missing_text}")

    validated = df.copy()
    # errors="coerce" : 파싱 불가한 값은 NaT 로 변환 (기존 코드는 에러 전파)
    validated["timestamp"] = pd.to_datetime(validated["timestamp"], utc=True, errors="coerce")
    validated["latitude"] = pd.to_numeric(validated["latitude"], errors="coerce")
    validated["longitude"] = pd.to_numeric(validated["longitude"], errors="coerce")

    # ── edge case 1: 타임스탬프 없음(NaT) ──
    nat_mask = validated["timestamp"].isna()
    if nat_mask.any():
        logger.warning(
            "타임스탬프가 없거나 파싱 불가한 사진 %d장 제외: photo_id=%s",
            nat_mask.sum(),
            validated.loc[nat_mask, "photo_id"].tolist(),
        )
        validated = validated[~nat_mask]

    # ── edge case 2: 미래 시간 (카메라 날짜 오류) ──
    now_utc = pd.Timestamp.now(tz="UTC")
    future_mask = validated["timestamp"] > now_utc + _TS_FUTURE_TOLERANCE
    if future_mask.any():
        logger.warning(
            "미래 시간으로 설정된 사진 %d장 제외 (카메라 날짜 오류 의심): photo_id=%s, timestamps=%s",
            future_mask.sum(),
            validated.loc[future_mask, "photo_id"].tolist(),
            validated.loc[future_mask, "timestamp"].tolist(),
        )
        validated = validated[~future_mask]

    # ── edge case 3: 디지털 카메라 보급 이전 날짜 (카메라 초기화 의심) ──
    ancient_mask = validated["timestamp"] < _TS_ANCIENT_THRESHOLD
    if ancient_mask.any():
        logger.warning(
            "1990년 이전 타임스탬프 사진 %d장 제외 (카메라 날짜 초기화 의심): photo_id=%s, timestamps=%s",
            ancient_mask.sum(),
            validated.loc[ancient_mask, "photo_id"].tolist(),
            validated.loc[ancient_mask, "timestamp"].tolist(),
        )
        validated = validated[~ancient_mask]

    validated = validated.sort_values("timestamp").reset_index(drop=True)
    return validated


def _finalize_event(
    user_id: int,
    event_photos: list[dict],
    event_ref: int,
    existing_event_id: int | None = None,
    merge_location: tuple[float, float] | None = None,
    merge_gps_count: int = 0,
) -> dict:
    start_ts = event_photos[0]["timestamp"]
    end_ts = event_photos[-1]["timestamp"]

    valid_coords = [
        (photo["latitude"], photo["longitude"])
        for photo in event_photos
        if _has_valid_coords(photo)
    ]

    primary_location = None
    if valid_coords:
        new_avg_lat = sum(lat for lat, _ in valid_coords) / len(valid_coords)
        new_avg_lon = sum(lon for _, lon in valid_coords) / len(valid_coords)

        # 가중 평균: GPS 유효 사진 수 기준으로 가중 결합
        if merge_location and merge_location[0] is not None and merge_gps_count > 0:
            old_lat, old_lon = merge_location
            total_weight = merge_gps_count + len(valid_coords)
            avg_lat = (old_lat * merge_gps_count + new_avg_lat * len(valid_coords)) / total_weight
            avg_lon = (old_lon * merge_gps_count + new_avg_lon * len(valid_coords)) / total_weight
        else:
            avg_lat = new_avg_lat
            avg_lon = new_avg_lon

        primary_location = f"{avg_lat:.6f},{avg_lon:.6f}"
    elif merge_location and merge_location[0] is not None:
        # 새 사진에 GPS가 없지만 기존 이벤트에는 위치가 있는 경우
        primary_location = f"{merge_location[0]:.6f},{merge_location[1]:.6f}"

    return {
        "event_ref": event_ref,
        "existing_event_id": existing_event_id,
        "user_id": user_id,
        "started_at": start_ts,
        "ended_at": end_ts,
        "primary_location": primary_location,
        "photo_count": len(event_photos),
        "photo_ids": [photo["photo_id"] for photo in event_photos],
    }


def _should_split(
    previous: dict,
    current: dict,
    anchor_photo: dict,
    config: ClusterConfig,
) -> bool:
    time_gap_minutes = (current["timestamp"] - previous["timestamp"]).total_seconds() / 60

    # 거리 계산 (GPS 유효 시)
    distance_from_anchor = None
    if _has_valid_coords(anchor_photo) and _has_valid_coords(current):
        distance_from_anchor = haversine_distance(
            anchor_photo["latitude"],
            anchor_photo["longitude"],
            current["latitude"],
            current["longitude"],
        )

    # 거리 기반 분리: anchor에서 멀리 떨어지면 무조건 분리
    if distance_from_anchor is not None and distance_from_anchor >= config.distance_split_meters:
        return True

    # 체류(Stay) 판정: anchor 근처이면 시간 임계값 완화
    if distance_from_anchor is not None and distance_from_anchor < config.stay_distance_meters:
        effective_time_split = config.stay_time_split_minutes
    else:
        effective_time_split = config.time_split_minutes

    if time_gap_minutes >= effective_time_split:
        return True

    return False


def cluster_events(
    photo_df: pd.DataFrame,
    user_id: int = 1,
    last_event: dict | None = None,
    config: ClusterConfig | None = None,
) -> dict:
    """
    사진 메타데이터를 이벤트 단위로 클러스터링한다.

    분리 규칙:
    1) 거리 차이가 distance_split_meters 이상이면 분리
    2) 체류(Stay) 상태(anchor에서 stay_distance_meters 이내)이면
       시간 임계값을 stay_time_split_minutes로 완화
    3) 그 외 시간 차이가 time_split_minutes 이상이면 분리

    Returns
    -------
    dict
        {
            "events": [event_dict, ...],
            "photo_event_links": [
                {"photo_id": <id>, "event_ref": <int>, "existing_event_id": <int|None>},
                ...
            ]
        }
    """
    if config is None:
        config = ClusterConfig()

    df = _validate_input(photo_df)
    if df.empty:
        return {"events": [], "photo_event_links": []}

    events: list[dict] = []
    photo_event_links: list[dict] = []

    event_ref = 0
    current_event: list[dict] = []
    current_existing_event_id: int | None = None
    start_idx = 0

    # 병합(Merge) 관련 상태
    merge_anchor: dict | None = None
    merge_location: tuple[float, float] | None = None
    merge_gps_count: int = 0

    if last_event and last_event.get("ended_at") is not None:
        first_photo = df.iloc[0].to_dict()
        last_event_ended_at = pd.to_datetime(last_event.get("ended_at"), utc=True)
        anchor_lat, anchor_lon = _parse_primary_location(last_event.get("primary_location"))
        last_event_anchor = {
            "latitude": anchor_lat,
            "longitude": anchor_lon,
            "timestamp": last_event_ended_at,
        }

        # 거리 체크 + 체류 판정으로 merge 시간 임계값 결정
        can_merge_by_distance = True
        merge_time_threshold = config.time_split_minutes

        if _has_valid_coords(first_photo) and _has_valid_coords(last_event_anchor):
            dist = haversine_distance(
                last_event_anchor["latitude"],
                last_event_anchor["longitude"],
                first_photo["latitude"],
                first_photo["longitude"],
            )
            can_merge_by_distance = dist < config.distance_split_meters
            if dist < config.stay_distance_meters:
                merge_time_threshold = config.stay_time_split_minutes

        time_gap = (first_photo["timestamp"] - last_event_ended_at).total_seconds() / 60
        can_merge_by_time = time_gap < merge_time_threshold

        if can_merge_by_time and can_merge_by_distance:
            current_event = [first_photo]
            current_existing_event_id = last_event.get("id")
            # DESIGN-1: 기존 이벤트의 위치를 anchor로 유지
            merge_anchor = last_event_anchor
            if anchor_lat is not None and anchor_lon is not None:
                merge_location = (anchor_lat, anchor_lon)
            # P0: Null Safety — None과 0을 구분 (0은 유효한 값)
            # P1: GPS 유효 사진 수 우선, None일 때만 photo_count로 폴백
            _gps = last_event.get("gps_photo_count")
            _total = last_event.get("photo_count")
            merge_gps_count = _gps if _gps is not None else (_total if _total is not None else 0)
            start_idx = 1

    if not current_event:
        current_event = [df.iloc[0].to_dict()]
        start_idx = 1

    for idx in range(start_idx, len(df)):
        previous = df.iloc[idx - 1].to_dict()
        current = df.iloc[idx].to_dict()
        # DESIGN-1: 병합 중이면 기존 이벤트의 anchor 사용,
        # 그 외에는 현재 이벤트 내 GPS 있는 첫 사진을 anchor 로 사용
        anchor_photo = merge_anchor if merge_anchor is not None else _find_anchor(current_event)

        if _should_split(
            previous=previous,
            current=current,
            anchor_photo=anchor_photo,
            config=config,
        ):
            finalized = _finalize_event(
                user_id=user_id,
                event_photos=current_event,
                event_ref=event_ref,
                existing_event_id=current_existing_event_id,
                merge_location=merge_location,
                merge_gps_count=merge_gps_count,
            )
            events.append(finalized)
            for photo_id in finalized["photo_ids"]:
                photo_event_links.append(
                    {
                        "photo_id": photo_id,
                        "event_ref": event_ref,
                        "existing_event_id": current_existing_event_id,
                    }
                )

            event_ref += 1
            current_event = [current]
            current_existing_event_id = None
            merge_anchor = None
            merge_location = None
            merge_gps_count = 0
            continue

        current_event.append(current)

    finalized = _finalize_event(
        user_id=user_id,
        event_photos=current_event,
        event_ref=event_ref,
        existing_event_id=current_existing_event_id,
        merge_location=merge_location,
        merge_gps_count=merge_gps_count,
    )
    events.append(finalized)
    for photo_id in finalized["photo_ids"]:
        photo_event_links.append(
            {
                "photo_id": photo_id,
                "event_ref": event_ref,
                "existing_event_id": current_existing_event_id,
            }
        )

    return {
        "events": events,
        "photo_event_links": photo_event_links,
    }


def resolve_photo_event_updates(
    cluster_result: dict,
    inserted_event_ids_by_ref: dict[int, int],
) -> list[tuple[int, int]]:
    """
    cluster_events 반환값과 신규 이벤트 INSERT 결과를 바탕으로
    photos.event_id 업데이트용 매핑을 만든다.
    """
    updates: list[tuple[int, int]] = []

    for link in cluster_result.get("photo_event_links", []):
        event_id = link.get("existing_event_id")
        if event_id is None:
            event_id = inserted_event_ids_by_ref[link["event_ref"]]
        updates.append((event_id, link["photo_id"]))

    return updates


def build_mock_photo_data() -> pd.DataFrame:
    """일상 체류 + 장거리 이동 + 집 체류가 섞인 테스트용 목데이터를 생성한다."""
    base_time = datetime(2026, 2, 13, 9, 0, 0)

    records = [
        # Event 1: 강남 근처 체류
        {
            "photo_id": "p1",
            "timestamp": base_time,
            "latitude": 37.498095,
            "longitude": 127.027610,
        },
        {
            "photo_id": "p2",
            "timestamp": base_time + timedelta(minutes=25),
            "latitude": 37.498500,
            "longitude": 127.028000,
        },
        {
            "photo_id": "p3",
            "timestamp": base_time + timedelta(minutes=50),
            "latitude": 37.497900,
            "longitude": 127.027300,
        },
        # Event 2: 2시간 초과 공백 + 장소 이동 → 분리
        {
            "photo_id": "p4",
            "timestamp": base_time + timedelta(hours=3, minutes=20),
            "latitude": 37.566610,
            "longitude": 126.978388,
        },
        {
            "photo_id": "p5",
            "timestamp": base_time + timedelta(hours=3, minutes=45),
            "latitude": 37.565800,
            "longitude": 126.978100,
        },
        # Event 3: 짧은 시간 내 1km+ 이동으로 분리
        {
            "photo_id": "p6",
            "timestamp": base_time + timedelta(hours=4, minutes=5),
            "latitude": 37.579617,
            "longitude": 126.977041,
        },
        {
            "photo_id": "p7",
            "timestamp": base_time + timedelta(hours=4, minutes=35),
            "latitude": 37.580000,
            "longitude": 126.976800,
        },
        # Stay 테스트: 집(경복궁 부근)에서 3시간 후 다시 사진 → 체류이므로 Event 3에 유지
        {
            "photo_id": "p8",
            "timestamp": base_time + timedelta(hours=7, minutes=35),
            "latitude": 37.579650,
            "longitude": 126.977100,
        },
    ]

    return pd.DataFrame(records)


def _serialize_for_print(events: list[dict]) -> list[dict]:
    serialized = []
    for event in events:
        copied = dict(event)
        copied["started_at"] = copied["started_at"].isoformat()
        copied["ended_at"] = copied["ended_at"].isoformat()
        serialized.append(copied)
    return serialized


if __name__ == "__main__":
    mock_df = build_mock_photo_data()
    clustered = cluster_events(mock_df, user_id=1)
    printable = {
        "events": _serialize_for_print(clustered["events"]),
        "photo_event_links": clustered["photo_event_links"],
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))
