"""photos 테이블 CRUD 함수"""

from pipeline.geocoder import PlaceInfo


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
