"""pipeline/utils/s3_uploader.py 단위 테스트."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import pipeline.utils.s3_uploader as s3_mod
from pipeline.utils.s3_uploader import S3Uploader, S3UploadResult, get_uploader


# ---------------------------------------------------------------------------
# S3 키 형식
# ---------------------------------------------------------------------------

class TestS3KeyFormat:
    @patch("boto3.client")
    def test_key_format(self, mock_boto):
        """S3 키: photos/{user_id}/{timestamp}_{filename}."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        with patch.dict(os.environ, {"AWS_S3_BUCKET_NAME": "test-bucket"}):
            uploader = S3Uploader(bucket="test-bucket")

        # 임시 파일 생성
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            result = uploader.upload(path, user_id="42", filename="beach.jpg")
            assert result.s3_key.startswith("photos/42/")
            assert result.s3_key.endswith("_beach.jpg")
            # timestamp 부분 확인
            parts = result.s3_key.split("/")
            ts_filename = parts[2]
            ts = ts_filename.split("_")[0]
            assert ts.isdigit()
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# ContentType 추론
# ---------------------------------------------------------------------------

class TestContentType:
    @patch("boto3.client")
    def test_jpeg_content_type(self, mock_boto):
        """JPEG → image/jpeg ContentType."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        uploader = S3Uploader(bucket="test-bucket")

        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            uploader.upload(path, user_id="1")
            call_args = mock_client.upload_file.call_args
            extra = call_args[1].get("ExtraArgs") or call_args[0][3] if len(call_args[0]) > 3 else call_args[1].get("ExtraArgs", {})
            assert extra.get("ContentType") == "image/jpeg"
        finally:
            os.unlink(path)

    @patch("boto3.client")
    def test_png_content_type(self, mock_boto):
        """PNG → image/png ContentType."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        uploader = S3Uploader(bucket="test-bucket")

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            uploader.upload(path, user_id="1")
            call_args = mock_client.upload_file.call_args
            extra = call_args[1].get("ExtraArgs") or {}
            assert extra.get("ContentType") == "image/png"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 파일 미존재
# ---------------------------------------------------------------------------

class TestUploadErrors:
    @patch("boto3.client")
    def test_file_not_found(self, mock_boto):
        """존재하지 않는 파일 → FileNotFoundError."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        uploader = S3Uploader(bucket="test-bucket")

        with pytest.raises(FileNotFoundError):
            uploader.upload("/nonexistent/path.jpg", user_id="1")

    def test_no_bucket_raises(self):
        """버킷 미설정 → ValueError."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AWS_S3_BUCKET_NAME", None)
            with patch("boto3.client"):
                with pytest.raises(ValueError, match="버킷"):
                    S3Uploader(bucket="")


# ---------------------------------------------------------------------------
# 싱글턴 패턴
# ---------------------------------------------------------------------------

class TestSingleton:
    @patch("boto3.client")
    def test_get_uploader_same_instance(self, mock_boto):
        """get_uploader()는 동일 인스턴스를 반환."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        # 싱글턴 초기화
        s3_mod._uploader = None
        with patch.dict(os.environ, {"AWS_S3_BUCKET_NAME": "test-bucket"}):
            u1 = get_uploader()
            u2 = get_uploader()
        assert u1 is u2

        # teardown
        s3_mod._uploader = None


# ---------------------------------------------------------------------------
# get_url 형식
# ---------------------------------------------------------------------------

class TestGetUrl:
    @patch("boto3.client")
    def test_url_format(self, mock_boto):
        """URL 형식: https://{bucket}.s3.{region}.amazonaws.com/{key}."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        uploader = S3Uploader(bucket="my-bucket", region="ap-northeast-2")
        url = uploader.get_url("photos/1/123_test.jpg")

        assert url == "https://my-bucket.s3.ap-northeast-2.amazonaws.com/photos/1/123_test.jpg"
