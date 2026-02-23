"""사진 조회 / 검색 / 이미지 서빙 라우터."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import List, Optional
import os

from backend.dependencies import get_current_user_id
from db.schema import get_connection
from db.crud import list_photos, search_photos, get_photo
from pipeline.core.embedder import embed_query

router = APIRouter()


@router.get("/")
def get_photos(
    limit: int = 100,
    user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    try:
        photos = list_photos(conn, user_id, limit=limit)
        return photos
    finally:
        conn.close()


@router.post("/search")
def search_photos_endpoint(
    query: str,
    limit: int = 20,
    user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    try:
        query_embedding = embed_query(query)
        results = search_photos(conn, query_embedding, user_id, limit=limit)
        return results
    finally:
        conn.close()


@router.get("/{photo_id}/image")
def get_photo_image(photo_id: int):
    """photo_id에 해당하는 이미지를 반환한다.

    - S3 URL이 저장된 경우: 307 Redirect (브라우저가 S3에서 직접 다운로드)
    - 로컬 경로가 저장된 경우: FileResponse (하위 호환)
    """
    conn = get_connection()
    try:
        photo = get_photo(conn, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        file_path = photo["file_path"]

        # S3 URL로 변환하여 브라우저가 직접 리소스를 가져오도록 함
        if file_path:
            if file_path.startswith("http://") or file_path.startswith("https://"):
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=file_path, status_code=307)
            # 버킷 이름이 지정된 경우 (일반적인 업로드 케이스) S3 key로 간주
            elif "AWS_S3_BUCKET_NAME" in os.environ:
                bucket = os.getenv("AWS_S3_BUCKET_NAME")
                region = os.getenv("AWS_S3_REGION", "ap-northeast-2")
                s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{file_path}"
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=s3_url, status_code=307)

        # 하위 호환: 로컬 경로가 저장된 경우 파일 직접 반환
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server")
        return FileResponse(file_path)
    finally:
        conn.close()