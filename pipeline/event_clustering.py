"""
시계열 사진 메타데이터를 이벤트 단위로 분리하는 모듈.

실행:
    python -m pipeline.event_clustering

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
import math
from datetime import datetime, timedelta
from typing import Any

import pandas as pd


EARTH_RADIUS_METERS = 6_371_000
TIME_SPLIT_MINUTES = 120
DISTANCE_SPLIT_METERS = 500


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
    validated["timestamp"] = pd.to_datetime(validated["timestamp"], utc=True)
    validated["latitude"] = pd.to_numeric(validated["latitude"], errors="coerce")
    validated["longitude"] = pd.to_numeric(validated["longitude"], errors="coerce")
    validated = validated.sort_values("timestamp").reset_index(drop=True)
    return validated


def _finalize_event(
    user_id: int,
    event_photos: list[dict],
    event_ref: int,
    existing_event_id: int | None = None,
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
        avg_lat = sum(lat for lat, _ in valid_coords) / len(valid_coords)
        avg_lon = sum(lon for _, lon in valid_coords) / len(valid_coords)
        primary_location = f"{avg_lat:.6f},{avg_lon:.6f}"

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
    time_split_minutes: int,
    distance_split_meters: float,
) -> bool:
    time_gap_minutes = (current["timestamp"] - previous["timestamp"]).total_seconds() / 60
    if time_gap_minutes >= time_split_minutes:
        return True

    if _has_valid_coords(anchor_photo) and _has_valid_coords(current):
        distance_from_anchor_meters = haversine_distance(
            anchor_photo["latitude"],
            anchor_photo["longitude"],
            current["latitude"],
            current["longitude"],
        )
        if distance_from_anchor_meters >= distance_split_meters:
            return True

    return False


def cluster_events(
    photo_df: pd.DataFrame,
    user_id: int = 1,
    time_split_minutes: int = TIME_SPLIT_MINUTES,
    distance_split_meters: float = DISTANCE_SPLIT_METERS,
    last_event: dict | None = None,
) -> dict:
    """
    사진 메타데이터를 이벤트 단위로 클러스터링한다.

    분리 규칙:
    1) 시간 차이가 time_split_minutes 이상이면 분리
    2) 시간 차이가 짧아도 거리 차이가 distance_split_meters 이상이면 분리

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
    df = _validate_input(photo_df)
    if df.empty:
        return {"events": [], "photo_event_links": []}

    events: list[dict] = []
    photo_event_links: list[dict] = []

    event_ref = 0
    current_event: list[dict] = []
    current_existing_event_id: int | None = None
    start_idx = 0

    if last_event and last_event.get("ended_at") is not None:
        first_photo = df.iloc[0].to_dict()
        last_event_ended_at = pd.to_datetime(last_event.get("ended_at"), utc=True)
        anchor_lat, anchor_lon = _parse_primary_location(last_event.get("primary_location"))
        last_event_anchor = {
            "latitude": anchor_lat,
            "longitude": anchor_lon,
            "timestamp": last_event_ended_at,
        }

        can_merge_by_time = (
            (first_photo["timestamp"] - last_event_ended_at).total_seconds() / 60
        ) < time_split_minutes

        can_merge_by_distance = True
        if _has_valid_coords(first_photo) and _has_valid_coords(last_event_anchor):
            distance_from_last_event = haversine_distance(
                last_event_anchor["latitude"],
                last_event_anchor["longitude"],
                first_photo["latitude"],
                first_photo["longitude"],
            )
            can_merge_by_distance = distance_from_last_event < distance_split_meters

        if can_merge_by_time and can_merge_by_distance:
            current_event = [first_photo]
            current_existing_event_id = last_event.get("id")
            start_idx = 1

    if not current_event:
        current_event = [df.iloc[0].to_dict()]
        start_idx = 1

    for idx in range(start_idx, len(df)):
        previous = df.iloc[idx - 1].to_dict()
        current = df.iloc[idx].to_dict()
        anchor_photo = current_event[0]

        if _should_split(
            previous=previous,
            current=current,
            anchor_photo=anchor_photo,
            time_split_minutes=time_split_minutes,
            distance_split_meters=distance_split_meters,
        ):
            finalized = _finalize_event(
                user_id=user_id,
                event_photos=current_event,
                event_ref=event_ref,
                existing_event_id=current_existing_event_id,
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
            continue

        current_event.append(current)

    finalized = _finalize_event(
        user_id=user_id,
        event_photos=current_event,
        event_ref=event_ref,
        existing_event_id=current_existing_event_id,
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
) -> list[tuple[int, str]]:
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
    """일상 체류 + 장거리 이동이 섞인 테스트용 목데이터를 생성한다."""
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
        # Event 2: 2시간 초과 공백으로 분리
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