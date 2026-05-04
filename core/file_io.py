"""文件写入/移动、session 持久化、Markdown 导出。"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .constants import (
    FINAL_DIR, PENDING_DIR, FIELD_SCHEMA,
    IMAGE_EXTS, VIDEO_EXTS, VECTOR_DB_DIR,
)
from .db_manager import (
    create_session, set_session_status, update_session_files, get_session,
)


def _file_subdir(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTS:
        return "images"
    if ext in VIDEO_EXTS:
        return "videos"
    return "text"


def _session_file_type(session: dict) -> str:
    files = session.get("files", [])
    if not files:
        return "text"
    return _file_subdir(files[0]["filename"])


def ensure_dirs() -> None:
    for base in (FINAL_DIR, PENDING_DIR):
        for sub in ("images", "videos", "text"):
            (base / sub).mkdir(parents=True, exist_ok=True)
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)


def _write_files(
    file_data_list: list[tuple], dest_dir: Path, session_id: str
) -> list[dict]:
    entries = []
    for idx, (data, orig_name) in enumerate(file_data_list):
        filename = f"{session_id}_{idx:03d}_{orig_name}"
        sub      = _file_subdir(filename)
        dest     = dest_dir / sub / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(data, "read"):
            with dest.open("wb") as f:
                shutil.copyfileobj(data, f)
        else:
            dest.write_bytes(data)
        entries.append({
            "filename":      filename,
            "original_name": orig_name,
            "path":          str(dest),
        })
    return entries


def _write_md(session: dict) -> None:
    """生成/更新 Final 目录中该 session 的 .md 文件。"""
    files = session.get("files", [])
    title = files[0]["original_name"] if files else "记录"
    if len(files) > 1:
        title += f" 等 {len(files)} 个文件"

    lines = [f"# {title}\n\n"]
    lines.append(f"**上传时间**：{session.get('upload_time', '')}\n")
    if session.get("archive_time"):
        lines.append(f"**归档时间**：{session['archive_time']}\n")
    lines.append("\n")

    for field in FIELD_SCHEMA:
        v = str(session.get(field["key"], "")).strip()
        if v:
            lines.append(f"## {field['label']}\n\n{v}\n\n")

    comments = [c for c in session.get("comments", []) if isinstance(c, dict)]
    if comments:
        lines.append("---\n\n## 评论区\n\n")
        for c in comments:
            lines.append(
                f"**{c.get('created_at', '')}**\n\n{c.get('text', '')}\n\n"
            )

    history = session.get("edit_history", [])
    if history:
        lines.append("---\n\n## 编辑历史\n\n")
        for edit in history:
            lines.append(f"### {edit['edited_at']}\n\n")
            for fk, change in edit["changes"].items():
                lbl = next(
                    (f["label"] for f in FIELD_SCHEMA if f["key"] == fk), fk
                )
                lines.append(
                    f"- **{lbl}**：「{change['from']}」→「{change['to']}」\n"
                )
            lines.append("\n")

    (FINAL_DIR / f"{session['session_id']}.md").write_text(
        "".join(lines), encoding="utf-8"
    )


def save_session_pending(
    file_data_list: list[tuple],
    source_type: str,
    field_values: dict,
    tags: list[str] | None = None,
) -> None:
    sid          = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_entries = _write_files(file_data_list, PENDING_DIR, sid)
    create_session(sid, file_entries, source_type, field_values, tags=tags)


def save_session_final(
    file_data_list: list[tuple],
    source_type: str,
    field_values: dict,
    tags: list[str] | None = None,
) -> None:
    from .vector_db import embed_session
    sid          = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_entries = _write_files(file_data_list, FINAL_DIR, sid)
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session      = create_session(
        sid, file_entries, source_type, field_values,
        tags=tags, status="final", archive_time=now,
    )
    _write_md(session)
    embed_session(session)


def move_to_final(session_id: str) -> None:
    from .vector_db import embed_session
    session = get_session(session_id)
    if not session:
        return
    updated_files = []
    for fe in session["files"]:
        src  = Path(fe["path"])
        sub  = _file_subdir(fe["filename"])
        dest = FINAL_DIR / sub / fe["filename"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.move(str(src), str(dest))
        updated_files.append({
            "filename":      fe["filename"],
            "original_name": fe["original_name"],
            "path":          str(dest),
        })
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_session_files(session_id, updated_files)
    set_session_status(session_id, "final", archive_time=now, is_complete=1)
    updated_session = get_session(session_id)
    if updated_session:
        _write_md(updated_session)
        embed_session(updated_session)


def import_folder_to_pending(
    file_paths: list[Path],
    as_one_session: bool,
    tags: list[str] | None = None,
) -> int:
    if not file_paths:
        return 0
    if as_one_session:
        handles, file_data = [], []
        try:
            for fp in file_paths:
                fh = open(fp, "rb")
                handles.append(fh)
                file_data.append((fh, fp.name))
            save_session_pending(file_data, "file", {}, tags=tags)
        finally:
            for fh in handles:
                fh.close()
        return 1
    else:
        count = 0
        for fp in file_paths:
            with open(fp, "rb") as fh:
                save_session_pending([(fh, fp.name)], "file", {}, tags=tags)
            count += 1
        return count
