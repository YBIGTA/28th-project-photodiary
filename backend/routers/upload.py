"""사진 업로드 라우터 — EXIF 추출 → 역지오코딩 → S3 업로드 → DB 저장."""

from __future__ import annotations

import os
import tempfile
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from backend.dependencies import get_current_user_id
from db.schema import get_connection
from db.crud import insert_photo
from pipeline.utils.exif_reader import get_exif_data, get_gps_info, get_lat_lon, get_taken_at
from pipeline.utils.geocoder import get_geocoder
from pipeline.utils.s3_uploader import upload_to_s3

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload")
def upload_photo(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    """사진 업로드: EXIF 추출 → GPS 역지오코딩 → S3 업로드 → DB INSERT.

    Returns
    -------
    dict
        {"photo_id": int, "s3_url": str}
    """
    # 허용 확장자 검증
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".heic"):
        raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다.")

    # 임시 파일에 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        # EXIF 추출
        lat, lon, taken_at, place_info = None, None, None, None
        exif_data = get_exif_data(tmp_path)
        if exif_data:
            taken_at = get_taken_at(exif_data)
            gps_info = get_gps_info(exif_data)
            if gps_info:
                lat, lon = get_lat_lon(gps_info)

        # GPS 역지오코딩
        if lat is not None and lon is not None:
            try:
                geocoder = get_geocoder()
                place_info = geocoder.reverse_geocode(lat, lon)
            except Exception as e:
                logger.warning("역지오코딩 실패: %s", e)

        # S3 업로드
        try:
            s3_result = upload_to_s3(tmp_path, str(user_id))
            s3_url = s3_result.s3_url
            file_path = s3_result.s3_key
        except Exception as e:
            logger.error("S3 업로드 실패: %s", e)
            raise HTTPException(status_code=500, detail="S3 업로드에 실패했습니다.")

        # DB INSERT
        conn = get_connection()
        try:
            photo_id = insert_photo(
                conn,
                user_id=user_id,
                file_path=file_path,
                lat=lat,
                lon=lon,
                place_info=place_info,
                taken_at=taken_at,
            )
        finally:
            conn.close()

        return {"photo_id": photo_id, "s3_url": s3_url}

    finally:
        # 임시 파일 정리
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
