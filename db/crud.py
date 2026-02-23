"""photos 테이블 CRUD 함수 + embedding 관련 함수 + 키워드 관련 함수 + 유저/일기 관련 함수"""

from __future__ import annotations

from pipeline.utils.geocoder import PlaceInfo
import numpy as np


# ── User 관련 ──

def create_user(conn, email: str, username: str, hashed_password: str) -> int:
    """users 테이블에 새 사용자 INSERT → user id 반환."""
    sql = """
        INSERT INTO users (email, username, hashed_password)
        VALUES (%s, %s, %s)
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (email, username, hashed_password))
        user_id = cur.fetchone()[0]
    conn.commit()
    return user_id


def get_user_by_email(conn, email: str) -> dict | None:
    """이메일로 사용자 조회 → dict (없으면 None)."""
    sql = "SELECT id, email, username, hashed_password, created_at FROM users WHERE email = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (email,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def get_user_by_id(conn, user_id: int) -> dict | None:
    """user_id로 사용자 조회 → dict (없으면 None)."""
    sql = "SELECT id, email, username, created_at FROM users WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def update_caption(conn, photo_id: int, caption: str, commit=True):
    """사진의 캡션 업데이트."""
    sql = "UPDATE photos SET caption = %s WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (caption, photo_id))
    if commit:
        conn.commit()


def list_events_by_date_range(conn, user_id: int, date_from=None, date_to=None) -> list[dict]:
    """날짜 범위 내 이벤트 목록 조회 (RAG Engine DIARY용)."""
    conditions = ["user_id = %s"]
    params: list = [user_id]
    if date_from:
        conditions.append("started_at >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("started_at <= %s")
        params.append(date_to)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, user_id, started_at, ended_at, primary_location, photo_count
        FROM events
        WHERE {where}
        ORDER BY started_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_photos_by_event(conn, event_id: int) -> list[dict]:
    """이벤트에 속한 사진 목록 조회."""
    sql = """
        SELECT id, user_id, file_path, taken_at,
               latitude, longitude,
               state, city, district, road, building, full_address,
               caption, event_id, created_at
        FROM photos
        WHERE event_id = %s
        ORDER BY taken_at ASC, id ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (event_id,))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def insert_photo(conn, user_id, file_path, lat, lon, place_info=None, taken_at=None,
                 commit=True):
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
    commit : bool — False면 커밋을 호출자에게 위임한다.

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
    if commit:
        conn.commit()
    return photo_id


def get_photo(conn, photo_id):
    """photo_id로 한 장 조회 → dict (없으면 None)"""
    sql = """
        SELECT id, user_id, file_path, taken_at,
               latitude, longitude,
               state, city, district, road, building, full_address,
               caption, event_id, created_at
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
               caption, event_id, created_at
        FROM photos
        WHERE user_id = %s
        ORDER BY taken_at DESC, id DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, limit))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_all_user_ids(conn) -> list[int]:
    """DB에 등록된 모든 user_id 목록을 반환한다 (파이프라인 CLI 전체 유저 순회용)."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT id FROM users ORDER BY id")
        return [row[0] for row in cur.fetchall()]


