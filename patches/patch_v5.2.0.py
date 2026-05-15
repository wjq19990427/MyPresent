"""
补丁 v5.2.0 — calendar_todos 树形结构字段

变更内容：
  - calendar_todos 新增 parent_id，用于表达待办父子关系
  - calendar_todos 新增 todo_state，用于表达 todo / done / moved 三态

使用方法：
  python patches/patch_v5.2.0.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "database.db"


def run() -> None:
    if not DB_PATH.exists():
        print(f"[SKIP] 数据库不存在：{DB_PATH}")
        return

    with sqlite3.connect(DB_PATH) as conn:
        _add_column(
            conn,
            "calendar_todos",
            "parent_id",
            "TEXT REFERENCES calendar_todos(id) ON DELETE CASCADE",
        )
        _add_column(
            conn,
            "calendar_todos",
            "todo_state",
            "TEXT NOT NULL DEFAULT 'todo'",
        )
        conn.execute(
            "UPDATE calendar_todos SET todo_state='done' "
            "WHERE status='已完成' AND todo_state='todo'"
        )

    print("[OK] patch_v5.2.0 执行完毕，待办树形字段已就绪。")


def _add_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"  + {table}.{column}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"  ~ {table}.{column} 已存在，跳过")
        else:
            raise


if __name__ == "__main__":
    run()
