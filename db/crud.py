"""photos 테이블 CRUD 함수 + embedding 관련 함수"""

from pipeline.geocoder import PlaceInfo
import numpy as np


def insert_photo(conn, user_id, file_path, lat, lon, place_info=None, taken_at=None):
    """
    photos 테이블에 한 장 INSERT.

    Parameters
    ----------
    conn : psycopg2 connection
    user_id : int
    file_path : str          — 이미지 파일 경로
    lat, lon : float | None  — 위도/경도
    place_info : PlaceInfo | None
    taken_at : datetime | None — 촬영 시각

    Returns
    -------
    int — 생성된 photo id
    """
    state = city = district = road = building = full_address = None
    if place_info:
        state = place_info.state or None
        city = place_info.city or None
        district = place_info.district or None
        road = place_info.road or None
        building = place_info.building or None
        full_address = place_info.full_address or None

    sql = """
        INSERT INTO photos
            (user_id, file_path, taken_at, latitude, longitude,
             state, city, district, road, building, full_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            user_id, file_path, taken_at, lat, lon,
            state, city, district, road, building, full_address,
        ))
        photo_id = cur.fetchone()[0]
    conn.commit()
    return photo_id


def get_photo(conn, photo_id):
    """photo_id로 한 장 조회 → dict (없으면 None)"""
    sql = """
        SELECT id, user_id, file_path, taken_at,
               latitude, longitude,
               state, city, district, road, building, full_address,
               event_id, created_at
        FROM photos
        WHERE id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def list_photos(conn, user_id, limit=100):
    """user_id에 해당하는 사진 목록 → list[dict] (기본 최근 100개)"""
    sql = """
        SELECT id, user_id, file_path, taken_at,
               latitude, longitude,
               state, city, district, road, building, full_address,
               event_id, created_at
        FROM photos
        WHERE user_id = %s
        ORDER BY taken_at DESC, id DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, limit))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def update_event_id(conn, photo_id, event_id):
    """사진의 event_id 업데이트"""
    sql = "UPDATE photos SET event_id = %s WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (event_id, photo_id))
    conn.commit()


def update_importance(conn, photo_id, keyword_id, importance):
    """photo_keywords 테이블의 importance 점수 업데이트"""
    sql = """
        UPDATE photo_keywords
        SET importance = %s
        WHERE photo_id = %s AND keyword_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (importance, photo_id, keyword_id))
    conn.commit()


# ── Embedding 관련 ──

def insert_embedding(conn, photo_id, embedding):
    """photo_embeddings 테이블에 벡터 INSERT (이미 존재하면 업데이트).

    Parameters
    ----------
    conn : psycopg2 connection
    photo_id : int
    embedding : np.ndarray | list — 768차원 벡터
    """
    vec = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
    sql = """
        INSERT INTO photo_embeddings (photo_id, embedding)
        VALUES (%s, %s)
        ON CONFLICT (photo_id) DO UPDATE SET embedding = EXCLUDED.embedding
    """
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id, vec))
    conn.commit()


def get_embedding(conn, photo_id):
    """photo_id의 임베딩 벡터 조회.

    Returns
    -------
    np.ndarray | None — 768차원 벡터 (없으면 None)
    """
    sql = "SELECT embedding FROM photo_embeddings WHERE photo_id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id,))
        row = cur.fetchone()
        if row is None:
            return None
    return np.array(row[0])


# ── Semantic Search ──

def search_photos(conn, query_embedding, user_id, limit=5):
    """벡터 유사도 기반 사진 검색 (cosine similarity).

    Parameters
    ----------
    conn : psycopg2 connection
    query_embedding : np.ndarray | list — 768차원 쿼리 벡터
    user_id : int
    limit : int — 반환할 최대 사진 수

    Returns
    -------
    list[dict] — [{id, file_path, taken_at, city, building, similarity, ...}, ...]
    """
    vec = query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding
    sql = """
        SELECT p.id, p.file_path, p.taken_at,
               p.state, p.city, p.district, p.road, p.building, p.full_address,
               p.event_id,
               1 - (pe.embedding <=> %s::vector) AS similarity
        FROM photos p
        JOIN photo_embeddings pe ON p.id = pe.photo_id
        WHERE p.user_id = %s
        ORDER BY pe.embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (vec, user_id, vec, limit))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def search_photos_filtered(conn, query_embedding, user_id, limit=5,
                           city=None, district=None, date_from=None, date_to=None):
    """메타데이터 필터 + 벡터 유사도 검색 (Hybrid Search).

    Parameters
    ----------
    conn : psycopg2 connection
    query_embedding : np.ndarray | list — 768차원 쿼리 벡터
    user_id : int
    limit : int
    city : str | None — 도시 필터 (LIKE 검색)
    district : str | None — 동/구 필터 (LIKE 검색)
    date_from : datetime | None — 시작 날짜
    date_to : datetime | None — 종료 날짜

    Returns
    -------
    list[dict]
    """
    vec = query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding

    conditions = ["p.user_id = %s"]
    params = [vec, user_id]

    if city:
        conditions.append("p.city LIKE %s")
        params.append(f"%{city}%")
    if district:
        conditions.append("p.district LIKE %s")
        params.append(f"%{district}%")
    if date_from:
        conditions.append("p.taken_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("p.taken_at <= %s")
        params.append(date_to)

    where = " AND ".join(conditions)
    params.extend([vec, limit])

    sql = f"""
        SELECT p.id, p.file_path, p.taken_at,
               p.state, p.city, p.district, p.road, p.building, p.full_address,
               p.event_id,
               1 - (pe.embedding <=> %s::vector) AS similarity
        FROM photos p
        JOIN photo_embeddings pe ON p.id = pe.photo_id
        WHERE {where}
        ORDER BY pe.embedding <=> %s::vector
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
