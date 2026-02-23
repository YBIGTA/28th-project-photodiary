"""
DB에 저장된 사진의 메타데이터 → 벡터 변환 → photo_embeddings 저장

실행:
  python -m pipeline.steps.04_embedding               # 모든 유저
  python -m pipeline.steps.04_embedding --user-id 3   # 특정 유저만
"""

import sys
import argparse

from dotenv import load_dotenv

load_dotenv()

from db.schema import get_connection
from db.crud import list_photos, insert_embedding, list_all_user_ids
from pipeline.core.embedder import embed_photo


def get_photo_keywords(conn, photo_id):
    """photo_keywords + keywords 테이블에서 해당 사진의 키워드 목록 조회.

    Returns
    -------
    list[str] — 키워드 이름 목록 (중요도 높은 순)
    """
    sql = """
        SELECT k.name
        FROM photo_keywords pk
        JOIN keywords k ON pk.keyword_id = k.id
        WHERE pk.photo_id = %s
        ORDER BY pk.importance DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id,))
        return [row[0] for row in cur.fetchall()]


def process_user(conn, user_id: int, limit: int = 10000):
    """특정 사용자의 사진 임베딩 생성 및 DB 저장."""
    photos = list_photos(conn, user_id, limit=limit)
    if not photos:
        print(f"[user_id={user_id}] DB에 저장된 사진이 없습니다.")
        return 0, 0

    print(f"\n[user_id={user_id}] 총 {len(photos)}장 사진 발견")
    saved = 0
    skipped = 0

    for photo in photos:
        photo_id = photo["id"]
        keywords = get_photo_keywords(conn, photo_id)
        place_parts = {
            "state": photo.get("state"),
            "city": photo.get("city"),
            "district": photo.get("district"),
            "road": photo.get("road"),
            "building": photo.get("building"),
        }
        caption = photo.get("caption") or ""

        has_place = any(v for v in place_parts.values())
        if not keywords and not has_place and not caption:
            print(f"  [SKIP] photo_id={photo_id}: 키워드/장소/캡션 정보 없음")
            skipped += 1
            continue

        vec = embed_photo(keywords, place_parts, caption)
        insert_embedding(conn, photo_id, vec)

        kw_str = ", ".join(keywords[:3]) if keywords else "(없음)"
        cap_str = caption[:40] + "…" if len(caption) > 40 else caption or "(없음)"
        city = photo.get("city") or ""
        print(f"  [OK] photo_id={photo_id} | 키워드: {kw_str} | 캡션: {cap_str} | {city}")
        saved += 1

    return saved, skipped


def main():
    parser = argparse.ArgumentParser(
        description="사진 메타데이터 → 임베딩 벡터 생성 후 DB 저장"
    )
    parser.add_argument(
        "--user-id", type=int, default=None,
        help="처리할 사용자 ID (미지정 시 전체 유저 처리)",
    )
    parser.add_argument(
        "--limit", type=int, default=10000,
        help="유저당 처리할 최대 사진 수 (기본: 10000)",
    )
    args = parser.parse_args()

    conn = get_connection()
    total_saved = 0
    total_skipped = 0

    try:
        user_ids = [args.user_id] if args.user_id else list_all_user_ids(conn)
        if not user_ids:
            print("DB에 등록된 사용자가 없습니다.")
            sys.exit(1)

        for uid in user_ids:
            saved, skipped = process_user(conn, uid, limit=args.limit)
            total_saved += saved
            total_skipped += skipped

        print(f"\n{'='*60}")
        print(f"완료! {total_saved}장 임베딩 저장, {total_skipped}장 스킵")

    except Exception as e:
        conn.rollback()
        print(f"\n오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
