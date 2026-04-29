"""字段更新、评论、auto_tag、文件夹导入（高层 session 操作）。"""
from __future__ import annotations

import os
from datetime import datetime

from .constants import FIELD_SCHEMA
from .db import load_db, save_db, validate_session, _is_text_session, _apply_fields
from .file_io import _write_md
from .vector_db import embed_session


def update_session_fields(session_id: str, new_values: dict) -> None:
    """更新字段；Final 记录额外追加 edit_history 并重写 .md。
    new_values 可包含 'tags' 和 'group_ids'，这两项不计入 edit_history。
    """
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return

    new_tags   = new_values.get("tags")
    new_groups = new_values.get("group_ids")

    if session.get("status") == "final":
        is_text = _is_text_session(session)
        changes = {}
        for f in FIELD_SCHEMA:
            k = f["key"]
            if is_text and k == "description":
                continue
            old = str(session.get(k, "")).strip()
            new = str(new_values.get(k, "")).strip()
            if old != new:
                changes[k] = {"from": old, "to": new}
        if changes:
            session.setdefault("edit_history", []).append({
                "edited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "changes":   changes,
            })

    _apply_fields(session, new_values)

    if new_tags is not None:
        session["tags"] = new_tags
    if new_groups is not None:
        session["group_ids"] = new_groups

    save_db(db)

    if session.get("status") == "final":
        _write_md(session)
        embed_session(session)


def update_session_tags(session_id: str, tags: list[str]) -> None:
    """单独更新标签（不触发 edit_history 或 .md 重写）。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return
    session["tags"] = tags
    save_db(db)
    if session.get("status") == "final":
        embed_session(session)


def update_session_groups(session_id: str, group_ids: list[str]) -> None:
    """单独更新所属分组。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return
    session["group_ids"] = group_ids
    save_db(db)


def add_comment(session_id: str, text: str) -> None:
    """追加一条评论（含自动时间戳）。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session or not text.strip():
        return
    now = datetime.now()
    session.setdefault("comments", []).append({
        "id":         now.strftime("%Y%m%d_%H%M%S_%f"),
        "text":       text.strip(),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_db(db)
    if session.get("status") == "final":
        _write_md(session)


def delete_comment(session_id: str, comment_id: str) -> None:
    """删除指定 id 的评论。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return
    session["comments"] = [
        c for c in session.get("comments", [])
        if isinstance(c, dict) and c.get("id") != comment_id
    ]
    save_db(db)
    if session.get("status") == "final":
        _write_md(session)


def auto_tag_session(session: dict) -> list[str]:
    """预留接口：调用外部 API 为 session 推荐标签，返回标签名列表。
    当前为 stub；配置 MYPRESENT_API_KEY 环境变量后 Phase 3 实现。
    """
    if not os.environ.get("MYPRESENT_API_KEY"):
        return []
    # TODO Phase 3：调用 Claude/OpenAI API，基于 description/feeling 推荐标签
    return []
