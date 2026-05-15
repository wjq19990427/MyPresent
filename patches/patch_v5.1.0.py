"""
补丁 v5.1.0 — 从 v5.0.0 升级到 v5.1.0

变更内容：
  - 新增 emotion_scores 表（情绪强度评分缓存）
  - daily_activities 表新增 start_time / end_time 列
  - calendar_todos 表新增 postponed_months 列

使用方法：
  python patches/patch_v5.1.0.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "database.db"


def run() -> None:
    if not DB_PATH.exists():
        print(f"[SKIP] 数据库不存在：{DB_PATH}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        _add_column(conn, "daily_activities", "start_time", "TEXT DEFAULT ''")
        _add_column(conn, "daily_activities", "end_time",   "TEXT DEFAULT ''")
        _add_column(conn, "calendar_todos",   "postponed_months", "INTEGER NOT NULL DEFAULT 0")
        _create_emotion_scores(conn)

    print("[OK] patch_v5.1.0 执行完毕，数据库已是最新 Schema。")


def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"  + {table}.{column}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"  ~ {table}.{column} 已存在，跳过")
        else:
            raise


def _create_emotion_scores(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emotion_scores (
            session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            emotion     TEXT NOT NULL,
            score       REAL NOT NULL CHECK(score >= 0.0 AND score <= 1.0),
            mode        TEXT NOT NULL CHECK(mode IN ('quick', 'precise')),
            model_id    TEXT DEFAULT '',
            computed_at TEXT NOT NULL,
            PRIMARY KEY (session_id, emotion, mode)
        )
    """)
    print("  + emotion_scores 表（已存在则跳过）")


if __name__ == "__main__":
    run()
