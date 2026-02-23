"""RAM++ (Recognize Anything Plus Plus) 이미지 태그/키워드 추출 모듈.

모델: RAM++ Swin-Large (384×384 입력)
- 4585개 사전 정의 태그 카테고리 지원
- 영어 + 중국어 태그 동시 출력
- confidence score 기반 필터링

체크포인트: HuggingFace 에서 자동 다운로드
  xinyu1205/recognize-anything-plus-model → ram_plus_swin_large_14m.pth

실행 예시:
    python -m pipeline.ram_tagger --image photos/test.jpg
    python -m pipeline.ram_tagger --dir photos/ --batch-size 4
"""

from __future__ import annotations

import os
import argparse
from dataclasses import dataclass, field
from pathlib import Path

# OpenMP 충돌 방지 (Windows + conda 환경)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

# ── RAM++ 패키지 ──
from ram.models import ram_plus
from ram import get_transform


# ============================================================
# 데이터 클래스
# ============================================================

@dataclass
class TagResult:
    """단일 태그 결과."""
    tag_en: str          # 영어 태그 (예: "pizza")
    tag_zh: str          # 중국어 태그 (예: "比萨饼")
    confidence: float    # 신뢰도 0~1


@dataclass
class ImageTagResult:
    """이미지 1장의 태그 추출 결과."""
    file_path: str
    tags: list[TagResult] = field(default_factory=list)


# ============================================================
# 설정
# ============================================================

MODEL_IMAGE_SIZE = 384
MODEL_VIT = "swin_l"

# HuggingFace repo 에서 자동 다운로드 (환경변수로 오버라이드 가능)
_HF_REPO = "xinyu1205/recognize-anything-plus-model"
_HF_FILENAME = "ram_plus_swin_large_14m.pth"

# 싱글톤
_model = None
_transform = None
_device = None


# ============================================================
# 디바이스·모델 로드
# ============================================================

def _select_device() -> torch.device:
    """최적 디바이스 자동 선택 (CUDA > MPS > CPU)."""
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


def _resolve_checkpoint() -> str:
    """체크포인트 경로 결정: 환경변수 → 로컬 → HuggingFace 자동 다운로드."""
    # 1) 환경변수로 직접 경로 지정
    env_path = os.getenv("RAM_PLUS_CHECKPOINT")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2) 프로젝트 내 pretrained/ 폴더
    local_path = Path("pretrained") / _HF_FILENAME
    if local_path.is_file():
        return str(local_path)

    # 3) huggingface_hub 자동 다운로드
    print(f"체크포인트를 HuggingFace에서 다운로드합니다: {_HF_REPO}/{_HF_FILENAME}")
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo_id=_HF_REPO, filename=_HF_FILENAME)


def load_model(pretrained_path: str | None = None):
    """RAM++ 모델 싱글톤 로드.

    Returns
    -------
    tuple[nn.Module, transforms] — (model, transform)
    """
    global _model, _transform

    if _model is not None:
        return _model, _transform

    device = _select_device()
    checkpoint = pretrained_path or _resolve_checkpoint()

    print(f"[RAM++] 모델 로드 중… (device={device}, ckpt={checkpoint})")

    _transform = get_transform(image_size=MODEL_IMAGE_SIZE)

    _model = ram_plus(
        pretrained=checkpoint,
        image_size=MODEL_IMAGE_SIZE,
        vit=MODEL_VIT,
    )
    _model.eval()
    _model.to(device)

    # GPU: FP16 최적화 (메모리 절반, 속도 향상)
    if device.type == "cuda":
        _model.half()

    print("[RAM++] 모델 로드 완료!")
    return _model, _transform


# ============================================================
# 내부 추론 (confidence 포함)
# ============================================================

