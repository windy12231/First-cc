import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path.home() / ".app_tracker" / "usage.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            window_title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER DEFAULT 0,
            date TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_log(date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_app ON usage_log(app_name)
    """)
    conn.commit()
    conn.close()


def log_session(app_name: str, window_title: str, start_time: datetime.datetime,
                end_time: datetime.datetime):
    duration = int((end_time - start_time).total_seconds())
    if duration < 1:
        return
    date_str = start_time.strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        "INSERT INTO usage_log (app_name, window_title, start_time, end_time, duration_seconds, date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (app_name, window_title, start_time.isoformat(), end_time.isoformat(), duration, date_str),
    )
    conn.commit()
    conn.close()


def get_today_summary() -> list[tuple[str, int]]:
    """Return list of (app_name, total_seconds) for today, sorted descending."""
    today = datetime.date.today().isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT app_name, SUM(duration_seconds) as total "
        "FROM usage_log WHERE date = ? GROUP BY app_name ORDER BY total DESC",
        (today,),
    ).fetchall()
    conn.close()
    return rows


def get_date_range_summary(start_date: str, end_date: str) -> list[tuple[str, int]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT app_name, SUM(duration_seconds) as total "
        "FROM usage_log WHERE date >= ? AND date <= ? "
        "GROUP BY app_name ORDER BY total DESC",
        (start_date, end_date),
    ).fetchall()
    conn.close()
    return rows


def get_daily_totals(days: int = 7) -> list[tuple[str, int]]:
    """Return (date, total_seconds) for the last N days."""
    conn = get_connection()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT date, SUM(duration_seconds) as total "
        "FROM usage_log WHERE date >= ? "
        "GROUP BY date ORDER BY date ASC",
        (cutoff,),
    ).fetchall()
    conn.close()
    return rows


def get_all_time_summary() -> list[tuple[str, int]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT app_name, SUM(duration_seconds) as total "
        "FROM usage_log GROUP BY app_name ORDER BY total DESC"
    ).fetchall()
    conn.close()
    return rows


def get_today_total() -> int:
    today = datetime.date.today().isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM usage_log WHERE date = ?",
        (today,),
    ).fetchone()
    conn.close()
    return row[0]


def get_current_app_today(app_name: str) -> int:
    today = datetime.date.today().isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM usage_log "
        "WHERE date = ? AND app_name = ?",
        (today, app_name),
    ).fetchone()
    conn.close()
    return row[0]


def get_week_total() -> int:
    cutoff = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    today = datetime.date.today().isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM usage_log "
        "WHERE date >= ? AND date <= ?",
        (cutoff, today),
    ).fetchone()
    conn.close()
    return row[0]
