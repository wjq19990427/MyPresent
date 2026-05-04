"""一次性数据迁移脚本：JSON → SQLite + Assets/ → data/

运行方式：python migrate.py
迁移完成后原 JSON 文件备份为 *.bak，Assets/ 目录保留原样。
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ─── 旧路径（迁移前） ──────────────────────────────────────────────────────────
OLD_DB_FILE    = Path("pending_db.json")
OLD_CONFIG     = Path("mypresent_config.json")
OLD_ASSETS_DIR = Path("Assets")

# ─── 新路径（迁移后） ──────────────────────────────────────────────────────────
NEW_DATA_DIR   = Path("data")
NEW_PENDING    = NEW_DATA_DIR / "pending"
NEW_FINAL      = NEW_DATA_DIR / "final"


def _load_json(path: Path) -> object:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [警告] 读取 {path} 失败：{e}")
        return None


def _copy_assets() -> dict[str, str]:
    """将 Assets/Pending/ 和 Assets/Final/ 中的文件复制到 data/pending|final/，
    返回 旧路径→新路径 的映射（用于更新 session_files.path）。"""
    path_map: dict[str, str] = {}
    for old_sub, new_sub in [
        (OLD_ASSETS_DIR / "Pending", NEW_PENDING),
        (OLD_ASSETS_DIR / "Final",   NEW_FINAL),
    ]:
        if not old_sub.exists():
            continue
        for old_file in old_sub.rglob("*"):
            if not old_file.is_file():
                continue
            rel = old_file.relative_to(old_sub)
            new_file = new_sub / rel
            new_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_file, new_file)
            path_map[str(old_file)] = str(new_file)
            # 同时处理正斜杠和反斜杠变体
            path_map[str(old_file).replace("\\", "/")] = str(new_file)
            path_map[str(old_file).replace("/", "\\")] = str(new_file)
    return path_map


def _remap_path(old_path: str, path_map: dict[str, str]) -> str:
    """用映射表转换文件路径，找不到则返回原值。"""
    return path_map.get(old_path, path_map.get(
        old_path.replace("\\", "/"),
        path_map.get(old_path.replace("/", "\\"), old_path),
    ))


def migrate() -> None:
    # 初始化新数据库
    from core.db_manager import init_db, _conn, DEFAULT_TAGS

    print("▶ 初始化 SQLite 数据库…")
    init_db()

    # ── 迁移配置（标签注册表 / 分组 / LLM 配置） ──────────────────────────────
    config_data = _load_json(OLD_CONFIG) or {}

    tags_registry: list[str] = config_data.get("tags_registry", DEFAULT_TAGS[:])
    groups:        list[dict] = config_data.get("groups", [])
    providers:     list[dict] = config_data.get("llm_providers", [])
    models:        list[dict] = config_data.get("llm_models", [])

    with _conn() as conn:
        print(f"  标签注册表：{len(tags_registry)} 条")
        for tag in tags_registry:
            conn.execute("INSERT OR IGNORE INTO tags_registry(name) VALUES(?)", (tag,))

        print(f"  分组：{len(groups)} 条")
        for g in groups:
            conn.execute(
                "INSERT OR IGNORE INTO groups(id,name,created_at) VALUES(?,?,?)",
                (g["id"], g["name"], g.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            )

        print(f"  LLM Provider：{len(providers)} 条")
        for p in providers:
            conn.execute(
                "INSERT OR IGNORE INTO llm_providers(id,name,base_url,api_key,framework) "
                "VALUES(?,?,?,?,?)",
                (p["id"], p["name"], p.get("base_url", ""),
                 p.get("api_key", ""), p.get("framework", "openai")),
            )

        print(f"  LLM Model：{len(models)} 条")
        for m in models:
            conn.execute(
                "INSERT OR IGNORE INTO llm_models(id,name,display_name,provider_id) "
                "VALUES(?,?,?,?)",
                (m["id"], m["name"], m.get("display_name", m["name"]), m["provider_id"]),
            )

    # ── 复制文件 ────────────────────────────────────────────────────────────────
    print("▶ 复制媒体文件 Assets/ → data/ …")
    path_map = _copy_assets()
    print(f"  复制文件数：{len(path_map) // 3}")  # 每文件存3种路径变体

    # ── 迁移 session 数据 ────────────────────────────────────────────────────────
    db_data: list[dict] = _load_json(OLD_DB_FILE) or []
    print(f"▶ 迁移 session 数据：{len(db_data)} 条…")

    with _conn() as conn:
        for s in db_data:
            sid = s.get("session_id", "")
            if not sid:
                continue

            conn.execute(
                """INSERT OR IGNORE INTO sessions
                   (id,status,source_type,content_time,description,
                    feeling,reason,is_complete,upload_time,archive_time)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    s.get("status",       "pending"),
                    s.get("source_type",  "file"),
                    s.get("content_time", ""),
                    s.get("description",  ""),
                    s.get("feeling",      ""),
                    s.get("reason",       ""),
                    int(bool(s.get("is_complete", False))),
                    s.get("upload_time",  datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    s.get("archive_time", ""),
                ),
            )

            for fe in s.get("files", []):
                new_path = _remap_path(fe.get("path", ""), path_map)
                conn.execute(
                    "INSERT OR IGNORE INTO session_files"
                    "(session_id,filename,original_name,path) VALUES(?,?,?,?)",
                    (sid, fe.get("filename", ""), fe.get("original_name", ""), new_path),
                )

            for tag in s.get("tags", []):
                conn.execute(
                    "INSERT OR IGNORE INTO session_tags(session_id,tag) VALUES(?,?)",
                    (sid, tag),
                )

            for gid in s.get("group_ids", []):
                # 确保 group 存在再关联
                exists = conn.execute(
                    "SELECT 1 FROM groups WHERE id=?", (gid,)
                ).fetchone()
                if exists:
                    conn.execute(
                        "INSERT OR IGNORE INTO session_groups(session_id,group_id) VALUES(?,?)",
                        (sid, gid),
                    )

            for edit in s.get("edit_history", []):
                conn.execute(
                    "INSERT INTO edit_history(session_id,edited_at,changes) VALUES(?,?,?)",
                    (
                        sid,
                        edit.get("edited_at", ""),
                        json.dumps(edit.get("changes", {}), ensure_ascii=False),
                    ),
                )

            for c in s.get("comments", []):
                if not isinstance(c, dict):
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO comments(id,session_id,body,created_at) VALUES(?,?,?,?)",
                    (
                        c.get("id", datetime.now().strftime("%Y%m%d_%H%M%S_%f")),
                        sid,
                        c.get("text", ""),
                        c.get("created_at", ""),
                    ),
                )

    # ── 验证 ────────────────────────────────────────────────────────────────────
    with _conn() as conn:
        n_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        n_files    = conn.execute("SELECT COUNT(*) FROM session_files").fetchone()[0]
        n_tags_reg = conn.execute("SELECT COUNT(*) FROM tags_registry").fetchone()[0]
        n_providers = conn.execute("SELECT COUNT(*) FROM llm_providers").fetchone()[0]

    print(f"\n✅ 迁移完成：")
    print(f"   sessions     : {n_sessions}  (原 JSON：{len(db_data)})")
    print(f"   session_files: {n_files}")
    print(f"   tags_registry: {n_tags_reg}")
    print(f"   llm_providers: {n_providers}")

    # ── 备份原文件 ─────────────────────────────────────────────────────────────
    for f in [OLD_DB_FILE, OLD_CONFIG]:
        if f.exists():
            bak = f.with_suffix(f.suffix + ".bak")
            f.rename(bak)
            print(f"   备份：{f} → {bak}")

    if n_sessions != len(db_data):
        print("\n⚠️  session 数量不一致，请检查原始数据。")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
