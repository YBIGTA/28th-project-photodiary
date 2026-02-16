"""
DB에 저장된 사진 → RAM++ 키워드 + Moondream 캡션 추출 → DB 저장

파이프라인 흐름:
  1. photos 테이블에서 사진 목록 조회
  2. 이미 키워드가 있는 사진은 스킵 (--force 로 재추출 가능)
  3. RAM++ 배치 추론으로 태그 + confidence 추출 → keywords/photo_keywords 저장
  4. (선택) Moondream 2 캡션 생성 → photos.caption 저장

실행:
  python -m pipeline.save_keywords                          # RAM++ 키워드만
  python -m pipeline.save_keywords --with-caption           # RAM++ + Moondream 캡션
  python -m pipeline.save_keywords --caption-only           # Moondream 캡션만
  python -m pipeline.save_keywords --with-caption --force   # 전체 재추출
"""

from __future__ import annotations

import os
import sys
import argparse

from dotenv import load_dotenv

load_dotenv()

from db.schema import get_connection
from db.crud import (
    list_photos,
    bulk_insert_photo_keywords,
    delete_photo_keywords,
    get_photo_keyword_count,
    update_caption,
)
from pipeline.ram_tagger import extract_tags_batch, ImageTagResult, TagResult

USER_ID = 1  # 단일 사용자 고정


# ============================================================
# 태그 카테고리 분류
# ============================================================

# 대표 태그 → 카테고리 매핑 (RAM++ 4585 태그 중 주요 분류)
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


# ============================================================
# 메인 파이프라인
# ============================================================

