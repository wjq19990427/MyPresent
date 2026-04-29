"""pending_db.json I/O 与 session 数据模型。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .constants import DB_FILE, FIELD_SCHEMA, REQUIRED_KEYS, TEXT_EXTS


def load_db() -> list[dict]:
    if not DB_FILE.exists():
        return []
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_db(data: list[dict]) -> None:
    DB_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def validate_session(session: dict) -> list[str]:
    """返回未填写的必填项 label 列表；空列表 = 全部完整。"""
    label_map = {f["key"]: f["label"] for f in FIELD_SCHEMA}
    return [label_map[k] for k in REQUIRED_KEYS
            if not str(session.get(k, "")).strip()]


def _is_text_session(session: dict) -> bool:
    """粘贴文字 或 全部文件均为 txt/md 时返回 True。"""
    if session.get("source_type") == "text":
        return True
    files = session.get("files", [])
    return bool(files) and all(
        Path(fe["filename"]).suffix.lower() in TEXT_EXTS for fe in files
    )


def _apply_fields(session: dict, field_values: dict) -> None:
    for f in FIELD_SCHEMA:
        session[f["key"]] = str(field_values.get(f["key"], "")).strip()
    session["is_complete"] = not validate_session(session)


def _make_session(
    session_id: str,
    file_entries: list[dict],
    source_type: str,
    field_values: dict,
    tags: list[str] | None = None,
) -> dict:
    session = {
        "session_id":   session_id,
        "status":       "pending",
        "files":        file_entries,
        "source_type":  source_type,
        "upload_time":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archive_time": "",
        "edit_history": [],
        "comments":     [],
        "tags":         tags or [],
        "group_ids":    [],
    }
    _apply_fields(session, field_values)
    return session
