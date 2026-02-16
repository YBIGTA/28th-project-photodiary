"""
Semantic Search 테스트 스크립트

사용법:
  python -m pipeline.search_test "부산에서 피자 먹은 사진"
  python -m pipeline.search_test "카페에서 커피" --city 서울
  python -m pipeline.search_test                          # 대화형 모드
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from db.schema import get_connection
from db.crud import search_photos, search_photos_filtered
from pipeline.core.embedder import embed_query

USER_ID = 1


def run_search(conn, query, city=None, district=None, limit=5):
    """쿼리 실행 + 결과 출력."""
    print(f'\n검색: "{query}"')
    if city:
        print(f"  필터: city={city}")
    if district:
        print(f"  필터: district={district}")

    query_vec = embed_query(query)

    if city or district:
        results = search_photos_filtered(
            conn, query_vec, USER_ID, limit=limit,
            city=city, district=district,
        )
    else:
        results = search_photos(conn, query_vec, USER_ID, limit=limit)

    if not results:
        print("\n  결과 없음. (photo_embeddings 테이블이 비어있을 수 있음)")
        print("  → python -m pipeline.save_embeddings 를 먼저 실행하세요.")
        return

    print(f"\n  {'순위':<4} {'ID':<6} {'유사도':<8} {'도시':<12} {'건물/장소':<20} {'촬영일'}")
    print(f"  {'─'*4} {'─'*6} {'─'*8} {'─'*12} {'─'*20} {'─'*12}")

    for i, r in enumerate(results, 1):
        sim = f"{r['similarity']:.4f}"
        city_val = r.get("city") or ""
        building = r.get("building") or ""
        taken = str(r.get("taken_at") or "")[:10]
        print(f"  {i:<4} {r['id']:<6} {sim:<8} {city_val:<12} {building:<20} {taken}")


def interactive_mode(conn):
    """대화형 검색 모드."""
    print("=" * 60)
    print("PicStory Semantic Search (MVP)")
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

        # 간단한 --city, --district 파싱
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

        run_search(conn, raw, city=city, district=district)


def main():
    conn = get_connection()

    try:
        # 인자가 있으면 단발 검색, 없으면 대화형
        args = sys.argv[1:]

        if args:
            query = []
            city = district = None
            i = 0
            while i < len(args):
                if args[i] == "--city" and i + 1 < len(args):
                    city = args[i + 1]
                    i += 2
                elif args[i] == "--district" and i + 1 < len(args):
                    district = args[i + 1]
                    i += 2
                elif args[i] == "--limit" and i + 1 < len(args):
                    i += 2  # limit은 기본값 사용
                else:
                    query.append(args[i])
                    i += 1

            query_text = " ".join(query)
            if query_text:
                run_search(conn, query_text, city=city, district=district)
            else:
                print("쿼리를 입력하세요.")
        else:
            interactive_mode(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
