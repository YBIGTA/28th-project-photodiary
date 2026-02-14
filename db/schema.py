"""
PhotoDiary DB 스키마 DDL — PostgreSQL + pgvector
실행: python db/schema.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "photodiary"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


DDL = """
-- pgvector 확장
CREATE EXTENSION IF NOT EXISTS vector;

-- ENUM 타입
DO $$ BEGIN
    CREATE TYPE keyword_category AS ENUM ('person', 'activity', 'place', 'object');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 1. events (photos 보다 먼저 생성 — FK 참조 대상)
CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ,
    primary_location TEXT,
    photo_count INTEGER NOT NULL DEFAULT 0
);

-- 2. photos
CREATE TABLE IF NOT EXISTS photos (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    file_path    TEXT    NOT NULL,
    taken_at     TIMESTAMPTZ,
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION,
    state        TEXT,
    city         TEXT,
    district     TEXT,
    road         TEXT,
    building     TEXT,
    full_address TEXT,
    caption      TEXT,
    event_id     INTEGER REFERENCES events(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- caption 컬럼 마이그레이션 (이미 테이블이 존재하는 경우)
DO $$ BEGIN
    ALTER TABLE photos ADD COLUMN IF NOT EXISTS caption TEXT;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- 3. keywords
CREATE TABLE IF NOT EXISTS keywords (
    id       SERIAL PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    category keyword_category NOT NULL
);

-- 4. photo_keywords
CREATE TABLE IF NOT EXISTS photo_keywords (
    id         SERIAL PRIMARY KEY,
    photo_id   INTEGER NOT NULL REFERENCES photos(id)   ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    importance REAL NOT NULL DEFAULT 1.0,
    UNIQUE (photo_id, keyword_id)
);

-- 5. diaries
CREATE TABLE IF NOT EXISTS diaries (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    diary_date DATE    NOT NULL,
    content    TEXT    NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, diary_date)
);

-- 6. photo_embeddings (pgvector 768차원)
CREATE TABLE IF NOT EXISTS photo_embeddings (
    id        SERIAL PRIMARY KEY,
    photo_id  INTEGER NOT NULL UNIQUE REFERENCES photos(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL
);

-- ============ 인덱스 ============

-- photos
CREATE INDEX IF NOT EXISTS idx_photos_user_taken
    ON photos (user_id, taken_at);
CREATE INDEX IF NOT EXISTS idx_photos_user_district
    ON photos (user_id, district);
CREATE INDEX IF NOT EXISTS idx_photos_event
    ON photos (event_id);

-- keywords
CREATE INDEX IF NOT EXISTS idx_keywords_category
    ON keywords (category);

-- photo_keywords
CREATE INDEX IF NOT EXISTS idx_photo_keywords_photo
    ON photo_keywords (photo_id);
CREATE INDEX IF NOT EXISTS idx_photo_keywords_keyword_imp
    ON photo_keywords (keyword_id, importance DESC);

-- events
CREATE INDEX IF NOT EXISTS idx_events_user_started
    ON events (user_id, started_at);

-- photo_embeddings: HNSW 벡터 인덱스 (cosine 유사도)
CREATE INDEX IF NOT EXISTS idx_photo_embeddings_hnsw
    ON photo_embeddings
    USING hnsw (embedding vector_cosine_ops);
"""


def run():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
        print("스키마 생성 완료 ✓")

        # 생성된 테이블 목록 출력
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
            tables = [row[0] for row in cur.fetchall()]
        print(f"테이블 목록: {', '.join(tables)}")
    except Exception as e:
        conn.rollback()
        print(f"오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
