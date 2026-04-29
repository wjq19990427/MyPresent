"""标签注册表与分组 CRUD。"""
from __future__ import annotations

import json
from datetime import datetime

from .constants import CONFIG_FILE, DEFAULT_TAGS


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"tags_registry": DEFAULT_TAGS.copy(), "groups": []}


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_tags_registry() -> list[str]:
    return load_config().get("tags_registry", DEFAULT_TAGS[:])


def add_tag(tag: str) -> None:
    tag = tag.strip()
    if not tag:
        return
    cfg = load_config()
    if tag not in cfg.get("tags_registry", []):
        cfg.setdefault("tags_registry", []).append(tag)
        save_config(cfg)


def remove_tag(tag: str) -> None:
    cfg = load_config()
    cfg["tags_registry"] = [t for t in cfg.get("tags_registry", []) if t != tag]
    save_config(cfg)


def get_groups() -> list[dict]:
    return load_config().get("groups", [])


def create_group(name: str) -> str:
    name = name.strip()
    if not name:
        return ""
    group_id = f"grp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cfg = load_config()
    cfg.setdefault("groups", []).append({
        "id":         group_id,
        "name":       name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_config(cfg)
    return group_id


def delete_group(group_id: str) -> None:
    from .db import load_db, save_db
    cfg = load_config()
    cfg["groups"] = [g for g in cfg.get("groups", []) if g["id"] != group_id]
    save_config(cfg)
    db = load_db()
    changed = False
    for s in db:
        if group_id in s.get("group_ids", []):
            s["group_ids"] = [g for g in s["group_ids"] if g != group_id]
            changed = True
    if changed:
        save_db(db)
