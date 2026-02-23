from __future__ import annotations

import shutil
import uuid
from pathlib import Path 
from typing import List, Optional, Tuple 

from fastapi import UploadFile, HTTPException 

from pipeline.utils.s3_uploader import get_uploader, S3UploadResult

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".heic"}
UPLOAD_ROOT = Path("data/uploads")

def upload_photo(
    photos: List[UploadFile],
    user_id: int, 
    upload_root: Path = UPLOAD_ROOT, 
    allowed_ext: set[str] = ALLOWED_EXT 
) -> List[Path]:
    """
    UploadFile 리스트를 임시로 서버 디스크에 저장한 뒤 S3에 업로드한 후 S3 디렉토리 경로를 반환한다.
    photos: 업로드할 사진 (UploadFile) 리스트 
    user_id: 사용자 id 
    upload_root: 사진 파일이 업로드되는 경로 (기본: data/uploads)
    allowed_ext: 사진 파일 확장자 제한 (기본: ./jpg, ./jpeg, ./png, ./heic)
    """
    if not photos:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    batch_id = uuid.uuid4().hex[:12]
    upload_dir = upload_root / str(user_id) / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_local_paths: List[Path] = []

    for f in photos:
        filename: str = (f.filename or "").strip()
        ext: str = Path(filename).suffix.lower().strip()
        if ext not in allowed_ext:
            try:
                f.file.close()
            except Exception:
                pass 
            continue 
        local_name: str = f"{uuid.uuid4().hex}{ext}"
        local_path: str = upload_dir / local_name 

        try:
            with local_path.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            saved_local_paths.append(local_path)
        except Exception:
            pass 
        finally:
            try:
                f.file.close()
            except Exception:
                pass

    return saved_local_paths

    # if not saved_local_paths:
    #     raise HTTPException(status_code=400, detail="All files rejected")
    
    # uploader = get_uploader()
    # s3_results: List[S3UploadResult] = []

    # for path in saved_local_paths:
    #     try:
    #         res = uploader.upload(local_path=path, user_id=str(user_id), filename=path.name)
    #         s3_results.append(res)
    #     except Exception:
    #         pass 
    
    # return s3_results
    
