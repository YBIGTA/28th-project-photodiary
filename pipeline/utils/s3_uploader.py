from __future__ import annotations
"""S3 이미지 업로드 유틸리티.

boto3를 사용하여 로컬 이미지를 AWS S3에 업로드하고
S3 URL을 반환하는 독립 모듈.
"""

from typing import Optional

import os
import time
import mimetypes
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# ── 환경변수 기본값 ──────────────────────────────────────────
_DEFAULT_REGION = "ap-northeast-2"


# ── 데이터 클래스 ────────────────────────────────────────────
@dataclass
class S3UploadResult:
    """단일 파일 업로드 결과.

    Attributes
    ----------
    local_path : str
        업로드한 로컬 파일 경로.
    s3_key : str
        S3 객체 키.
    s3_url : str
        퍼블릭 S3 URL.
    """

    local_path: str
    s3_key: str
    s3_url: str


# ── 메인 클래스 ──────────────────────────────────────────────
class S3Uploader:
    """boto3 S3 클라이언트 래퍼.

    Parameters
    ----------
    bucket : str, optional
        S3 버킷 이름. 미지정 시 ``AWS_S3_BUCKET_NAME`` 환경변수 사용.
    region : str, optional
        AWS 리전. 미지정 시 ``AWS_S3_REGION`` 환경변수 또는 ``ap-northeast-2``.
    """

    def __init__(self, bucket: Optional[str] = None, region: Optional[str] = None):
        self.bucket = bucket or os.getenv("AWS_S3_BUCKET_NAME", "")
        self.region = region or os.getenv("AWS_S3_REGION", _DEFAULT_REGION)

        if not self.bucket:
            raise ValueError("S3 버킷 이름이 설정되지 않았습니다. "
                             "AWS_S3_BUCKET_NAME 환경변수를 확인하세요.")

        self._client = boto3.client(
            "s3",
            region_name=self.region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

    # ── public API ───────────────────────────────────────────

    def upload(
        self,
        local_path: str | Path,
        user_id: str,
        filename: Optional[str] = None,
    ) -> S3UploadResult:
        """단일 파일을 S3에 업로드.

        Parameters
        ----------
        local_path : str | Path
            업로드할 로컬 파일 경로.
        user_id : str
            사용자 식별자 (S3 키 prefix).
        filename : str, optional
            S3에 저장할 파일명. 미지정 시 원본 파일명 사용.

        Returns
        -------
        S3UploadResult
            업로드 결과 (local_path, s3_key, s3_url).

        Raises
        ------
        FileNotFoundError
            로컬 파일이 존재하지 않을 때.
        ClientError
            S3 업로드 실패 시.
        """
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        if filename is None:
            filename = path.name

        timestamp = int(time.time())
        s3_key = f"photos/{user_id}/{timestamp}_{filename}"

        extra_args: dict[str, str] = {}
        content_type, _ = mimetypes.guess_type(str(path))
        if content_type:
            extra_args["ContentType"] = content_type

        self._client.upload_file(
            str(path),
            self.bucket,
            s3_key,
            ExtraArgs=extra_args,
        )

        s3_url = self.get_url(s3_key)
        return S3UploadResult(
            local_path=str(path),
            s3_key=s3_key,
            s3_url=s3_url,
        )

    def download(self, s3_key: str, local_path: str | Path) -> str:
        """S3에서 파일을 다운로드합니다.

        Parameters
        ----------
        s3_key : str
            다운로드할 S3 객체의 키.
        local_path : str | Path
            저장할 로컬 파일 경로.

        Returns
        -------
        str
            저장된 로컬 파일의 절대 경로.

        Raises
        ------
        ClientError
            S3 다운로드 실패 시.
        """
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, s3_key, str(path))
        return str(path.absolute())

    def upload_batch(
        self,
        local_paths: list[str | Path],
        user_id: str,
    ) -> list[S3UploadResult]:
        """여러 파일을 일괄 업로드.

        Parameters
        ----------
        local_paths : list[str | Path]
            업로드할 로컬 파일 경로 목록.
        user_id : str
            사용자 식별자.

        Returns
        -------
        list[S3UploadResult]
            각 파일의 업로드 결과 리스트.
        """
        results: list[S3UploadResult] = []
        for i, path in enumerate(local_paths, 1):
            result = self.upload(path, user_id)
            results.append(result)
            print(f"  [{i}/{len(local_paths)}] 업로드 완료: {result.s3_key}")
        return results

    def delete(self, s3_key: str) -> bool:
        """S3 객체 삭제.

        Parameters
        ----------
        s3_key : str
            삭제할 S3 객체 키.

        Returns
        -------
        bool
            삭제 성공 여부.
        """
        try:
            self._client.delete_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False

    def get_url(self, s3_key: str) -> str:
        """S3 객체의 URL 생성.

        Parameters
        ----------
        s3_key : str
            S3 객체 키.

        Returns
        -------
        str
            ``https://{bucket}.s3.{region}.amazonaws.com/{key}`` 형식 URL.
        """
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{s3_key}"


# ── 싱글턴 ───────────────────────────────────────────────────
_uploader: Optional[S3Uploader] = None


# ── 모듈 레벨 편의 함수 ─────────────────────────────────────

def get_uploader(bucket: Optional[str] = None, region: Optional[str] = None) -> S3Uploader:
    """S3Uploader 싱글턴 반환 (최초 호출 시 생성).

    Parameters
    ----------
    bucket : str, optional
        S3 버킷 이름.
    region : str, optional
        AWS 리전.

    Returns
    -------
    S3Uploader
    """
    global _uploader
    if _uploader is None:
        _uploader = S3Uploader(bucket=bucket, region=region)
    return _uploader


def upload_to_s3(local_path: str | Path, user_id: str) -> S3UploadResult:
    """원라인 S3 업로드 편의 함수.

    Parameters
    ----------
    local_path : str | Path
        업로드할 로컬 파일 경로.
    user_id : str
        사용자 식별자.

    Returns
    -------
    S3UploadResult
    """
    return get_uploader().upload(local_path, user_id)


def download_from_s3(s3_key: str, local_path: str | Path) -> str:
    """원라인 S3 다운로드 편의 함수.

    Parameters
    ----------
    s3_key : str
        S3 객체 키.
    local_path : str | Path
        다운로드할 로컬 파일 경로.

    Returns
    -------
    str
        로컬 파일 절대 경로.
    """
    return get_uploader().download(s3_key, local_path)


# ── CLI 테스트 ───────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="S3 업로드 테스트")
    parser.add_argument("file", help="업로드할 파일 경로")
    parser.add_argument("--user-id", default="test_user", help="사용자 ID")
    parser.add_argument("--bucket", default=None, help="S3 버킷 이름 (미지정 시 환경변수)")
    args = parser.parse_args()

    uploader = S3Uploader(bucket=args.bucket)
    result = uploader.upload(args.file, args.user_id)

    print(f"로컬 경로: {result.local_path}")
    print(f"S3 키:    {result.s3_key}")
    print(f"S3 URL:   {result.s3_url}")
