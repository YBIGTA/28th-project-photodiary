"""사진 키워드/메타데이터를 벡터로 변환하는 임베딩 모듈.

모델: intfloat/multilingual-e5-base (768차원)
- 비대칭 검색 특화: query ↔ passage 구분
- 사진 키워드(passage)와 사용자 질문(query)의 관계를 잘 찾음
"""

from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = "intfloat/multilingual-e5-base"
EMBEDDING_DIM = 768

_model = None


def get_model():
    """모델 싱글톤 로드 (최초 호출 시 다운로드)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def build_photo_text(
    keywords: list[str],
    place_parts: dict | None = None,
    caption: str | None = None,
) -> str:
    """사진의 키워드 + 장면 캡션 + 장소 정보를 하나의 텍스트로 조합.

    Parameters
    ----------
    keywords : list[str]
        사진에서 추출된 키워드 목록 (RAM++ 등)
    place_parts : dict | None
        장소 메타데이터
    caption : str | None
        Moondream 2가 생성한 장면 설명 캡션

    Returns
    -------
    str — "passage: keyword1 keyword2 | caption text | 부산광역시 해운대구"
    """
    segments = []

    if keywords:
        segments.append(" ".join(keywords))

    if caption and caption.strip():
        segments.append(caption.strip())

    if place_parts:
        place_tokens = []
        for key in ("state", "city", "district", "road", "building"):
            val = place_parts.get(key)
            if val:
                place_tokens.append(val)
        if place_tokens:
            segments.append(" ".join(place_tokens))

    text = " | ".join(segments) if segments else ""
    return f"passage: {text}"


def build_query_text(query: str) -> str:
    """사용자 검색 쿼리에 e5 접두사 추가.

    Parameters
    ----------
    query : str — 사용자 자연어 쿼리
        예: "부산에서 피자 먹은 사진"

    Returns
    -------
    str — "query: 부산에서 피자 먹은 사진"
    """
    return f"query: {query}"


def embed_texts(texts: list[str]) -> np.ndarray:
    """텍스트 리스트를 벡터로 변환.

    Parameters
    ----------
    texts : list[str] — 변환할 텍스트 목록 (접두사 포함)

    Returns
    -------
    np.ndarray — shape (len(texts), 768)
    """
    model = get_model()
    return model.encode(texts, normalize_embeddings=True)


def embed_photo(
    keywords: list[str],
    place_parts: dict | None = None,
    caption: str | None = None,
) -> np.ndarray:
    """사진 1장의 키워드+캡션+장소 → 768차원 벡터.

    Returns
    -------
    np.ndarray — shape (768,)
    """
    text = build_photo_text(keywords, place_parts, caption)
    return embed_texts([text])[0]


def embed_query(query: str) -> np.ndarray:
    """사용자 쿼리 → 768차원 벡터.

    Returns
    -------
    np.ndarray — shape (768,)
    """
    text = build_query_text(query)
    return embed_texts([text])[0]


# ── 단독 테스트 ──
if __name__ == "__main__":
    print(f"모델 로드 중: {MODEL_NAME}")
    model = get_model()
    print(f"모델 로드 완료 (차원: {EMBEDDING_DIM})")

    # 사진 임베딩 테스트
    photo_vec = embed_photo(
        keywords=["피자", "크리스마스트리", "사람", "식사"],
        place_parts={"city": "부산광역시", "district": "해운대구", "building": "이재모피자"},
    )
    print(f"\n사진 벡터: shape={photo_vec.shape}, norm={np.linalg.norm(photo_vec):.4f}")

    # 쿼리 임베딩 테스트
    query_vec = embed_query("부산에서 피자 먹은 사진")
    print(f"쿼리 벡터: shape={query_vec.shape}, norm={np.linalg.norm(query_vec):.4f}")

    # 유사도 테스트
    similarity = np.dot(photo_vec, query_vec)
    print(f"\n유사도 (cosine): {similarity:.4f}")

    # 관련 없는 쿼리와 비교
    other_vec = embed_query("서울에서 커피 마신 사진")
    other_sim = np.dot(photo_vec, other_vec)
    print(f"비관련 유사도:    {other_sim:.4f}")
