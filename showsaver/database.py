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
                     url            TEXT NOT NULL,
                     show_name      TEXT NOT NULL,
                     title          TEXT NOT NULL,
                     thumbnail      TEXT NOT NULL,
                     duration       INTEGER NOT NULL,
                     fetched_at     REAL NOT NULL   -- unix timestamp
            )
        """)


def upsert_dropout_episode_basic(url_path: str, url: str, episode_title: str, thumbnail: str, duration_secs: int) -> None:
    """Upsert scrape-time fields without touching show_name (preserves any yt-dlp-resolved value)."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO dropout_episodes (url_path, url, show_name, title, thumbnail, duration, fetched_at)
            VALUES (?, ?, '', ?, ?, ?, ?)
            ON CONFLICT(url_path) DO UPDATE SET
                url = excluded.url,
                title = excluded.title,
                thumbnail = excluded.thumbnail,
                duration = excluded.duration,
                fetched_at = excluded.fetched_at
        """, (url_path, url, episode_title, thumbnail, duration_secs, time.time()))


def upsert_dropout_episode(url_path: str, url: str, show_name: str, episode_title: str, thumbnail: str, duration_secs: int) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO dropout_episodes (url_path, url, show_name, title, thumbnail, duration, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_path) DO UPDATE SET
                url = excluded.url,
                show_name = excluded.show_name,
                title = excluded.title,
                thumbnail = excluded.thumbnail,
                duration = excluded.duration,
                fetched_at = excluded.fetched_at
        """, (url_path, url, show_name, episode_title, thumbnail, duration_secs, time.time()))


def get_dropout_episode(url_path: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dropout_episodes WHERE url_path = ?", (url_path,)
        ).fetchone()
    return dict(row) if row else None


def get_all_dropout_episodes() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM dropout_episodes").fetchall()
    return [dict(r) for r in rows]