def get_photo_keywords(conn, photo_id: int) -> list[str]:
    """photo_keywords + keywords 테이블에서 해당 사진의 키워드 목록 조회.

    Returns
    -------
    list[str] — 키워드 이름 목록 (중요도 높은 순)
    """
    sql = """
        SELECT k.name
        FROM photo_keywords pk
        JOIN keywords k ON pk.keyword_id = k.id
        WHERE pk.photo_id = %s
        ORDER BY pk.importance DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id,))
        return [row[0] for row in cur.fetchall()]


def list_unclustered_photos(conn, user_id, limit=1000):
    """event_id가 없는 사진 목록을 시간순으로 조회한다."""
    sql = """
        SELECT id AS photo_id, user_id, file_path, taken_at,
               latitude, longitude,
               state, city, district, road, building, full_address,
               event_id, created_at
        FROM photos
        WHERE user_id = %s
          AND event_id IS NULL
        ORDER BY taken_at ASC, id ASC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, limit))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_last_event(conn, user_id):
    """사용자의 가장 최근 이벤트 1건을 조회한다 (GPS 유효 사진 수 포함)."""
    sql = """
        SELECT e.id, e.user_id, e.started_at, e.ended_at,
               e.primary_location, e.photo_count,
               (SELECT COUNT(*) FROM photos p
                WHERE p.event_id = e.id
                  AND p.latitude IS NOT NULL
                  AND p.longitude IS NOT NULL) AS gps_photo_count
        FROM events e
        WHERE e.user_id = %s
        ORDER BY COALESCE(e.ended_at, e.started_at) DESC, e.id DESC
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def insert_events(conn, events, commit=True):
    """
    events 테이블에 신규 이벤트를 INSERT하고 event_ref -> event_id 매핑을 반환한다.

    Parameters
    ----------
    events : list[dict]
        cluster_events 결과 중 existing_event_id가 None인 이벤트 목록
    commit : bool — False면 커밋을 호출자에게 위임한다.
    """
    if not events:
        return {}

    sql = """
        INSERT INTO events
            (user_id, started_at, ended_at, primary_location, photo_count)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """

    event_id_map = {}
    with conn.cursor() as cur:
        for event in events:
            cur.execute(
                sql,
                (
                    event["user_id"],
                    event["started_at"],
                    event["ended_at"],
                    event["primary_location"],
                    event["photo_count"],
                ),
            )
            inserted_event_id = cur.fetchone()[0]
            event_id_map[event["event_ref"]] = inserted_event_id
    if commit:
        conn.commit()
    return event_id_map


def update_existing_event(conn, event_id, ended_at, primary_location, photo_count,
                          commit=True):
    """
    기존 이벤트의 메타데이터를 갱신한다 (증분 클러스터링 병합 시 사용).

    Parameters
    ----------
    conn : psycopg2 connection
    event_id : int
    ended_at : datetime — 갱신된 종료 시각
    primary_location : str | None — 갱신된 대표 좌표 ("lat,lon")
    photo_count : int — 갱신된 총 사진 수
    commit : bool — False면 커밋을 호출자에게 위임한다.
    """
    sql = """
        UPDATE events
        SET ended_at = %s, primary_location = %s, photo_count = %s
        WHERE id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (ended_at, primary_location, photo_count, event_id))
    if commit:
        conn.commit()


def update_event_id(conn, photo_id, event_id, commit=True):
    """사진의 event_id 업데이트"""
    sql = "UPDATE photos SET event_id = %s WHERE id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (event_id, photo_id))
    if commit:
        conn.commit()


def update_photo_event_ids(conn, photo_event_updates, commit=True):
    """
    photos.event_id 일괄 업데이트.

    Parameters
    ----------
    photo_event_updates : list[tuple[int, int | str]]
        [(event_id, photo_id), ...]
    commit : bool — False면 커밋을 호출자에게 위임한다.
    """
    if not photo_event_updates:
        return 0

    sql = "UPDATE photos SET event_id = %s WHERE id = %s"
    with conn.cursor() as cur:
        cur.executemany(sql, photo_event_updates)
    if commit:
        conn.commit()
    return len(photo_event_updates)


def update_importance(conn, photo_id, keyword_id, importance, commit=True):
    """photo_keywords 테이블의 importance 점수 업데이트"""
    sql = """
        UPDATE photo_keywords
        SET importance = %s
        WHERE photo_id = %s AND keyword_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (importance, photo_id, keyword_id))
    if commit:
        conn.commit()


# ── 키워드 관련 ──

def insert_keyword(conn, name: str, category: str) -> int:
    """keywords 테이블에 키워드 INSERT (이미 존재하면 id 반환)."""
    sql = """
        INSERT INTO keywords (name, category)
        VALUES (%s, %s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (name, category))
        keyword_id = cur.fetchone()[0]
    conn.commit()
    return keyword_id


def link_photo_keyword(conn, photo_id: int, keyword_id: int, importance: float = 1.0):
    """photo_keywords 테이블에 사진-키워드 연결 (이미 존재하면 importance 업데이트)."""
    sql = """
        INSERT INTO photo_keywords (photo_id, keyword_id, importance)
        VALUES (%s, %s, %s)
        ON CONFLICT (photo_id, keyword_id)
        DO UPDATE SET importance = EXCLUDED.importance
    """
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id, keyword_id, importance))
    conn.commit()


