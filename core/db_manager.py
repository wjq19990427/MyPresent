"""统一数据库管理层：SQLite 主库。

对外暴露与原 db.py / config.py / llm.py(配置部分) / session_ops.py
相同的函数签名，上层代码无需感知底层存储变更。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from .constants import DB_PATH, FIELD_SCHEMA, REQUIRED_KEYS, DEFAULT_TAGS, TEXT_EXTS

# ─── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    status       TEXT    NOT NULL DEFAULT 'pending',
    source_type  TEXT    NOT NULL DEFAULT 'file',
    content_time TEXT    DEFAULT '',
    description  TEXT    DEFAULT '',
    feeling      TEXT    DEFAULT '',
    reason       TEXT    DEFAULT '',
    is_complete  INTEGER NOT NULL DEFAULT 0,
    upload_time  TEXT    NOT NULL,
    archive_time TEXT    DEFAULT '',
    deleted_at   TEXT,
    pre_delete_status TEXT
);

CREATE TABLE IF NOT EXISTS session_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    original_name TEXT NOT NULL,
    path          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_tags (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tag        TEXT NOT NULL,
    PRIMARY KEY (session_id, tag)
);

CREATE TABLE IF NOT EXISTS tags_registry (
    name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS groups (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_groups (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    group_id   TEXT NOT NULL REFERENCES groups(id)   ON DELETE CASCADE,
    PRIMARY KEY (session_id, group_id)
);

CREATE TABLE IF NOT EXISTS edit_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    edited_at  TEXT NOT NULL,
    changes    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_providers (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    base_url  TEXT NOT NULL,
    api_key   TEXT NOT NULL,
    framework TEXT NOT NULL DEFAULT 'openai'
);

CREATE TABLE IF NOT EXISTS llm_models (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    provider_id  TEXT NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS llm_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id          TEXT,
    skill_name        TEXT,
    session_id        TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    latency_ms        INTEGER,
    success           INTEGER NOT NULL DEFAULT 1,
    error_message     TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL,
    operation    TEXT    NOT NULL,
    operated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(_SCHEMA)
        _cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        if "deleted_at" not in _cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN deleted_at TEXT")
        if "pre_delete_status" not in _cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN pre_delete_status TEXT")
        # 初始化默认标签
        for tag in DEFAULT_TAGS:
            conn.execute(
                "INSERT OR IGNORE INTO tags_registry(name) VALUES (?)", (tag,)
            )


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=ON")
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ─── 内部辅助 ──────────────────────────────────────────────────────────────────

def _load_aux(conn: sqlite3.Connection, session_id: str) -> tuple:
    files = [
        {
            "filename":      r["filename"],
            "original_name": r["original_name"],
            "path":          r["path"],
        }
        for r in conn.execute(
            "SELECT filename, original_name, path FROM session_files "
            "WHERE session_id=? ORDER BY id",
            (session_id,),
        )
    ]
    tags = [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM session_tags WHERE session_id=? ORDER BY tag",
            (session_id,),
        )
    ]
    group_ids = [
        r["group_id"]
        for r in conn.execute(
            "SELECT group_id FROM session_groups WHERE session_id=?",
            (session_id,),
        )
    ]
    history = [
        {
            "edited_at": r["edited_at"],
            "changes":   json.loads(r["changes"]),
        }
        for r in conn.execute(
            "SELECT edited_at, changes FROM edit_history "
            "WHERE session_id=? ORDER BY id",
            (session_id,),
        )
    ]
    comments = [
        {
            "id":         r["id"],
            "text":       r["body"],
            "created_at": r["created_at"],
        }
        for r in conn.execute(
            "SELECT id, body, created_at FROM comments "
            "WHERE session_id=? ORDER BY created_at",
            (session_id,),
        )
    ]
    return files, tags, group_ids, history, comments


def _row_to_dict(row: sqlite3.Row, aux: tuple) -> dict:
    files, tags, group_ids, history, comments = aux
    return {
        "session_id":   row["id"],
        "status":       row["status"],
        "source_type":  row["source_type"],
        "content_time": row["content_time"] or "",
        "description":  row["description"]  or "",
        "feeling":      row["feeling"]       or "",
        "reason":       row["reason"]        or "",
        "is_complete":  bool(row["is_complete"]),
        "upload_time":  row["upload_time"],
        "archive_time": row["archive_time"]  or "",
        "deleted_at":   row["deleted_at"]    or "",
        "pre_delete_status": row["pre_delete_status"] or "",
        "files":        files,
        "tags":         tags,
        "group_ids":    group_ids,
        "edit_history": history,
        "comments":     comments,
    }


# ─── Session CRUD ─────────────────────────────────────────────────────────────

def load_db() -> list[dict]:
    """返回所有 session 的 dict 列表（与原 db.py 接口兼容）。"""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE status != 'deleted' ORDER BY upload_time DESC"
        ).fetchall()
        return [_row_to_dict(r, _load_aux(conn, r["id"])) for r in rows]


def get_session(session_id: str) -> dict | None:
    """按 ID 获取单条 session。"""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return _row_to_dict(row, _load_aux(conn, session_id))


def create_session(
    session_id: str,
    file_entries: list[dict],
    source_type: str,
    field_values: dict,
    tags: list[str] | None = None,
    status: str = "pending",
    archive_time: str = "",
) -> dict:
    """插入新 session，返回 session dict。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
    is_complete = int(not _missing_fields(fields))

    with _conn() as conn:
        conn.execute(
            """INSERT INTO sessions
               (id, status, source_type, content_time, description,
                feeling, reason, is_complete, upload_time, archive_time)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, status, source_type,
                fields.get("content_time", ""),
                fields.get("description", ""),
                fields.get("feeling", ""),
                fields.get("reason", ""),
                is_complete, now, archive_time,
            ),
        )
        for fe in file_entries:
            conn.execute(
                "INSERT INTO session_files(session_id,filename,original_name,path) "
                "VALUES(?,?,?,?)",
                (session_id, fe["filename"], fe["original_name"], fe["path"]),
            )
        for tag in (tags or []):
            conn.execute(
                "INSERT OR IGNORE INTO session_tags(session_id,tag) VALUES(?,?)",
                (session_id, tag),
            )

    return get_session(session_id)


def update_session_fields(session_id: str, new_values: dict) -> None:
    """更新字段；Final 记录额外记录 edit_history 并重写 .md。
    new_values 可含 'tags' 和 'group_ids'，它们不计入 edit_history。
    """
    from .file_io import _write_md
    from .vector_db import embed_session

    session = get_session(session_id)
    if not session:
        return

    new_tags   = new_values.get("tags")
    new_groups = new_values.get("group_ids")

    fields = {f["key"]: str(new_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
    is_complete = int(not _missing_fields(fields))

    with _conn() as conn:
        if session["status"] == "final":
            is_text = _is_text_session(session)
            changes: dict = {}
            for f in FIELD_SCHEMA:
                k = f["key"]
                if is_text and k == "description":
                    continue
                old = str(session.get(k, "")).strip()
                new = fields.get(k, "")
                if old != new:
                    changes[k] = {"from": old, "to": new}
            if changes:
                conn.execute(
                    "INSERT INTO edit_history(session_id,edited_at,changes) VALUES(?,?,?)",
                    (
                        session_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        json.dumps(changes, ensure_ascii=False),
                    ),
                )

        conn.execute(
            """UPDATE sessions SET
               content_time=?, description=?, feeling=?, reason=?, is_complete=?
               WHERE id=?""",
            (
                fields.get("content_time", ""),
                fields.get("description", ""),
                fields.get("feeling", ""),
                fields.get("reason", ""),
                is_complete,
                session_id,
            ),
        )

        if new_tags is not None:
            conn.execute("DELETE FROM session_tags WHERE session_id=?", (session_id,))
            for tag in new_tags:
                conn.execute(
                    "INSERT OR IGNORE INTO session_tags(session_id,tag) VALUES(?,?)",
                    (session_id, tag),
                )

        if new_groups is not None:
            conn.execute("DELETE FROM session_groups WHERE session_id=?", (session_id,))
            for gid in new_groups:
                conn.execute(
                    "INSERT OR IGNORE INTO session_groups(session_id,group_id) VALUES(?,?)",
                    (session_id, gid),
                )

    if session["status"] == "final":
        updated = get_session(session_id)
        if updated:
            _write_md(updated)
            embed_session(updated)


def update_session_tags(session_id: str, tags: list[str]) -> None:
    """单独更新标签（不触发 edit_history）。"""
    from .vector_db import embed_session

    with _conn() as conn:
        conn.execute("DELETE FROM session_tags WHERE session_id=?", (session_id,))
        for tag in tags:
            conn.execute(
                "INSERT OR IGNORE INTO session_tags(session_id,tag) VALUES(?,?)",
                (session_id, tag),
            )

    session = get_session(session_id)
    if session and session["status"] == "final":
        embed_session(session)


def update_session_groups(session_id: str, group_ids: list[str]) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM session_groups WHERE session_id=?", (session_id,))
        for gid in group_ids:
            conn.execute(
                "INSERT OR IGNORE INTO session_groups(session_id,group_id) VALUES(?,?)",
                (session_id, gid),
            )


def update_session_files(session_id: str, file_entries: list[dict]) -> None:
    """替换 session 的文件列表（用于 move_to_final 路径更新）。"""
    with _conn() as conn:
        conn.execute("DELETE FROM session_files WHERE session_id=?", (session_id,))
        for fe in file_entries:
            conn.execute(
                "INSERT INTO session_files(session_id,filename,original_name,path) "
                "VALUES(?,?,?,?)",
                (session_id, fe["filename"], fe["original_name"], fe["path"]),
            )


def set_session_status(
    session_id: str,
    status: str,
    archive_time: str = "",
    is_complete: int = 1,
) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET status=?, archive_time=?, is_complete=? WHERE id=?",
            (status, archive_time, is_complete, session_id),
        )


def add_comment(session_id: str, text: str) -> None:
    from .file_io import _write_md

    if not text.strip():
        return
    session = get_session(session_id)
    if not session:
        return
    now = datetime.now()
    comment_id = now.strftime("%Y%m%d_%H%M%S_%f")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO comments(id,session_id,body,created_at) VALUES(?,?,?,?)",
            (comment_id, session_id, text.strip(), now.strftime("%Y-%m-%d %H:%M:%S")),
        )
    if session["status"] == "final":
        updated = get_session(session_id)
        if updated:
            _write_md(updated)


def delete_comment(session_id: str, comment_id: str) -> None:
    from .file_io import _write_md

    session = get_session(session_id)
    with _conn() as conn:
        conn.execute(
            "DELETE FROM comments WHERE id=? AND session_id=?",
            (comment_id, session_id),
        )
    if session and session["status"] == "final":
        updated = get_session(session_id)
        if updated:
            _write_md(updated)


def validate_session(session: dict) -> list[str]:
    """返回未填写的必填项 label 列表；空列表 = 全部完整。"""
    label_map = {f["key"]: f["label"] for f in FIELD_SCHEMA}
    return [label_map[k] for k in REQUIRED_KEYS if not str(session.get(k, "")).strip()]


def _missing_fields(fields: dict) -> list[str]:
    return [k for k in REQUIRED_KEYS if not str(fields.get(k, "")).strip()]


def _is_text_session(session: dict) -> bool:
    if session.get("source_type") == "text":
        return True
    files = session.get("files", [])
    return bool(files) and all(
        Path(fe["filename"]).suffix.lower() in TEXT_EXTS for fe in files
    )


# ─── Tags Registry ────────────────────────────────────────────────────────────

def get_tags_registry() -> list[str]:
    with _conn() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM tags_registry ORDER BY name")]


def add_tag(tag: str) -> None:
    tag = tag.strip()
    if tag:
        with _conn() as conn:
            conn.execute("INSERT OR IGNORE INTO tags_registry(name) VALUES(?)", (tag,))


def remove_tag(tag: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM tags_registry WHERE name=?", (tag,))


# ─── Groups ───────────────────────────────────────────────────────────────────

def get_groups() -> list[dict]:
    with _conn() as conn:
        return [
            {"id": r["id"], "name": r["name"], "created_at": r["created_at"]}
            for r in conn.execute("SELECT id,name,created_at FROM groups ORDER BY created_at")
        ]


def create_group(name: str) -> str:
    name = name.strip()
    if not name:
        return ""
    group_id = f"grp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO groups(id,name,created_at) VALUES(?,?,?)",
            (group_id, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    return group_id


def delete_group(group_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM groups WHERE id=?", (group_id,))


# ─── LLM Providers ────────────────────────────────────────────────────────────

def get_llm_providers() -> list[dict]:
    with _conn() as conn:
        return [
            {"id": r["id"], "name": r["name"], "base_url": r["base_url"],
             "api_key": r["api_key"], "framework": r["framework"]}
            for r in conn.execute("SELECT * FROM llm_providers ORDER BY name")
        ]


def add_llm_provider(
    name: str, base_url: str, api_key: str, framework: str = "openai"
) -> str:
    name     = name.strip()
    base_url = base_url.strip().rstrip("/")
    api_key  = api_key.strip()
    if not (name and base_url and api_key):
        raise ValueError("name / base_url / api_key 均不能为空")
    provider_id = f"pvd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO llm_providers(id,name,base_url,api_key,framework) VALUES(?,?,?,?,?)",
            (provider_id, name, base_url, api_key, framework),
        )
    return provider_id


def remove_llm_provider(provider_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM llm_providers WHERE id=?", (provider_id,))


def update_llm_provider(provider_id: str, **kwargs) -> None:
    allowed = {"name", "base_url", "api_key", "framework"}
    updates = {k: str(v).strip() for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return
    sets = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE llm_providers SET {sets} WHERE id=?",
            (*updates.values(), provider_id),
        )


# ─── LLM Models ───────────────────────────────────────────────────────────────

def get_llm_models() -> list[dict]:
    with _conn() as conn:
        return [
            {"id": r["id"], "name": r["name"], "display_name": r["display_name"],
             "provider_id": r["provider_id"]}
            for r in conn.execute("SELECT * FROM llm_models ORDER BY name")
        ]


def add_llm_model(
    model_name: str, provider_id: str, display_name: str = ""
) -> str:
    model_name = model_name.strip()
    if not model_name or not provider_id:
        raise ValueError("model_name / provider_id 均不能为空")
    providers = get_llm_providers()
    if not any(p["id"] == provider_id for p in providers):
        raise ValueError(f"Provider {provider_id} 不存在")
    model_id = f"mdl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO llm_models(id,name,display_name,provider_id) VALUES(?,?,?,?)",
            (model_id, model_name, display_name.strip() or model_name, provider_id),
        )
    return model_id


def remove_llm_model(model_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM llm_models WHERE id=?", (model_id,))


def update_llm_model(model_id: str, **kwargs) -> None:
    allowed = {"name", "display_name"}
    updates = {k: str(v).strip() for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return
    sets = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE llm_models SET {sets} WHERE id=?",
            (*updates.values(), model_id),
        )


# ─── LLM Logs ─────────────────────────────────────────────────────────────────

def log_llm_call(
    model_id: str = "",
    skill_name: str = "",
    session_id: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    success: bool = True,
    error_message: str = "",
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO llm_logs
               (model_id,skill_name,session_id,prompt_tokens,completion_tokens,
                latency_ms,success,error_message)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                model_id or None, skill_name or None, session_id or None,
                prompt_tokens, completion_tokens, latency_ms,
                int(success), error_message or None,
            ),
        )


def get_llm_logs(limit: int = 200) -> list[dict]:
    with _conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM llm_logs ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


def log_operation(session_id: str, operation: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO operation_logs(session_id, operation) VALUES (?,?)",
            (session_id, operation),
        )


def get_operation_logs(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM operation_logs ORDER BY operated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def soft_delete_session(session_id: str) -> None:
    """软删除：标记 status='deleted'，保留文件，写入 deleted_at。"""
    session = get_session(session_id)
    if not session:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET status='deleted', pre_delete_status=?, deleted_at=? WHERE id=?",
            (session["status"], now, session_id),
        )
    try:
        from .vector_db import delete_embedding
        delete_embedding(session_id)
    except Exception:
        pass
    log_operation(session_id, "delete")


def restore_session(session_id: str) -> None:
    """从回收站恢复到删除前的 status；final 记录重新入向量库。"""
    with _conn() as conn:
        row = conn.execute(
            "SELECT pre_delete_status FROM sessions WHERE id=? AND status='deleted'",
            (session_id,),
        ).fetchone()
        if not row:
            return
        prev = row["pre_delete_status"] or "pending"
        conn.execute(
            "UPDATE sessions SET status=?, deleted_at=NULL, pre_delete_status=NULL WHERE id=?",
            (prev, session_id),
        )
    if prev == "final":
        session = get_session(session_id)
        if session:
            from .vector_db import embed_session
            try:
                embed_session(session)
            except Exception:
                pass
    log_operation(session_id, "restore")


def get_deleted_sessions() -> list[dict]:
    """返回所有软删除记录（含 deleted_at）。"""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE status='deleted' ORDER BY deleted_at DESC"
        ).fetchall()
        return [_row_to_dict(r, _load_aux(conn, r["id"])) for r in rows]


def purge_expired_deleted(days: int = 30) -> int:
    """永久删除超过 days 天的软删除记录（含磁盘文件）。返回删除数量。"""
    with _conn() as conn:
        rows = conn.execute(
            f"""SELECT id FROM sessions
                WHERE status='deleted'
                AND deleted_at <= datetime('now', 'localtime', '-{days} days')"""
        ).fetchall()
        ids = [r["id"] for r in rows]
    for sid in ids:
        session = get_session(sid)
        if session:
            for f in session.get("files", []):
                path = Path(f.get("path", ""))
                if path.exists():
                    path.unlink(missing_ok=True)
        log_operation(sid, "purge")
        with _conn() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    return len(ids)
