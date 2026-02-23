"""pipeline/steps/03_clustering.py 단위 테스트 — 가장 핵심 테스트."""

import importlib
from datetime import datetime, timedelta

import pandas as pd
import pytest

clustering = importlib.import_module("pipeline.steps.03_clustering")
haversine_distance = clustering.haversine_distance
cluster_events = clustering.cluster_events
resolve_photo_event_updates = clustering.resolve_photo_event_updates
build_mock_photo_data = clustering.build_mock_photo_data
ClusterConfig = clustering.ClusterConfig
_validate_input = clustering._validate_input


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_df(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def _photo(pid, ts, lat=None, lon=None):
    return {
        "photo_id": pid,
        "timestamp": ts,
        "latitude": lat,
        "longitude": lon,
    }


BASE = datetime(2026, 2, 13, 9, 0, 0)

# 서울 강남 좌표
GANGNAM = (37.498095, 127.027610)
# 서울 광화문 좌표
GWANGHWAMUN = (37.566610, 126.978388)
# 부산 해운대 좌표
HAEUNDAE = (35.158698, 129.160384)


# ---------------------------------------------------------------------------
# haversine_distance
# ---------------------------------------------------------------------------

class TestHaversineDistance:
    def test_same_point(self):
        d = haversine_distance(37.5, 127.0, 37.5, 127.0)
        assert d == 0.0

    def test_seoul_busan(self):
        """서울-부산 직선 거리 ≈ 325km."""
        d = haversine_distance(37.5665, 126.9780, 35.1796, 129.0756)
        assert 300_000 < d < 350_000  # 300~350km

    def test_short_distance(self):
        """강남역 근처 100m 이내."""
        d = haversine_distance(37.498095, 127.027610, 37.498500, 127.028000)
        assert d < 200  # 200m 미만


# ---------------------------------------------------------------------------
# _validate_input
# ---------------------------------------------------------------------------

class TestValidateInput:
    def test_missing_columns_raises(self):
        df = pd.DataFrame({"photo_id": [1], "timestamp": ["2026-01-01"]})
        with pytest.raises(ValueError, match="latitude"):
            _validate_input(df)

    def test_nat_timestamp_removed(self):
        df = _make_df([
            _photo("p1", "2026-02-13 09:00:00", 37.5, 127.0),
            _photo("p2", None, 37.5, 127.0),
        ])
        result = _validate_input(df)
        assert len(result) == 1

    def test_future_timestamp_removed(self):
        future = datetime.now() + timedelta(days=10)
        df = _make_df([
            _photo("p1", "2026-02-13 09:00:00", 37.5, 127.0),
            _photo("p2", future.isoformat(), 37.5, 127.0),
        ])
        result = _validate_input(df)
        assert len(result) == 1

    def test_ancient_timestamp_removed(self):
        df = _make_df([
            _photo("p1", "2026-02-13 09:00:00", 37.5, 127.0),
            _photo("p2", "1985-01-01 00:00:00", 37.5, 127.0),
        ])
        result = _validate_input(df)
        assert len(result) == 1

    def test_sorted_by_timestamp(self):
        df = _make_df([
            _photo("p2", "2026-02-13 10:00:00", 37.5, 127.0),
            _photo("p1", "2026-02-13 09:00:00", 37.5, 127.0),
        ])
        result = _validate_input(df)
        assert result.iloc[0]["photo_id"] == "p1"


# ---------------------------------------------------------------------------
# cluster_events — 시간 기반 분리
# ---------------------------------------------------------------------------

class TestTimeBasedSplit:
    def test_120min_gap_splits(self):
        """120분 초과 갭(GPS 없음) → 새 이벤트 분리.

        GPS가 없으면 체류 판정 없이 기본 time_split_minutes(120)만 적용된다.
        """
        df = _make_df([
            _photo("p1", BASE, None, None),
            _photo("p2", BASE + timedelta(minutes=130), None, None),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 2

    def test_120min_gap_with_stay_does_not_split(self):
        """동일 위치(50m 이내) 120분 초과 → 체류이므로 분리 안 됨."""
        df = _make_df([
            _photo("p1", BASE, *GANGNAM),
            _photo("p2", BASE + timedelta(minutes=130), *GANGNAM),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 1  # 체류: stay_time_split_minutes(720) 적용

    def test_within_120min_same_event(self):
        """120분 이내 → 같은 이벤트."""
        df = _make_df([
            _photo("p1", BASE, *GANGNAM),
            _photo("p2", BASE + timedelta(minutes=60), *GANGNAM),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 1


# ---------------------------------------------------------------------------
# cluster_events — 거리 기반 분리
# ---------------------------------------------------------------------------

class TestDistanceBasedSplit:
    def test_500m_plus_splits(self):
        """500m 이상 이동 → 새 이벤트 분리 (시간이 가까워도)."""
        df = _make_df([
            _photo("p1", BASE, *GANGNAM),
            _photo("p2", BASE + timedelta(minutes=30), *GWANGHWAMUN),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 2

    def test_close_distance_same_event(self):
        """가까운 거리 → 같은 이벤트."""
        df = _make_df([
            _photo("p1", BASE, 37.498095, 127.027610),
            _photo("p2", BASE + timedelta(minutes=30), 37.498500, 127.028000),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 1


# ---------------------------------------------------------------------------
# cluster_events — 체류(Stay) 감지
# ---------------------------------------------------------------------------

class TestStayDetection:
    def test_stay_within_50m_3hours(self):
        """50m 이내 체류 3시간 → 같은 이벤트 유지."""
        df = _make_df([
            _photo("p1", BASE, 37.579617, 126.977041),
            _photo("p2", BASE + timedelta(hours=3), 37.579650, 126.977100),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 1

    def test_stay_over_12hours_splits(self):
        """체류 12시간 초과 → 새 이벤트 분리."""
        df = _make_df([
            _photo("p1", BASE, 37.579617, 126.977041),
            _photo("p2", BASE + timedelta(hours=13), 37.579650, 126.977100),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 2


# ---------------------------------------------------------------------------
# GPS 없는 사진
# ---------------------------------------------------------------------------

class TestNoGPS:
    def test_time_based_only(self):
        """GPS 없으면 시간 기준으로만 분리."""
        df = _make_df([
            _photo("p1", BASE, None, None),
            _photo("p2", BASE + timedelta(minutes=60), None, None),
            _photo("p3", BASE + timedelta(hours=3), None, None),
        ])
        result = cluster_events(df)
        assert len(result["events"]) == 2  # p1+p2 / p3


# ---------------------------------------------------------------------------
# 단일 사진
# ---------------------------------------------------------------------------

class TestSinglePhoto:
    def test_single_photo_one_event(self):
        df = _make_df([_photo("p1", BASE, *GANGNAM)])
        result = cluster_events(df)
        assert len(result["events"]) == 1
        assert result["events"][0]["photo_count"] == 1


# ---------------------------------------------------------------------------
# 빈 DataFrame
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_df(self):
        df = pd.DataFrame(columns=["photo_id", "timestamp", "latitude", "longitude"])
        result = cluster_events(df)
        assert result == {"events": [], "photo_event_links": []}

    def test_all_invalid_timestamps(self):
        """모든 타임스탬프가 무효 → 빈 결과."""
        df = _make_df([
            _photo("p1", None, *GANGNAM),
            _photo("p2", None, *GANGNAM),
        ])
        result = cluster_events(df)
        assert result == {"events": [], "photo_event_links": []}


# ---------------------------------------------------------------------------
# last_event 병합/분리
# ---------------------------------------------------------------------------

class TestLastEventMerge:
    def test_merge_with_last_event(self):
        """이전 이벤트에서 가까운 시간/거리 → 병합."""
        last_event = {
            "id": 99,
            "ended_at": (BASE - timedelta(minutes=30)).isoformat(),
            "primary_location": f"{GANGNAM[0]},{GANGNAM[1]}",
            "photo_count": 5,
            "gps_photo_count": 3,
        }
        df = _make_df([
            _photo("p10", BASE, *GANGNAM),
        ])
        result = cluster_events(df, user_id=1, last_event=last_event)
        assert len(result["events"]) == 1
        assert result["events"][0]["existing_event_id"] == 99

    def test_split_from_last_event(self):
        """이전 이벤트에서 먼 거리 → 분리 (existing_event_id = None)."""
        last_event = {
            "id": 99,
            "ended_at": (BASE - timedelta(minutes=30)).isoformat(),
            "primary_location": f"{HAEUNDAE[0]},{HAEUNDAE[1]}",
            "photo_count": 5,
            "gps_photo_count": 5,
        }
        df = _make_df([
            _photo("p10", BASE, *GANGNAM),
        ])
        result = cluster_events(df, user_id=1, last_event=last_event)
        assert len(result["events"]) == 1
        assert result["events"][0]["existing_event_id"] is None


# ---------------------------------------------------------------------------
# resolve_photo_event_updates
# ---------------------------------------------------------------------------

class TestResolvePhotoEventUpdates:
    def test_conversion(self):
        cluster_result = {
            "events": [],
            "photo_event_links": [
                {"photo_id": 1, "event_ref": 0, "existing_event_id": None},
                {"photo_id": 2, "event_ref": 0, "existing_event_id": None},
                {"photo_id": 3, "event_ref": 1, "existing_event_id": 99},
            ],
        }
        inserted_map = {0: 100, 1: 101}
        updates = resolve_photo_event_updates(cluster_result, inserted_map)

        assert (100, 1) in updates
        assert (100, 2) in updates
        assert (99, 3) in updates  # 기존 이벤트 ID 유지


# ---------------------------------------------------------------------------
# build_mock_photo_data 실행 확인
# ---------------------------------------------------------------------------

class TestBuildMockData:
    def test_produces_3_events(self):
        """강남/광화문/경복궁 → 3개 이벤트."""
        df = build_mock_photo_data()
        result = cluster_events(df, user_id=1)
        assert len(result["events"]) == 3

    def test_photo_count_correct(self):
        df = build_mock_photo_data()
        result = cluster_events(df, user_id=1)
        total = sum(e["photo_count"] for e in result["events"])
        assert total == 8  # p1~p8


# ---------------------------------------------------------------------------
# photo_event_links 구조 확인
# ---------------------------------------------------------------------------

class TestPhotoEventLinks:
    def test_links_count_matches_photos(self):
        df = build_mock_photo_data()
        result = cluster_events(df, user_id=1)
        assert len(result["photo_event_links"]) == 8

    def test_links_have_required_fields(self):
        df = build_mock_photo_data()
        result = cluster_events(df, user_id=1)
        for link in result["photo_event_links"]:
            assert "photo_id" in link
            assert "event_ref" in link
            assert "existing_event_id" in link
