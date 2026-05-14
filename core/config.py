"""Deployment configuration and per-user path resolution."""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv

from . import constants

load_dotenv()

DEPLOY_MODE: str = os.getenv("DEPLOY_MODE", "local").strip().lower()
if DEPLOY_MODE not in {"local", "cloud"}:
    raise ValueError("DEPLOY_MODE 必须为 local 或 cloud")

_current_user: ContextVar[str | None] = ContextVar("current_user", default=None)


def set_current_user(username: str | None) -> None:
    if DEPLOY_MODE == "local":
        return
    _current_user.set(username)


def get_current_user() -> str | None:
    if DEPLOY_MODE == "local":
        return None
    return _current_user.get()


def _resolve_user(username: str | None) -> str:
    user = username if username is not None else get_current_user()
    if not user:
        raise RuntimeError("Cloud 模式下未设置当前用户")
    return user


def _user_root(username: str | None = None) -> Path:
    return constants.DATA_DIR / "users" / _resolve_user(username)


def get_global_db_path() -> Path:
    """全局认证库，始终指向 data/database.db，仅含 users 表。"""
    return constants.DB_PATH


def get_db_path(username: str | None = None) -> Path:
    if DEPLOY_MODE == "local":
        return constants.DB_PATH
    return _user_root(username) / "database.db"


def get_vector_db_dir(username: str | None = None) -> Path:
    if DEPLOY_MODE == "local":
        return constants.VECTOR_DB_DIR
    return _user_root(username) / "vector_db"


def get_pending_dir(username: str | None = None) -> Path:
    if DEPLOY_MODE == "local":
        return constants.PENDING_DIR
    return _user_root(username) / "pending"


def get_final_dir(username: str | None = None) -> Path:
    if DEPLOY_MODE == "local":
        return constants.FINAL_DIR
    return _user_root(username) / "final"