def bulk_insert_photo_keywords(
    conn, photo_id: int, keyword_data: list[tuple[str, str, float]],
) -> int:
    """한 사진의 키워드를 한번에 INSERT (트랜잭션 1회).
    
    주의: 동시 다발적인 multi-file 업로드 시 여러 프로세스가 서로 다른 순서로
    동일한 키워드를 INSERT 하려 할 때 발생하는 데드락(Deadlock)을 방기하기 위해,
    반드시 키워드 이름(name)을 기준으로 정렬하여 락 획득 순서를 일치시켜야 합니다.
    """
    if not keyword_data:
        return 0
        
    keyword_data = sorted(keyword_data, key=lambda x: x[0])
    saved = 0
    with conn.cursor() as cur:
        for name, category, importance in keyword_data:
            cur.execute(
                """INSERT INTO keywords (name, category) VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
                (name, category),
            )
            keyword_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO photo_keywords (photo_id, keyword_id, importance)
                VALUES (%s, %s, %s)
                ON CONFLICT (photo_id, keyword_id) DO UPDATE SET importance = EXCLUDED.importance""",
                (photo_id, keyword_id, importance),
            )
            saved += 1
    conn.commit()
    return saved


def delete_photo_keywords(conn, photo_id: int) -> int:
    """사진의 기존 키워드 연결 전부 삭제 (재추출 시 사용)."""
    sql = "DELETE FROM photo_keywords WHERE photo_id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id,))
        deleted = cur.rowcount
    conn.commit()
    return deleted


def get_photo_keyword_count(conn, photo_id: int) -> int:
    """사진에 연결된 키워드 수 조회."""
    sql = "SELECT COUNT(*) FROM photo_keywords WHERE photo_id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id,))
        return cur.fetchone()[0]


def get_photo_keywords_batch(conn, photo_ids: list[int]) -> dict[int, list[str]]:
    """photo_id 목록에 대해 {photo_id: [keyword_name, ...]} 를 배치 조회."""
    if not photo_ids:
        return {}
    placeholders = ",".join(["%s"] * len(photo_ids))
    sql = f"""
        SELECT pk.photo_id, k.name
        FROM photo_keywords pk
        JOIN keywords k ON pk.keyword_id = k.id
        WHERE pk.photo_id IN ({placeholders})
        ORDER BY pk.photo_id, pk.importance DESC
    """
    result: dict[int, list[str]] = {pid: [] for pid in photo_ids}
    with conn.cursor() as cur:
        cur.execute(sql, photo_ids)
        for photo_id, keyword_name in cur.fetchall():
            result[photo_id].append(keyword_name)
    return result


# ── Embedding 관련 ──

def insert_embedding(conn, photo_id, embedding, commit=True):
    """photo_embeddings 테이블에 벡터 INSERT (이미 존재하면 업데이트).

    Parameters
    ----------
    conn : psycopg2 connection
    photo_id : int
    embedding : np.ndarray | list — 768차원 벡터
    commit : bool — False면 커밋을 호출자에게 위임한다.
    """
    vec = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
    sql = """
        INSERT INTO photo_embeddings (photo_id, embedding)
        VALUES (%s, %s)
        ON CONFLICT (photo_id) DO UPDATE SET embedding = EXCLUDED.embedding
    """
    with conn.cursor() as cur:
        cur.execute(sql, (photo_id, vec))
    if commit:
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
                           state=None, city=None, district=None,
                           date_from=None, date_to=None):
    """메타데이터 필터 + 벡터 유사도 검색 (Hybrid Search).

    Parameters
    ----------
    conn : psycopg2 connection
    query_embedding : np.ndarray | list — 768차원 쿼리 벡터
    user_id : int
    limit : int
    state : str | None — 광역시/도 필터 (LIKE 검색)
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

    if state:
        conditions.append("p.state LIKE %s")
        params.append(f"%{state}%")
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


def insert_diary(conn, user_id: int, diary_date, content: str) -> int:
    """diaries 테이블에 일기 INSERT (같은 날짜면 내용 업데이트) → diary id 반환."""
    sql = """
        INSERT INTO diaries (user_id, diary_date, content)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, diary_date) DO UPDATE SET content = EXCLUDED.content
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, diary_date, content))
        diary_id = cur.fetchone()[0]
    conn.commit()
    return diary_id


def get_diary(conn, user_id: int, diary_date) -> dict | None:
    """특정 날짜의 일기 1건 조회 → dict (없으면 None)."""
    sql = """
        SELECT id, user_id, diary_date, content, created_at
        FROM diaries
        WHERE user_id = %s AND diary_date = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, diary_date))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def get_diaries_by_range(conn, user_id: int, date_from, date_to) -> list[dict]:
    """날짜 범위의 일기 목록 조회 (오래된 순)."""
    sql = """
        SELECT id, user_id, diary_date, content, created_at
        FROM diaries
        WHERE user_id = %s AND diary_date >= %s AND diary_date <= %s
        ORDER BY diary_date ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, date_from, date_to))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
