"""
증분 이벤트 클러스터링 실행 스크립트.

실행:
    python -m pipeline.run_clustering               # 모든 유저
    python -m pipeline.run_clustering --user-id 3   # 특정 유저만
"""

import sys
import argparse
from importlib import import_module

import pandas as pd

from db.crud import (
    get_last_event,
    insert_events,
    list_unclustered_photos,
    list_all_user_ids,
    update_existing_event,
    update_photo_event_ids,
)
from db.schema import get_connection

_clustering_module = import_module("pipeline.steps.03_clustering")
cluster_events = _clustering_module.cluster_events
resolve_photo_event_updates = _clustering_module.resolve_photo_event_updates


def _build_cluster_input(photos: list[dict]) -> pd.DataFrame:
    if not photos:
        return pd.DataFrame(columns=["photo_id", "timestamp", "latitude", "longitude"])

    photo_df = pd.DataFrame(photos)
    return photo_df.rename(columns={"taken_at": "timestamp"})


def cluster_for_user(conn, user_id: int) -> None:
    """특정 사용자의 미클러스터 사진에 대해 이벤트 클러스터링을 수행한다."""
    unclustered_photos = list_unclustered_photos(conn, user_id=user_id)
    if not unclustered_photos:
        print(f"[user_id={user_id}] 처리할 미클러스터 사진이 없습니다.")
        return

    last_event = get_last_event(conn, user_id=user_id)
    cluster_input_df = _build_cluster_input(unclustered_photos)

    cluster_result = cluster_events(
        cluster_input_df,
        user_id=user_id,
        last_event=last_event,
    )

    new_events = []
    merged_events = []
    for event in cluster_result["events"]:
        if event.get("existing_event_id") is None:
            new_events.append(event)
        else:
            merged_events.append(event)

    # P0: 트랜잭션 원자성 — 모든 쓰기를 commit=False로 수행 후 마지막에 일괄 커밋
    inserted_event_ids_by_ref = insert_events(conn, new_events, commit=False)

    for event in merged_events:
        existing_id = event["existing_event_id"]
        original_count = (last_event.get("photo_count") or 0) if last_event else 0
        update_existing_event(
            conn,
            event_id=existing_id,
            ended_at=event["ended_at"],
            primary_location=event["primary_location"],
            photo_count=original_count + event["photo_count"],
            commit=False,
        )

    photo_event_updates = resolve_photo_event_updates(
        cluster_result,
        inserted_event_ids_by_ref,
    )
    updated_photo_count = update_photo_event_ids(
        conn, photo_event_updates, commit=False,
    )

    # 모든 쓰기 성공 후 일괄 커밋
    conn.commit()

    print(
        f"[user_id={user_id}] {len(new_events)}개의 이벤트 생성, "
        f"{len(merged_events)}개의 이벤트 병합, "
        f"{updated_photo_count}개의 사진 업데이트 완료"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="증분 이벤트 클러스터링 실행 스크립트")
    parser.add_argument(
        "--user-id", type=int, default=None,
        help="처리할 사용자 ID (미지정 시 전체 유저 처리)",
    )
    args = parser.parse_args()

    conn = get_connection()
    try:
        user_ids = [args.user_id] if args.user_id else list_all_user_ids(conn)
        if not user_ids:
            print("DB에 등록된 사용자가 없습니다.")
            return

        for uid in user_ids:
            try:
                cluster_for_user(conn, uid)
            except Exception as error:
                conn.rollback()
                print(f"[user_id={uid}] 클러스터링 오류: {error}", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
