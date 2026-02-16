from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List, Optional
import os

from db.schema import get_connection
from db.crud import list_photos, search_photos, get_photo
from pipeline.core.embedder import embed_query

router = APIRouter()

USER_ID = 1 # Fixed for prototype

@router.get("/")
def get_photos(limit: int = 100):
    conn = get_connection()
    try:
        photos = list_photos(conn, USER_ID, limit=limit)
        return photos
    finally:
        conn.close()

@router.post("/search")
def search_photos_endpoint(query: str, limit: int = 20):
    conn = get_connection()
    try:
        # 1. Embed the query
        query_embedding = embed_query(query)
        
        # 2. Search in DB
        results = search_photos(conn, query_embedding, USER_ID, limit=limit)
        return results
    finally:
        conn.close()

@router.get("/{photo_id}/image")
def get_photo_image(photo_id: int):
    conn = get_connection()
    try:
        photo = get_photo(conn, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        file_path = photo["file_path"]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server")
            
        return FileResponse(file_path)
    finally:
        conn.close()