def _inference_with_confidence(
    model,
    images: torch.Tensor,
    threshold: float | None = None,
) -> list[tuple[list[tuple[str, str]], list[float]]]:
    """RAM++ 모델 내부 logits에서 태그 + confidence 추출.

    RAM++ 고유 아키텍처: 태그별 다중 설명(description) 임베딩을
    이미지-태그 정렬(alignment)로 reweight 한 뒤 tagging head에 전달.

    Parameters
    ----------
    model : RAM++ 모델 (RAM_plus)
    images : torch.Tensor — shape (B, 3, 384, 384)
    threshold : float | None — 전역 임계값 (None이면 태그별 기본 임계값 사용)

    Returns
    -------
    list — 배치 내 각 이미지별 (tags, confidences)
        tags: list[(tag_en, tag_zh)]
        confidences: list[float]
    """
    # ── 이미지 인코딩 ──
    image_embeds = model.image_proj(model.visual_encoder(images))
    image_atts = torch.ones(
        image_embeds.size()[:-1], dtype=torch.long, device=images.device
    )

    image_cls_embeds = image_embeds[:, 0, :]
    bs = image_embeds.shape[0]

    # ── RAM++ 태그 설명 reweight (핵심 차이점) ──
    # label_embed shape: (num_class * des_per_class, 512)
    des_per_class = int(model.label_embed.shape[0] / model.num_class)

    image_cls_norm = image_cls_embeds / image_cls_embeds.norm(dim=-1, keepdim=True)
    reweight_scale = model.reweight_scale.exp()
    logits_per_image = reweight_scale * image_cls_norm @ model.label_embed.t()
    logits_per_image = logits_per_image.view(bs, -1, des_per_class)

    weight_normalized = F.softmax(logits_per_image, dim=2)
    label_embed_reweight = torch.empty(
        bs, model.num_class, 512, device=images.device, dtype=images.dtype
    )

    reshaped_value = model.label_embed.view(-1, des_per_class, 512)
    for i in range(bs):
        product = weight_normalized[i].unsqueeze(-1) * reshaped_value
        label_embed_reweight[i] = product.sum(dim=1)

    label_embed = F.relu(model.wordvec_proj(label_embed_reweight))

    # ── Tagging head 추론 ──
    tagging_embed = model.tagging_head(
        encoder_embeds=label_embed,
        encoder_hidden_states=image_embeds,
        encoder_attention_mask=image_atts,
        return_dict=False,
        mode="tagging",
    )

    logits = model.fc(tagging_embed[0]).squeeze(-1)

    # float32로 변환 후 sigmoid → confidence
    probs = torch.sigmoid(logits.float()).cpu().numpy()  # (B, num_class)

    # 임계값 결정
    class_threshold = model.class_threshold.numpy()
    if threshold is not None:
        class_threshold = np.full_like(class_threshold, threshold)

    delete_idx = getattr(model, "delete_tag_index", [])

    results = []
    for b in range(bs):
        indices = np.where(probs[b] > class_threshold)[0]

        # 삭제 태그 필터
        if delete_idx:
            indices = np.setdiff1d(indices, delete_idx)

        # confidence 내림차순 정렬
        sorted_idx = indices[np.argsort(-probs[b][indices])]

        tags = [
            (model.tag_list[i], model.tag_list_chinese[i])
            for i in sorted_idx
        ]
        confidences = [float(probs[b][i]) for i in sorted_idx]

        results.append((tags, confidences))

    return results


# ============================================================
# 공개 API — 단일 이미지
# ============================================================

def extract_tags(
    image_path: str,
    threshold: float | None = None,
) -> ImageTagResult:
    """단일 이미지에서 태그 + confidence 추출.

    Parameters
    ----------
    image_path : str — 이미지 파일 경로
    threshold : float | None — 태그 임계값 (None → 태그별 기본값)

    Returns
    -------
    ImageTagResult — 태그 목록 (confidence 내림차순)
    """
    model, transform = load_model()
    device = _select_device()

    img = Image.open(image_path).convert("RGB")
    tensor = transform(img).unsqueeze(0).to(device)

    if device.type == "cuda" and next(model.parameters()).dtype == torch.float16:
        tensor = tensor.half()

    with torch.no_grad():
        batch_result = _inference_with_confidence(model, tensor, threshold)

    tags_raw, confs = batch_result[0]

    tags = [
        TagResult(tag_en=en, tag_zh=zh, confidence=c)
        for (en, zh), c in zip(tags_raw, confs)
    ]
    return ImageTagResult(file_path=image_path, tags=tags)


# ============================================================
# 공개 API — 배치 처리
# ============================================================

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}


def extract_tags_batch(
    image_paths: list[str],
    batch_size: int = 8,
    threshold: float | None = None,
    show_progress: bool = True,
) -> list[ImageTagResult]:
    """배치 처리로 여러 이미지의 태그 추출.

    Parameters
    ----------
    image_paths : list[str] — 이미지 파일 경로 목록
    batch_size : int — 배치 크기 (GPU VRAM에 따라 조절)
    threshold : float | None — 태그 임계값
    show_progress : bool — 진행률 표시

    Returns
    -------
    list[ImageTagResult] — 각 이미지별 결과 (입력 순서 보장)
    """
    model, transform = load_model()
    device = _select_device()
    use_fp16 = device.type == "cuda" and next(model.parameters()).dtype == torch.float16

    total = len(image_paths)
    results: list[ImageTagResult] = []

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_paths = image_paths[start:end]

        # 이미지 로드 + 전처리
        tensors: list[torch.Tensor] = []
        valid_indices: list[int] = []  # results 내 유효 위치

        for i, path in enumerate(batch_paths):
            try:
                img = Image.open(path).convert("RGB")
                tensors.append(transform(img))
                valid_indices.append(start + i)
            except Exception as e:
                print(f"  [ERROR] {path}: {e}")
                results.append(ImageTagResult(file_path=path, tags=[]))

        if not tensors:
            continue

        batch_tensor = torch.stack(tensors).to(device)
        if use_fp16:
            batch_tensor = batch_tensor.half()

        with torch.no_grad():
            batch_result = _inference_with_confidence(model, batch_tensor, threshold)

        for idx_in_batch, (tags_raw, confs) in enumerate(batch_result):
            path = image_paths[valid_indices[idx_in_batch]]
            tags = [
                TagResult(tag_en=en, tag_zh=zh, confidence=c)
                for (en, zh), c in zip(tags_raw, confs)
            ]
            results.append(ImageTagResult(file_path=path, tags=tags))

        if show_progress:
            print(f"  [{end}/{total}] 처리 완료")

    return results


