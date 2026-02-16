"""
DB에 저장된 사진의 메타데이터 → 벡터 변환 → photo_embeddings 저장

실행: python -m pipeline.save_embeddings
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from db.schema import get_connection
from db.crud import list_photos, insert_embedding
from pipeline.core.embedder import embed_photo

USER_ID = 1  # 단일 사용자 고정


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


def main():
    conn = get_connection()

    try:
        photos = list_photos(conn, USER_ID, limit=10000)

        if not photos:
            print("DB에 저장된 사진이 없습니다.")
            sys.exit(1)

        print(f"총 {len(photos)}장 사진 발견")

        saved = 0
        skipped = 0

        for photo in photos:
            photo_id = photo["id"]

            # RAM++ 키워드 가져오기 (아직 없으면 빈 리스트)
            keywords = get_photo_keywords(conn, photo_id)

            # 장소 메타데이터 조합
            place_parts = {
                "state": photo.get("state"),
                "city": photo.get("city"),
                "district": photo.get("district"),
                "road": photo.get("road"),
                "building": photo.get("building"),
            }

            # Moondream 캡션 가져오기
            caption = photo.get("caption") or ""

            # 키워드도 장소 정보도 캡션도 없으면 스킵
            has_place = any(v for v in place_parts.values())
            if not keywords and not has_place and not caption:
                print(f"  [SKIP] photo_id={photo_id}: 키워드/장소/캡션 정보 없음")
                skipped += 1
                continue

            # 벡터 변환 + 저장 (키워드 + 캡션 + 장소 통합)
            vec = embed_photo(keywords, place_parts, caption)
            insert_embedding(conn, photo_id, vec)

            kw_str = ", ".join(keywords[:3]) if keywords else "(없음)"
            cap_str = caption[:40] + "…" if len(caption) > 40 else caption or "(없음)"
            city = photo.get("city") or ""
            print(f"  [OK] photo_id={photo_id} | 키워드: {kw_str} | 캡션: {cap_str} | {city}")
            saved += 1

        print(f"\n{'='*60}")
        print(f"완료! {saved}장 임베딩 저장, {skipped}장 스킵")

    except Exception as e:
        conn.rollback()
        print(f"\n오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
