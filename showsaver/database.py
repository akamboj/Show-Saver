import sqlite3
import time
from env import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # Rows behave like dicts
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dropout_episodes (
                     url_path       TEXT PRIMARY KEY,
                     full_url       TEXT NOT NULL,
                     show_name      TEXT NOT NULL,
                     episode_title  TEXT NOT NULL,
                     fetched_at     REAL NOT NULL   -- unix timestamp
            )
        """)


def upsert_dropout_episode(url_path: str, full_url: str, show_name: str, episode_title: str) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO dropout_episodes (url_path, full_url, show_name, episode_title, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url_path) DO UPDATE SET
                full_url = excluded.full_url
                show_name = excluded.show_name,
                episode_title = excluded.episode_title,
                fetched_at = excluded.fetched_at
        """, (url_path, full_url, show_name, episode_title, time.time()))


def get_dropout_episode(url_path: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dropout_episodes WHERE url_path = ?", (url_path,)
        ).fetchone()
    return dict(row) if row else None


def get_all_dropout_episodes() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SLECT * FROM dropout_episodes").fetchall()
    return [dict(r) for r in rows]
