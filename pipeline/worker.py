"""
백그라운드에서 동작할 단일 사진 파이프라인 워커 (Background Worker).
업로드된 사진 1장을 S3에서 다운받고, RAM++ 태그, Moondream 캡션을 추출하며
임베딩을 만들고, 마지막으로 이벤트 클러스터링을 실행합니다.
"""
from __future__ import annotations

import os
import sys
import tempfile
import logging
from pathlib import Path

from db.schema import get_connection
from db.crud import (
    get_photo,
    bulk_insert_photo_keywords,
    update_caption,
    insert_embedding,
    get_last_event,
    list_unclustered_photos,
    insert_events,
    update_existing_event,
    update_photo_event_ids,
)
from pipeline.utils.s3_uploader import download_from_s3
from pipeline.steps.02_tagging import categorize_tag
from pipeline.core.ram_tagger import extract_tags_batch
from pipeline.core.moondream import generate_captions_batch, unload_model as unload_moondream
from pipeline.core.embedder import embed_photo
from pipeline.steps.03_clustering import cluster_events, resolve_photo_event_updates
from pipeline.steps.04_embedding import get_photo_keywords
import pandas as pd

logger = logging.getLogger(__name__)

def _extract_s3_key(file_path: str) -> str:
    """DB에 저장된 file_path가 S3 Key 혹은 S3 URL 어느 형태여도 Key만 추출한다.
    
    - S3 Key 예시:  photos/1/abc.jpg           → photos/1/abc.jpg
    - S3 URL 예시:  https://bucket.s3.region.amazonaws.com/photos/1/abc.jpg
                    → photos/1/abc.jpg
    """
    # TODO: DB에 저장된 file_path는 보통 한 가지 종류일듯. 팀원 구현 코드 확인 필요.
    if file_path.startswith("http://") or file_path.startswith("https://"):
        # URL에서 도메인 제거 후 첫 '/' 이후 path만 추출
        from urllib.parse import urlparse
        parsed = urlparse(file_path)
        return parsed.path.lstrip("/")
    return file_path


def process_photo_pipeline(photo_id: int, user_id: int, s3_key: str):
    """단일 사진에 대한 AI 처리 파이프라인 (백그라운드 실행용)."""
    logger.info(f"[Worker] Starting pipeline for photo_id={photo_id}, user_id={user_id}")
    
    # 1. DB에서 file_path를 꺼내 S3 Key를 결정 (인자 s3_key 또는 DB에서 재조회)
    # s3_key 인자가 URL이나 Key 중 어느 형태여도 올바르게 처리
    actual_s3_key = _extract_s3_key(s3_key)
    ext = os.path.splitext(actual_s3_key)[1].lower() or ".jpg"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp_path = tmp.name
        
        logger.info(f"  [1] Downloading from S3: {actual_s3_key} -> {tmp_path}")
        download_from_s3(actual_s3_key, tmp_path)
        
        conn = get_connection()
        try:
            # 사진 메타데이터 조회
            photo = get_photo(conn, photo_id)
            if not photo:
                logger.error(f"  Photo not found in DB: {photo_id}")
                return

            # 2. RAM++ 태깅
            logger.info("  [2] Extracting tags with RAM++")
            ram_results = extract_tags_batch([tmp_path], batch_size=1, show_progress=False)
            if ram_results and ram_results[0].tags:
                tags = ram_results[0].tags
                keyword_data = [
                    (tag.tag_en, categorize_tag(tag.tag_en), tag.confidence)
                    for tag in tags
                ]
                bulk_insert_photo_keywords(conn, photo_id, keyword_data)
                logger.info(f"      Saved {len(tags)} tags.")
            
            # RAM++ 모델 VRAM 해제
            import pipeline.core.ram_tagger as ram_mod
            if ram_mod._model is not None:
                del ram_mod._model
                ram_mod._model = None
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
            # 3. Moondream 캡셔닝
            logger.info("  [3] Generating caption with Moondream 2")
            moon_results = generate_captions_batch([tmp_path], length="normal", show_progress=False)
            caption = ""
            if moon_results and moon_results[0].caption:
                caption = moon_results[0].caption
                update_caption(conn, photo_id, caption)
                logger.info(f"      Caption: {caption[:30]}...")
            
            unload_moondream()  # 필요하면 메모리 해제
            
            # 4. 임베딩 생성 (e5-base)
            logger.info("  [4] Generating embedding")
            # keywords 가져오기
            keywords = get_photo_keywords(conn, photo_id)
            place_parts = {
                "state": photo.get("state"),
                "city": photo.get("city"),
                "district": photo.get("district"),
                "road": photo.get("road"),
                "building": photo.get("building"),
            }
            if keywords or any(place_parts.values()) or caption:
                vec = embed_photo(keywords, place_parts, caption)
                insert_embedding(conn, photo_id, vec)
                logger.info("      Embedding generated and saved.")
            
            # 5. 이벤트 클러스터링
            logger.info("  [5] Clustering events")
            unclustered = list_unclustered_photos(conn, user_id, limit=200)
            if unclustered:
                df = pd.DataFrame(unclustered)
                df = df.rename(columns={"taken_at": "timestamp"})
                last_event = get_last_event(conn, user_id)
                cluster_result = cluster_events(df, user_id=user_id, last_event=last_event)
                
                inserted_ids = insert_events(conn, cluster_result["events"])
                updates = resolve_photo_event_updates(cluster_result, inserted_ids)
                if updates:
                    update_photo_event_ids(conn, updates)
                
                # 기존 이벤트가 업데이트된 경우 (merge_anchor)
                for event in cluster_result["events"]:
                    if event["existing_event_id"] is not None:
                        update_existing_event(
                            conn,
                            event_id=event["existing_event_id"],
                            ended_at=event["ended_at"],
                            primary_location=event["primary_location"],
                            photo_count=event["photo_count"]
                        )
                logger.info(f"      Clustering complete. {len(cluster_result['events'])} events extracted/updated.")
        finally:
            conn.close()
    
    except Exception as e:
        logger.error(f"Pipeline error for photo {photo_id}: {e}", exc_info=True)
    finally:
        # 임시 파일 정리
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.info(f"  [6] Cleaned up temporary file: {tmp_path}")
