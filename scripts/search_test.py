"""
Semantic Search 테스트 스크립트

사용법:
  python -m pipeline.utils.search_test "부산에서 피자 먹은 사진" --user-id 1
  python -m pipeline.utils.search_test "카페에서 커피" --user-id 1 --city 서울
  python -m pipeline.utils.search_test --user-id 1        # 대화형 모드
"""

import sys
import argparse

from dotenv import load_dotenv

load_dotenv()

from db.schema import get_connection
from db.crud import search_photos, search_photos_filtered
from pipeline.core.embedder import embed_query


def run_search(conn, query, user_id: int, city=None, district=None, limit=5):
    """쿼리 실행 + 결과 출력."""
    print(f'\n검색: "{query}" (user_id={user_id})')
    if city:
        print(f"  필터: city={city}")
    if district:
        print(f"  필터: district={district}")

    query_vec = embed_query(query)

    if city or district:
        results = search_photos_filtered(
            conn, query_vec, user_id, limit=limit,
            city=city, district=district,
        )
    else:
        results = search_photos(conn, query_vec, user_id, limit=limit)

    if not results:
        print("\n  결과 없음. (photo_embeddings 테이블이 비어있을 수 있음)")
        print("  → python -m pipeline.steps.04_embedding 를 먼저 실행하세요.")
        return

    print(f"\n  {'순위':<4} {'ID':<6} {'유사도':<8} {'도시':<12} {'건물/장소':<20} {'촬영일'}")
    print(f"  {'─'*4} {'─'*6} {'─'*8} {'─'*12} {'─'*20} {'─'*12}")

    for i, r in enumerate(results, 1):
        sim = f"{r['similarity']:.4f}"
        city_val = r.get("city") or ""
        building = r.get("building") or ""
        taken = str(r.get("taken_at") or "")[:10]
        print(f"  {i:<4} {r['id']:<6} {sim:<8} {city_val:<12} {building:<20} {taken}")


def interactive_mode(conn, user_id: int):
    """대화형 검색 모드."""
    print("=" * 60)
    print(f"PicTrace Semantic Search (user_id={user_id})")
    print("종료: q 또는 Ctrl+C")
    print("필터 예시: 부산에서 피자 --city 부산")
    print("=" * 60)

    while True:
        try:
            raw = input("\n검색> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료.")
            break

        if not raw or raw.lower() == "q":
            print("종료.")
            break

        city = district = None
        parts = raw.split("--city")
        if len(parts) == 2:
            raw = parts[0].strip()
            city = parts[1].strip().split()[0] if parts[1].strip() else None

        parts = raw.split("--district")
        if len(parts) == 2:
            raw = parts[0].strip()
            district = parts[1].strip().split()[0] if parts[1].strip() else None

        if not raw:
            print("쿼리를 입력하세요.")
            continue

        run_search(conn, raw, user_id=user_id, city=city, district=district)


def main():
    parser = argparse.ArgumentParser(description="시맨틱 사진 검색 테스트")
    parser.add_argument("query", nargs="?", help="검색 쿼리 (없으면 대화형 모드)")
    parser.add_argument("--user-id", type=int, required=True, help="검색 대상 사용자 ID")
    parser.add_argument("--city", type=str, default=None, help="도시 필터")
    parser.add_argument("--district", type=str, default=None, help="구/동 필터")
    parser.add_argument("--limit", type=int, default=5, help="최대 결과 수 (기본: 5)")
    args = parser.parse_args()

    conn = get_connection()
    try:
        if args.query:
            run_search(conn, args.query, user_id=args.user_id,
                       city=args.city, district=args.district, limit=args.limit)
        else:
            interactive_mode(conn, user_id=args.user_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
