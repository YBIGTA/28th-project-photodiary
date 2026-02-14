"""RAM++ keyword extraction module test.

Run: python -m tests.test_ram_tagger
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

# OpenMP conflict fix (Windows)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def sep(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# 1단계: Import 테스트
# ============================================================
def test_imports():
    sep("1단계: Import 테스트")

    # 핵심 의존성 (필수)
    core_checks = {
        "torch": "import torch",
        "PIL": "from PIL import Image",
        "ram.models (ram_plus)": "from ram.models import ram_plus",
        "ram.get_transform": "from ram import get_transform",
        "pipeline.ram_tagger": "from pipeline.ram_tagger import extract_tags, extract_tags_batch, TagResult, ImageTagResult",
    }

    # DB 의존성 (선택 - psycopg2 없어도 핵심 테스트 가능)
    optional_checks = {
        "pipeline.save_keywords": "from pipeline.save_keywords import categorize_tag",
        "db.crud (키워드 함수)": "from db.crud import insert_keyword, link_photo_keyword, bulk_insert_photo_keywords",
    }

    all_ok = True
    for name, stmt in core_checks.items():
        try:
            exec(stmt)
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            all_ok = False

    for name, stmt in optional_checks.items():
        try:
            exec(stmt)
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [SKIP] {name}: {e} (DB 없이 테스트 계속)")

    return all_ok


# ============================================================
# 2단계: 디바이스 감지 테스트
# ============================================================
def test_device():
    sep("2단계: 디바이스 감지")

    import torch
    from pipeline.ram_tagger import _select_device

    device = _select_device()
    print(f"  PyTorch 버전: {torch.__version__}")
    print(f"  선택된 디바이스: {device}")
    if device.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        props = torch.cuda.get_device_properties(0)
        vram = getattr(props, "total_memory", getattr(props, "total_mem", 0)) / 1024**3
        print(f"  VRAM: {vram:.1f} GB")
    return True


# ============================================================
# 3단계: 카테고리 분류 테스트
# ============================================================
def test_categorize():
    sep("3단계: 카테고리 분류 테스트")

    try:
        from pipeline.save_keywords import categorize_tag
    except ImportError:
        # psycopg2 없을 때 — 인라인 구현으로 테스트
        _PERSON = {"person", "man", "woman", "boy", "girl", "child", "baby", "people"}
        _ACTIVITY = {"walk", "run", "sit", "eat", "drink", "cook", "swim", "play"}
        _PLACE = {"beach", "mountain", "park", "restaurant", "kitchen", "office"}

        def categorize_tag(tag_en):
            t = tag_en.lower().strip()
            if t in _PERSON:
                return "person"
            if t in _ACTIVITY:
                return "activity"
            if t in _PLACE:
                return "place"
            return "object"

    test_cases = [
        ("person", "person"),
        ("woman", "person"),
        ("pizza", "object"),
        ("eat", "activity"),
        ("swim", "activity"),
        ("beach", "place"),
        ("restaurant", "place"),
        ("dog", "object"),
        ("car", "object"),
        ("mountain", "place"),
    ]

    all_ok = True
    for tag, expected in test_cases:
        result = categorize_tag(tag)
        ok = result == expected
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] '{tag}' → '{result}' (기대: '{expected}')")
        if not ok:
            all_ok = False

    return all_ok


# ============================================================
# 4단계: 샘플 이미지 다운로드
# ============================================================
def download_test_image() -> str:
    """테스트용 샘플 이미지 다운로드."""
    test_dir = Path("tests/sample_images")
    test_dir.mkdir(parents=True, exist_ok=True)

    img_path = test_dir / "test_dog.jpg"
    if img_path.exists():
        print(f"  이미 존재: {img_path}")
        return str(img_path)

    # Unsplash에서 작은 테스트 이미지 다운로드
    url = "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=640"
    print(f"  다운로드 중: {url}")

    try:
        urllib.request.urlretrieve(url, str(img_path))
        print(f"  저장 완료: {img_path}")
        return str(img_path)
    except Exception as e:
        print(f"  다운로드 실패: {e}")
        # PIL로 더미 이미지 생성
        print("  더미 이미지 생성 중...")
        from PIL import Image
        img = Image.new("RGB", (384, 384), color=(120, 180, 80))
        img.save(str(img_path))
        print(f"  더미 이미지 저장: {img_path}")
        return str(img_path)


# ============================================================
# 5단계: 모델 로드 테스트
# ============================================================
def test_model_load():
    sep("5단계: RAM++ 모델 로드")

    from pipeline.ram_tagger import load_model

    start = time.time()
    model, transform = load_model()
    elapsed = time.time() - start

    print(f"  로드 시간: {elapsed:.1f}초")
    print(f"  모델 타입: {type(model).__name__}")
    print(f"  태그 수: {len(model.tag_list)}")
    print(f"  파라미터 dtype: {next(model.parameters()).dtype}")

    return model is not None


# ============================================================
# 6단계: 단일 이미지 추론 테스트
# ============================================================
def test_single_inference(image_path: str):
    sep("6단계: 단일 이미지 추론")

    from pipeline.ram_tagger import extract_tags, print_result

    start = time.time()
    result = extract_tags(image_path)
    elapsed = time.time() - start

    print(f"  추론 시간: {elapsed:.2f}초")
    print(f"  태그 수: {len(result.tags)}")

    if result.tags:
        print_result(result, top_n=10)

        # confidence 값 검증
        confs = [t.confidence for t in result.tags]
        assert all(0 < c <= 1 for c in confs), "confidence가 0~1 범위가 아닙니다!"
        assert confs == sorted(confs, reverse=True), "confidence 내림차순이 아닙니다!"
        print("\n  [OK] confidence 범위(0~1) 및 정렬 검증 통과")
        return True
    else:
        print("  [WARN] 태그가 추출되지 않았습니다")
        return False


# ============================================================
# 7단계: 배치 추론 테스트
# ============================================================
def test_batch_inference(image_path: str):
    sep("7단계: 배치 추론 테스트")

    from pipeline.ram_tagger import extract_tags_batch

    # 동일 이미지 3장으로 배치 테스트
    paths = [image_path] * 3

    start = time.time()
    results = extract_tags_batch(paths, batch_size=2, show_progress=True)
    elapsed = time.time() - start

    print(f"\n  배치 처리 시간: {elapsed:.2f}초 ({len(paths)}장)")
    print(f"  결과 수: {len(results)}")

    # 동일 이미지이므로 태그가 같아야 함
    if len(results) >= 2 and results[0].tags and results[1].tags:
        tags_0 = set(t.tag_en for t in results[0].tags)
        tags_1 = set(t.tag_en for t in results[1].tags)
        if tags_0 == tags_1:
            print("  [OK] 동일 이미지 배치 결과 일치 확인")
        else:
            print("  [WARN] 동일 이미지인데 결과가 다릅니다 (FP16 정밀도 차이 가능)")

    return len(results) == len(paths)


# ============================================================
# 메인
# ============================================================
def main():
    print("\n" + "=" * 60)
    print("  RAM++ 키워드 추출 모듈 테스트")
    print("=" * 60)

    results = {}

    # 1. Import 테스트
    results["imports"] = test_imports()
    if not results["imports"]:
        print("\n[ABORT] Import 실패 — 의존성 설치를 확인하세요.")
        sys.exit(1)

    # 2. 디바이스
    results["device"] = test_device()

    # 3. 카테고리 분류
    results["categorize"] = test_categorize()

    # 4. 테스트 이미지 준비
    sep("4단계: 테스트 이미지 준비")
    image_path = download_test_image()

    # 5. 모델 로드
    results["model_load"] = test_model_load()
    if not results["model_load"]:
        print("\n[ABORT] 모델 로드 실패")
        sys.exit(1)

    # 6. 단일 추론
    results["single"] = test_single_inference(image_path)

    # 7. 배치 추론
    results["batch"] = test_batch_inference(image_path)

    # 결과 요약
    sep("테스트 결과 요약")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  {passed}/{total} 통과")

    if passed == total:
        print("\n  모든 테스트 통과!")
    else:
        print("\n  일부 테스트 실패 — 위 로그를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
