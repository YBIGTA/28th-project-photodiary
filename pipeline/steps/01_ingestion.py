"""
01_ingestion.py: 로컬 디렉토리의 사진을 스캔하여 DB에 등록하는 첫 번째 단계.
"""

from __future__ import annotations

import os, sys
from contextlib import contextmanager
from pathlib import Path
from db.schema import get_connection
from db.crud import insert_photo
from pipeline.utils.exif_reader import analyze_photo
from pipeline.utils.geocoder import get_geocoder
from typing import List, Dict, Optional
from tqdm import tqdm

@contextmanager
def _suppress_stdout():
    """
    stdout 비활성화.
    ex)
        with suppress_stdout():
            print("Hi!")
    """
    saved = sys.stdout
    devnull = open(os.devnull, "w")
    try:
        sys.stdout = devnull
        yield
    finally:
        sys.stdout = saved
        devnull.close()

def ingest_directory(dir_path: str, user_id: int = 1) -> None:
    """
    1. 디렉토리 내 이미지 파일 목록 확보
    2. 각 파일의 EXIF 정보 추출 (taken_at, GPS)
    3. GPS가 있다면 주소로 변환 (Geocoding)
    4. DB (photos 테이블)에 저장 (중복 체크 포함)

    dir_path: str = 순회할 디렉토리 주소
    user_id: int = DB에 저장될 user id
    """
    base: Path = Path(dir_path)
    if not base.exists() or not base.is_dir():
        # dir_path 존재하지 않는 경우
        raise FileNotFoundError(f"디렉토리가 존재하지 않습니다: {base}")

    print(f"{dir_path} 하위 디렉토리에서 사진 추출 중...")

    photos: List[str] = [] 
    # 사진 경로 저장하는 리스트
    for (path, dirs, files) in os.walk(dir_path):
        # dir_path를 포함한 하위 디렉토리 순회하며 사진 파일 추출
        for f in files:
            if f.lower().endswith((".jpeg", ".jpg", ".png", ".heic")):
                # 파일이 사진 형식인지 확인한 후 리스트에 삽입
                photos.append(os.path.join(path, f))

    geocoder = get_geocoder()
    # 기본 geocoder 받아오기

    provider: str = type(geocoder).__name__ 
    print(f"{provider} 이용해 GPS 데이터 추출.")

    conn = get_connection()
    # DB 연결
    conn.autocommit = False 
    # autocommit 해제 (쿼리 시행 과정 에러 방지, 전체 한번에 commit)

    total: int = len(photos)
    skip: int = 0
    # total: 전체 파일 수, skip: 에러 발생한 파일 수

    for photo_path in tqdm(
        sorted(photos), 
        total=total, 
        desc="Ingest", 
        unit="img", 
    ):
        # tqdm으로 진행 상황 표시
        with _suppress_stdout():
            # analyze_photo의 출력이 tqdm 진행바와 겹치는 문제 해결
            photo_info: Optional[Dict] = analyze_photo(photo_path, geocoder)

        if not photo_info:
            # photo_info가 None일 경우 skip
            skip += 1
            tqdm.write(f"[SKIP] {photo_path}: GPS/EXIF 데이터 없음")
            continue
        try:
            # DB에 photo_info 정보 삽입하기
            insert_photo(
                conn,
                user_id=user_id,
                file_path=photo_path,
                lat=photo_info.get("lat"),
                lon=photo_info.get("lon"),
                place_info=photo_info.get("place"),
                taken_at=photo_info.get("taken_at"),
                commit=False
            )
        except Exception as e:
            # 삽입 과정에서 에러 발생한 경우 skip
            skip += 1
            tqdm.write(f"[SKIP] {photo_path}: {e}")

    print(f"{total-skip} / {total}개 사진 저장됨.")

    try:
        # DB commit 시도
        conn.commit()
    except Exception as e:
        # 시도 과정에서 에러 발생한 경우 되돌리기
        conn.rollback()
        print(f"DB 저장 중 에러 발생: {e}")
    finally:
        # DB 종료
        conn.close()


if __name__ == "__main__":
    # ingest_directory("data/my_photos")
    pass