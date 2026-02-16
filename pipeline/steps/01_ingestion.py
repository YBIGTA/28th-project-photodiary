"""
01_ingestion.py: 로컬 디렉토리의 사진을 스캔하여 DB에 등록하는 첫 번째 단계.
"""

from pathlib import Path
from db.schema import get_connection
from db.crud import insert_photo
from pipeline.utils.exif_reader import extract_exif # To be created
from pipeline.utils.geocoder import reverse_geocode # To be created

def ingest_directory(dir_path: str, user_id: int = 1):
    """
    1. 디렉토리 내 이미지 파일 목록 확보
    2. 각 파일의 EXIF 정보 추출 (taken_at, GPS)
    3. GPS가 있다면 주소로 변환 (Geocoding)
    4. DB (photos 테이블)에 저장 (중복 체크 포함)
    """
    path = Path(dir_path)
    conn = get_connection()
    
    # TODO: Implement file scanning and metadata extraction logic
    print(f"Scanning {dir_path} for images...")
    
    pass

if __name__ == "__main__":
    # ingest_directory("data/my_photos")
    pass
