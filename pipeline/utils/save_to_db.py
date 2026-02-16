"""
사진 → GPS 추출 → 역지오코딩 → DB INSERT 파이프라인

실행: python -m pipeline.save_to_db
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from pipeline.extract_gps import analyze_photo
from pipeline.geocoder import get_geocoder
from db.schema import get_connection
from db.crud import insert_photo

USER_ID = 1  # 단일 사용자 고정


def main():
    photo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    photos = sorted(
        os.path.join(photo_dir, f)
        for f in os.listdir(photo_dir)
        if f.lower().endswith((".jpeg", ".jpg", ".png", ".heic"))
    )

    if not photos:
        print("이미지 파일을 찾을 수 없습니다.")
        sys.exit(1)

    geocoder = get_geocoder()
    provider = type(geocoder).__name__
    print(f"총 {len(photos)}개 사진 발견")
    print(f"역지오코딩: {provider}")

    conn = get_connection()
    saved = 0

    try:
        for photo_path in photos:
            result = analyze_photo(photo_path, geocoder)
            if result is None:
                continue

            lat = result["lat"]
            lon = result["lon"]
            place = result["place"]
            taken_at = result["taken_at"]

            photo_id = insert_photo(
                conn,
                user_id=USER_ID,
                file_path=photo_path,
                lat=lat,
                lon=lon,
                place_info=place,
                taken_at=taken_at,
            )
            print(f"  → DB 저장 완료 (photo_id={photo_id})")
            saved += 1
    except Exception as e:
        conn.rollback()
        print(f"\n오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    print(f"\n{'='*60}")
    print(f"완료! {saved}/{len(photos)}장 저장됨")


if __name__ == "__main__":
    main()
