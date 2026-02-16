"""
증분 이벤트 클러스터링 실행 스크립트.

실행:
    python -m pipeline.run_clustering
"""

import sys

import pandas as pd

from db.crud import (
    get_last_event,
    insert_events,
    list_unclustered_photos,
    update_existing_event,
    update_photo_event_ids,
)
from db.schema import get_connection
from pipeline.event_clustering import cluster_events, resolve_photo_event_updates

USER_ID = 1


def _build_cluster_input(photos: list[dict]) -> pd.DataFrame:
    if not photos:
        return pd.DataFrame(columns=["photo_id", "timestamp", "latitude", "longitude"])

    photo_df = pd.DataFrame(photos)
    return photo_df.rename(columns={"taken_at": "timestamp"})


def main() -> None:
    conn = get_connection()

    try:
        unclustered_photos = list_unclustered_photos(conn, user_id=USER_ID)
        if not unclustered_photos:
            print("처리할 미클러스터 사진이 없습니다.")
            return

        last_event = get_last_event(conn, user_id=USER_ID)
        cluster_input_df = _build_cluster_input(unclustered_photos)

        cluster_result = cluster_events(
            cluster_input_df,
            user_id=USER_ID,
            last_event=last_event,
        )

        new_events = []
        merged_events = []
        for event in cluster_result["events"]:
            if event.get("existing_event_id") is None:
                new_events.append(event)
            else:
                merged_events.append(event)

        inserted_event_ids_by_ref = insert_events(conn, new_events)

        # 기존 이벤트에 병합된 경우 메타데이터 갱신
        for event in merged_events:
            existing_id = event["existing_event_id"]
            # 기존 이벤트의 원래 photo_count를 더해야 정확한 값이 됨
            original_count = last_event.get("photo_count", 0) if last_event else 0
            update_existing_event(
                conn,
                event_id=existing_id,
                ended_at=event["ended_at"],
                primary_location=event["primary_location"],
                photo_count=original_count + event["photo_count"],
            )

        photo_event_updates = resolve_photo_event_updates(
            cluster_result,
            inserted_event_ids_by_ref,
        )
        updated_photo_count = update_photo_event_ids(conn, photo_event_updates)

        print(
            f"{len(new_events)}개의 이벤트 생성, "
            f"{len(merged_events)}개의 이벤트 병합, "
            f"{updated_photo_count}개의 사진 업데이트 완료"
        )
    except Exception as error:
        conn.rollback()
        print(f"클러스터링 파이프라인 실행 중 오류 발생: {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