# ============================================================
# 유틸리티
# ============================================================

def collect_image_paths(directory: str) -> list[str]:
    """디렉토리 내 이미지 파일 경로 수집 (재귀)."""
    paths = []
    for root, _, files in os.walk(directory):
        for f in files:
            if Path(f).suffix.lower() in IMAGE_EXTENSIONS:
                paths.append(os.path.join(root, f))
    paths.sort()
    return paths


def print_result(result: ImageTagResult, top_n: int = 15):
    """태그 결과를 보기 좋게 출력."""
    print(f"\n{'='*60}")
    print(f"파일: {result.file_path}")
    print(f"태그 수: {len(result.tags)}")
    print(f"{'-'*60}")
    for i, tag in enumerate(result.tags[:top_n]):
        bar = "█" * int(tag.confidence * 20)
        print(f"  {i+1:2d}. {tag.tag_en:<25} {tag.confidence:.3f} {bar}")
    if len(result.tags) > top_n:
        print(f"  ... 외 {len(result.tags) - top_n}개")


# ============================================================
# CLI 실행
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="RAM++ 이미지 태그 추출")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=str, help="단일 이미지 파일 경로")
    group.add_argument("--dir", type=str, help="이미지 디렉토리 경로")
    parser.add_argument("--batch-size", type=int, default=4, help="배치 크기 (기본: 4)")
    parser.add_argument("--threshold", type=float, default=None, help="태그 임계값")
    parser.add_argument("--top-n", type=int, default=15, help="출력할 상위 태그 수")
    args = parser.parse_args()

    if args.image:
        result = extract_tags(args.image, threshold=args.threshold)
        print_result(result, top_n=args.top_n)
    else:
        paths = collect_image_paths(args.dir)
        if not paths:
            print(f"이미지를 찾을 수 없습니다: {args.dir}")
            return
        print(f"총 {len(paths)}장 이미지 발견")
        results = extract_tags_batch(
            paths,
            batch_size=args.batch_size,
            threshold=args.threshold,
        )
        for r in results:
            print_result(r, top_n=args.top_n)

        # 요약
        total_tags = sum(len(r.tags) for r in results)
        avg_tags = total_tags / len(results) if results else 0
        print(f"\n{'='*60}")
        print(f"총 {len(results)}장, 평균 {avg_tags:.1f}개 태그/장")


if __name__ == "__main__":
    main()


# ============================================================
# 태그 카테고리 분류 (DB 저장용)
# ============================================================

_PERSON_TAGS = frozenset({
    "person", "man", "woman", "boy", "girl", "child", "baby", "people",
    "teenager", "adult", "elder", "couple", "crowd", "family", "kid",
    "female", "male", "lady", "gentleman", "toddler", "infant",
    "bride", "groom", "model", "player", "athlete", "soldier",
    "student", "teacher", "chef", "doctor", "nurse", "worker",
})

_ACTIVITY_TAGS = frozenset({
    "walk", "run", "sit", "stand", "eat", "drink", "cook", "read",
    "write", "play", "swim", "dance", "sing", "jump", "climb",
    "ride", "drive", "fly", "ski", "surf", "skate", "hike",
    "sleep", "lay", "talk", "smile", "laugh", "cry", "wave",
    "throw", "catch", "kick", "hit", "hold", "carry", "push",
    "pull", "lift", "cut", "paint", "draw", "photograph", "shop",
    "travel", "camp", "fish", "hunt", "celebrate", "pray",
    "exercise", "stretch", "yoga", "meditate", "work", "study",
    "race", "compete", "perform", "juggle", "balance",
})

_PLACE_TAGS = frozenset({
    "beach", "mountain", "forest", "park", "garden", "street",
    "road", "bridge", "building", "house", "apartment", "hotel",
    "restaurant", "cafe", "bar", "church", "temple", "mosque",
    "school", "university", "hospital", "airport", "station",
    "market", "mall", "store", "shop", "museum", "library",
    "stadium", "gym", "pool", "playground", "zoo", "aquarium",
    "farm", "field", "lake", "river", "ocean", "sea", "island",
    "desert", "cave", "waterfall", "city", "town", "village",
    "countryside", "suburb", "downtown", "harbor", "port",
    "kitchen", "bedroom", "bathroom", "living room", "office",
    "classroom", "hallway", "balcony", "rooftop", "basement",
    "garage", "yard", "patio", "courtyard", "lobby",
})


def categorize_tag(tag_en: str) -> str:
    """RAM++ 영어 태그를 DB 카테고리로 분류.

    Returns
    -------
    str — 'person' | 'activity' | 'place' | 'object'
    """
    tag_lower = tag_en.lower().strip()
    if tag_lower in _PERSON_TAGS:
        return "person"
    if tag_lower in _ACTIVITY_TAGS:
        return "activity"
    if tag_lower in _PLACE_TAGS:
        return "place"
    return "object"
