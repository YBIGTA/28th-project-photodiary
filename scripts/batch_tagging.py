from __future__ import annotations
"""
DB에 저장된 사진 → RAM++ 키워드 + Moondream 캡션 추출 → DB 저장 (관리자 CLI 도구)

실행:
  python scripts/batch_tagging.py                          # RAM++ 키워드만 (전체 유저)
  python scripts/batch_tagging.py --with-caption           # RAM++ + Moondream 캡션
  python scripts/batch_tagging.py --caption-only           # Moondream 캡션만
  python scripts/batch_tagging.py --user-id 1 --force     # 특정 유저 전체 재추출
"""

from typing import Optional

import os
import sys
import argparse
import tempfile

from dotenv import load_dotenv

load_dotenv()

from db.schema import get_connection
from db.crud import (
    list_photos,
    bulk_insert_photo_keywords,
    delete_photo_keywords,
    get_photo_keyword_count,
    update_caption,
    list_all_user_ids,
)
from pipeline.core.ram_tagger import extract_tags_batch, ImageTagResult, TagResult, categorize_tag
from pipeline.utils.s3_uploader import download_from_s3


# ============================================================
# S3 경로 처리 헬퍼
# ============================================================

def _extract_s3_key(file_path: str) -> str:
    """DB의 file_path가 S3 URL이든 Key이든 Key만 추출한다."""
    if file_path.startswith("http://") or file_path.startswith("https://"):
        from urllib.parse import urlparse
        parsed = urlparse(file_path)
        return parsed.path.lstrip("/")
    return file_path


def _is_s3_path(file_path: str) -> bool:
    """file_path가 S3 URL(http/https) 또는 S3 Key 형식(photos/...)인지 확인한다."""
    if file_path.startswith("http://") or file_path.startswith("https://"):
        return True
    # S3 Key는 로컬 절대 경로가 아님: '/'로 시작하지 않고, OS 절대 경로도 아님
    if not os.path.isabs(file_path) and not os.path.exists(file_path):
        return True
    return False


# ============================================================
# S3 경로 처리 헬퍼
# ============================================================

def process_photos(
    user_id: int,
    batch_size: int = 4,
    threshold: Optional[float] = None,
    force: bool = False,
    limit: int = 10000,
    with_caption: bool = False,
    caption_only: bool = False,
):
    """사진 키워드 추출 + 캡션 생성 → DB 저장 파이프라인.

    Parameters
    ----------
    user_id : int — 처리할 사용자 ID
    batch_size : int — RAM++ 배치 크기
    threshold : Optional[float] — 태그 임계값
    force : bool — True이면 기존 데이터 삭제 후 재추출
    limit : int — 처리할 최대 사진 수
    with_caption : bool — Moondream 캡션도 생성할지
    caption_only : bool — Moondream 캡션만 생성 (RAM++ 스킵)
    """
    conn = get_connection()
    run_ram = not caption_only
    run_moondream = with_caption or caption_only

    try:
        photos = list_photos(conn, user_id, limit=limit)
        if not photos:
            print(f"[user_id={user_id}] DB에 저장된 사진이 없습니다.")
            return

        print(f"[user_id={user_id}] 총 {len(photos)}장 사진 발견")

        # 처리 대상 필터링 (로컬 파일 + S3 파일 모두 허용)
        targets = []
        for photo in photos:
            photo_id = photo["id"]
            file_path = photo["file_path"]

            # 로컬 파일도 아니고 S3 경로도 아니면 스킵
            is_s3 = _is_s3_path(file_path)
            if not is_s3 and not os.path.isfile(file_path):
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

        # 원본 DB file_path → photo 매핑
        path_to_photo = {p["file_path"]: p for p in targets}
        db_file_paths = [p["file_path"] for p in targets]

        modes = []
        if run_ram:
            modes.append("RAM++ 키워드")
        if run_moondream:
            modes.append("Moondream 캡션")

        print(f"\n{len(targets)}장 사진 분석 시작… [{' + '.join(modes)}]")
        print(f"  재추출 모드: {'ON' if force else 'OFF'}")
        print()

        # S3 이미지 임시 다운로드: local_path → 원본 db_path 매핑
        tmp_dir = tempfile.mkdtemp(prefix="tagging_cache_")
        local_path_to_db_path: dict[str, str] = {}  # 로컬 임시 경로 → DB file_path
        local_file_paths: list[str] = []  # AI 모델에 넘길 실제 로컬 경로 목록

        try:
            for db_path in db_file_paths:
                if _is_s3_path(db_path):
                    s3_key = _extract_s3_key(db_path)
                    ext = os.path.splitext(s3_key)[1].lower() or ".jpg"
                    tmp_img = tempfile.NamedTemporaryFile(
                        delete=False, suffix=ext, dir=tmp_dir
                    )
                    tmp_img.close()
                    try:
                        download_from_s3(s3_key, tmp_img.name)
                        local_path_to_db_path[tmp_img.name] = db_path
                        local_file_paths.append(tmp_img.name)
                        print(f"  [S3] 다운로드 완료: {s3_key} → {tmp_img.name}")
                    except Exception as e:
                        print(f"  [SKIP] S3 다운로드 실패 ({db_path}): {e}")
                        os.unlink(tmp_img.name)
                else:
                    local_path_to_db_path[db_path] = db_path
                    local_file_paths.append(db_path)


            # ────────────────────────────────────────────
            # Phase 1: RAM++ 키워드 추출
            # ────────────────────────────────────────────
            total_keywords = 0
            saved_kw_photos = 0

            if run_ram:
                print(f"── Phase 1: RAM++ 키워드 추출 (batch_size={batch_size}) ──")

                results = extract_tags_batch(
                    local_file_paths,
                    batch_size=batch_size,
                    threshold=threshold,
                    show_progress=True,
                )

                for result in results:
                    # 로컬 임시 경로 → 원본 DB file_path → photo 매핑
                    db_path = local_path_to_db_path.get(result.file_path)
                    photo = path_to_photo.get(db_path) if db_path else None
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
                    import pipeline.core.ram_tagger as ram_mod
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

                from pipeline.core.moondream import (
                    generate_captions_batch,
                    unload_model as unload_moondream,
                )

                # 캡션 필요한 사진만 필터 (로컬 경로 기준)
                if force:
                    cap_paths = local_file_paths
                else:
                    cap_paths = [
                        lp for lp in local_file_paths
                        if not path_to_photo[local_path_to_db_path[lp]].get("caption")
                    ]

                if cap_paths:
                    cap_results = generate_captions_batch(
                        cap_paths, length="normal", show_progress=True,
                    )

                    for cap in cap_results:
                        # 로컬 임시 경로 → 원본 DB file_path → photo 매핑
                        db_path = local_path_to_db_path.get(cap.file_path)
                        photo = path_to_photo.get(db_path) if db_path else None
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
            # S3 에서 다운로드한 임시 파일 전체 정리
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

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
        "--user-id", type=int, default=None,
        help="처리할 사용자 ID (미지정 시 전체 유저 처리)",
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

    conn_tmp = get_connection()
    try:
        user_ids = [args.user_id] if args.user_id else list_all_user_ids(conn_tmp)
    finally:
        conn_tmp.close()

    for uid in user_ids:
        process_photos(
            user_id=uid,
            batch_size=args.batch_size,
            threshold=args.threshold,
            force=args.force,
            limit=args.limit,
            with_caption=args.with_caption,
            caption_only=args.caption_only,
        )


if __name__ == "__main__":
    main()