def process_photos(
    batch_size: int = 4,
    threshold: float | None = None,
    force: bool = False,
    limit: int = 10000,
    with_caption: bool = False,
    caption_only: bool = False,
):
    """사진 키워드 추출 + 캡션 생성 → DB 저장 파이프라인.

    Parameters
    ----------
    batch_size : int — RAM++ 배치 크기
    threshold : float | None — 태그 임계값
    force : bool — True이면 기존 데이터 삭제 후 재추출
    limit : int — 처리할 최대 사진 수
    with_caption : bool — Moondream 캡션도 생성할지
    caption_only : bool — Moondream 캡션만 생성 (RAM++ 스킵)
    """
    conn = get_connection()
    run_ram = not caption_only
    run_moondream = with_caption or caption_only

    try:
        photos = list_photos(conn, USER_ID, limit=limit)
        if not photos:
            print("DB에 저장된 사진이 없습니다.")
            return

        print(f"총 {len(photos)}장 사진 발견")

        # 처리 대상 필터링
        targets = []
        for photo in photos:
            photo_id = photo["id"]
            file_path = photo["file_path"]

            if not os.path.isfile(file_path):
                print(f"  [SKIP] photo_id={photo_id}: 파일 없음 ({file_path})")
                continue

            if not force:
                # RAM++ 키워드 이미 있고, 캡션도 이미 있으면 스킵
                has_keywords = get_photo_keyword_count(conn, photo_id) > 0
                has_caption = bool(photo.get("caption"))

                skip_ram = has_keywords or not run_ram
                skip_moon = has_caption or not run_moondream

                if skip_ram and skip_moon:
                    print(f"  [SKIP] photo_id={photo_id}: 이미 처리됨")
                    continue

            targets.append(photo)

        if not targets:
            print("처리할 사진이 없습니다. (--force 옵션으로 재추출 가능)")
            return

        path_to_photo = {p["file_path"]: p for p in targets}
        file_paths = [p["file_path"] for p in targets]

        modes = []
        if run_ram:
            modes.append("RAM++ 키워드")
        if run_moondream:
            modes.append("Moondream 캡션")

        print(f"\n{len(targets)}장 사진 분석 시작… [{' + '.join(modes)}]")
        print(f"  재추출 모드: {'ON' if force else 'OFF'}")
        print()

        # ────────────────────────────────────────────
        # Phase 1: RAM++ 키워드 추출
        # ────────────────────────────────────────────
        total_keywords = 0
        saved_kw_photos = 0

        if run_ram:
            print(f"── Phase 1: RAM++ 키워드 추출 (batch_size={batch_size}) ──")

            results = extract_tags_batch(
                file_paths,
                batch_size=batch_size,
                threshold=threshold,
                show_progress=True,
            )

            for result in results:
                photo = path_to_photo.get(result.file_path)
                if photo is None or not result.tags:
                    continue

                photo_id = photo["id"]

                if force:
                    deleted = delete_photo_keywords(conn, photo_id)
                    if deleted > 0:
                        print(f"  [DEL] photo_id={photo_id}: 기존 {deleted}개 키워드 삭제")

                keyword_data = [
                    (tag.tag_en, categorize_tag(tag.tag_en), tag.confidence)
                    for tag in result.tags
                ]
                saved = bulk_insert_photo_keywords(conn, photo_id, keyword_data)

                top3 = ", ".join(
                    f"{t.tag_en}({t.confidence:.2f})" for t in result.tags[:3]
                )
                print(f"  [OK] photo_id={photo_id} | {saved}개 태그 | 상위: {top3}")

                total_keywords += saved
                saved_kw_photos += 1

            # RAM++ 모델 VRAM 해제 (Moondream 로드 전)
            if run_moondream:
                from pipeline.ram_tagger import _model as ram_model
                import pipeline.ram_tagger as ram_mod
                if ram_mod._model is not None:
                    del ram_mod._model
                    ram_mod._model = None
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    print("\n  [MEM] RAM++ 모델 VRAM 해제 완료")

        # ────────────────────────────────────────────
        # Phase 2: Moondream 캡션 생성
        # ────────────────────────────────────────────
        saved_cap_photos = 0

        if run_moondream:
            print(f"\n── Phase 2: Moondream 캡션 생성 ──")

            from pipeline.moondream_captioner import (
                generate_captions_batch,
                unload_model as unload_moondream,
            )

            # 캡션 필요한 사진만 필터
            if force:
                cap_paths = file_paths
            else:
                cap_paths = [
                    p for p in file_paths
                    if not path_to_photo[p].get("caption")
                ]

            if cap_paths:
                cap_results = generate_captions_batch(
                    cap_paths, length="normal", show_progress=True,
                )

                for cap in cap_results:
                    photo = path_to_photo.get(cap.file_path)
                    if photo is None or not cap.caption:
                        continue

                    update_caption(conn, photo["id"], cap.caption)

                    cap_preview = cap.caption[:50] + "…" if len(cap.caption) > 50 else cap.caption
                    print(f"  [CAP] photo_id={photo['id']} | {cap_preview}")
                    saved_cap_photos += 1

            # Moondream 모델 해제
            unload_moondream()

        # ────────────────────────────────────────────
        # 결과 요약
        # ────────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"완료!")
        if run_ram:
            avg_kw = total_keywords / saved_kw_photos if saved_kw_photos else 0
            print(f"  [RAM++] {saved_kw_photos}장, {total_keywords}개 키워드 (평균 {avg_kw:.1f}개/장)")
        if run_moondream:
            print(f"  [Moondream] {saved_cap_photos}장 캡션 생성")

    except Exception as e:
        conn.rollback()
        print(f"\n오류 발생: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="RAM++ 키워드 + Moondream 캡션 → DB 저장 파이프라인"
    )
    parser.add_argument(
        "--batch-size", type=int, default=4,
        help="RAM++ 배치 크기 (GPU VRAM에 따라 조절, 기본: 4)",
    )
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="태그 임계값 (기본: 태그별 최적 임계값 사용)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="기존 데이터 삭제 후 재추출",
    )
    parser.add_argument(
        "--limit", type=int, default=10000,
        help="처리할 최대 사진 수 (기본: 10000)",
    )
    parser.add_argument(
        "--with-caption", action="store_true",
        help="Moondream 2 캡션도 같이 생성 (RAM++ + Moondream)",
    )
    parser.add_argument(
        "--caption-only", action="store_true",
        help="Moondream 2 캡션만 생성 (RAM++ 스킵)",
    )
    args = parser.parse_args()

    process_photos(
        batch_size=args.batch_size,
        threshold=args.threshold,
        force=args.force,
        limit=args.limit,
        with_caption=args.with_caption,
        caption_only=args.caption_only,
    )


if __name__ == "__main__":
    main()
