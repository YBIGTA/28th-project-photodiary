"""Moondream 2 이미지 캡션/장면 설명 생성 모듈.

모델: vikhyatk/moondream2 (2B, HuggingFace Transformers)
- 이미지 → 자연어 캡션 생성
- VQA(Visual Q&A)로 키워드 추출 가능
- FP16 CUDA / BF16 CPU 자동 선택

실행 예시:
    python -m pipeline.moondream_captioner --image photos/test.jpg
    python -m pipeline.moondream_captioner --dir photos/
"""

from __future__ import annotations

import os
import argparse
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import torch
from PIL import Image


# ============================================================
# 데이터 클래스
# ============================================================

@dataclass
class CaptionResult:
    """이미지 1장의 캡션 결과."""
    file_path: str
    caption: str = ""
    tags_raw: str = ""


# ============================================================
# 설정
# ============================================================

MODEL_ID = "vikhyatk/moondream2"
MODEL_REVISION = "2025-01-09"

_model = None
_device = None


# ============================================================
# 모델 로드 / 해제
# ============================================================

def _select_device() -> torch.device:
    global _device
    if _device is not None:
        return _device
    if torch.cuda.is_available():
        _device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        _device = torch.device("mps")
    else:
        _device = torch.device("cpu")
    return _device


def load_model():
    """Moondream 2 모델 싱글톤 로드 (2025-01-09 API: tokenizer 내장)."""
    global _model

    if _model is not None:
        return _model

    from transformers import AutoModelForCausalLM

    device = _select_device()
    dtype = torch.float16 if device.type == "cuda" else torch.float32

    print(f"[Moondream] 모델 로드 중… (device={device}, dtype={dtype})")

    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        trust_remote_code=True,
        torch_dtype=dtype,
        device_map={"": str(device)},
    )
    _model.eval()

    print("[Moondream] 모델 로드 완료!")
    return _model


def unload_model():
    """Moondream 모델 메모리 해제 (VRAM 확보용)."""
    global _model
    if _model is not None:
        del _model
        _model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[Moondream] 모델 언로드 완료")


# ============================================================
# 공개 API (2025-01-09 신규 API: tokenizer 내장)
# ============================================================

def generate_caption(image_path: str, length: str = "normal") -> CaptionResult:
    """단일 이미지 캡션 생성."""
    model = load_model()
    img = Image.open(image_path).convert("RGB")

    result = model.caption(img, length=length)
    caption = result["caption"] if isinstance(result, dict) else str(result)

    return CaptionResult(file_path=image_path, caption=caption)


def generate_caption_and_tags(image_path: str, length: str = "normal") -> CaptionResult:
    """단일 이미지 캡션 + VQA 태그 동시 추출."""
    model = load_model()
    img = Image.open(image_path).convert("RGB")

    # 이미지 인코딩 1회 재사용
    encoded = model.encode_image(img)

    # 1) 캡션
    cap_result = model.caption(encoded, length=length)
    caption = cap_result["caption"] if isinstance(cap_result, dict) else str(cap_result)

    # 2) VQA 태그
    tag_prompt = (
        "List the main keywords describing this image as comma-separated tags. "
        "Include objects, people, activities, scene, colors, and mood."
    )
    tag_result = model.query(encoded, tag_prompt)
    tags_raw = tag_result["answer"] if isinstance(tag_result, dict) else str(tag_result)

    return CaptionResult(file_path=image_path, caption=caption, tags_raw=tags_raw)


def generate_captions_batch(
    image_paths: list[str],
    length: str = "normal",
    with_tags: bool = False,
    show_progress: bool = True,
) -> list[CaptionResult]:
    """여러 이미지 캡션 순차 생성."""
    model = load_model()
    total = len(image_paths)
    results: list[CaptionResult] = []

    tag_prompt = (
        "List the main keywords describing this image as comma-separated tags. "
        "Include objects, people, activities, scene, colors, and mood."
    )

    for i, path in enumerate(image_paths):
        try:
            img = Image.open(path).convert("RGB")
            encoded = model.encode_image(img)

            cap_result = model.caption(encoded, length=length)
            caption = cap_result["caption"] if isinstance(cap_result, dict) else str(cap_result)

            tags_raw = ""
            if with_tags:
                tag_result = model.query(encoded, tag_prompt)
                tags_raw = tag_result["answer"] if isinstance(tag_result, dict) else str(tag_result)

            results.append(CaptionResult(file_path=path, caption=caption, tags_raw=tags_raw))
        except Exception as e:
            print(f"  [ERROR] {path}: {e}")
            results.append(CaptionResult(file_path=path))

        if show_progress and ((i + 1) % 5 == 0 or i + 1 == total):
            print(f"  [{i+1}/{total}] 캡션 생성 완료")

    return results


# ============================================================
# CLI
# ============================================================

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}


def collect_image_paths(directory: str) -> list[str]:
    paths = []
    for root, _, files in os.walk(directory):
        for f in files:
            if Path(f).suffix.lower() in IMAGE_EXTENSIONS:
                paths.append(os.path.join(root, f))
    paths.sort()
    return paths


def main():
    parser = argparse.ArgumentParser(description="Moondream 2 이미지 캡션 생성")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=str, help="단일 이미지 파일 경로")
    group.add_argument("--dir", type=str, help="이미지 디렉토리 경로")
    parser.add_argument("--length", choices=["short", "normal"], default="normal")
    parser.add_argument("--with-tags", action="store_true", help="VQA 태그도 추출")
    args = parser.parse_args()

    if args.image:
        fn = generate_caption_and_tags if args.with_tags else generate_caption
        result = fn(args.image, length=args.length)
        print(f"\nFile: {result.file_path}")
        print(f"Caption: {result.caption}")
        if result.tags_raw:
            print(f"Tags: {result.tags_raw}")
    else:
        paths = collect_image_paths(args.dir)
        if not paths:
            print(f"No images found: {args.dir}")
            return
        print(f"Found {len(paths)} images")
        for r in generate_captions_batch(paths, length=args.length, with_tags=args.with_tags):
            print(f"\n  {r.file_path}")
            print(f"    Caption: {r.caption}")
            if r.tags_raw:
                print(f"    Tags: {r.tags_raw}")


if __name__ == "__main__":
    main()
