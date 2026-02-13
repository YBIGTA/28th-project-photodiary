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


def _validate_input(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"photo_id", "timestamp", "latitude", "longitude"}
    missing = required_columns - set(df.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"입력 DataFrame에 필수 컬럼이 없습니다: {missing_text}")

    validated = df.copy()
    validated["timestamp"] = pd.to_datetime(validated["timestamp"], utc=True)
    validated = validated.sort_values("timestamp").reset_index(drop=True)
    return validated


def _finalize_event(user_id: int, event_photos: list[dict]) -> dict:
    start_ts = event_photos[0]["timestamp"]
    end_ts = event_photos[-1]["timestamp"]
    avg_lat = sum(photo["latitude"] for photo in event_photos) / len(event_photos)
    avg_lon = sum(photo["longitude"] for photo in event_photos) / len(event_photos)

    return {
        "user_id": user_id,
        "started_at": start_ts,
        "ended_at": end_ts,
        "primary_location": f"{avg_lat:.6f},{avg_lon:.6f}",
        "photo_count": len(event_photos),
        "photo_ids": [photo["photo_id"] for photo in event_photos],
    }


def cluster_events(
    photo_df: pd.DataFrame,
    user_id: int = 1,
    time_split_minutes: int = TIME_SPLIT_MINUTES,
    distance_split_meters: float = DISTANCE_SPLIT_METERS,
) -> list[dict]:
    """
    사진 메타데이터를 이벤트 단위로 클러스터링한다.

    분리 규칙:
    1) 시간 차이가 time_split_minutes 이상이면 분리
    2) 시간 차이가 짧아도 거리 차이가 distance_split_meters 이상이면 분리
    """
    df = _validate_input(photo_df)
    if df.empty:
        return []

    events: list[dict] = []
    current_event: list[dict] = [df.iloc[0].to_dict()]

    for idx in range(1, len(df)):
        previous = df.iloc[idx - 1]
        current = df.iloc[idx]

        anchor_photo = current_event[0]
        time_gap_minutes = (current["timestamp"] - previous["timestamp"]).total_seconds() / 60
        distance_from_anchor_meters = haversine_distance(
            anchor_photo["latitude"],
            anchor_photo["longitude"],
            current["latitude"],
            current["longitude"],
        )

        should_split = (
            time_gap_minutes >= time_split_minutes
            or distance_from_anchor_meters >= distance_split_meters
        )

        if should_split:
            events.append(_finalize_event(user_id=user_id, event_photos=current_event))
            current_event = [current.to_dict()]
            continue

        current_event.append(current.to_dict())

    if current_event:
        events.append(_finalize_event(user_id=user_id, event_photos=current_event))

    return events


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
    print(json.dumps(_serialize_for_print(clustered), ensure_ascii=False, indent=2))