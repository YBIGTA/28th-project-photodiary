from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
import os

from db.schema import get_connection
from db.crud import list_photos, search_photos, get_photo
from pipeline.core.embedder import embed_query
from backend.dependencies import get_current_user_id

router = APIRouter()


@router.get("/")
def get_photos(limit: int = 100, user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    try:
        photos = list_photos(conn, user_id, limit=limit)
        return photos
    finally:
        conn.close()


@router.post("/search")
def search_photos_endpoint(query: str, limit: int = 20, user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    try:
        query_embedding = embed_query(query)
        results = search_photos(conn, query_embedding, user_id, limit=limit)
        return results
    finally:
        conn.close()


@router.get("/{photo_id}/image")
def get_photo_image(photo_id: int, user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    try:
        photo = get_photo(conn, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        if photo["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        file_path = photo["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server")

        return FileResponse(file_path)
    finally:
        conn.close()
