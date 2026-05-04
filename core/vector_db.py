"""ChromaDB + BGE embedding 层。"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from .constants import VECTOR_DB_DIR
from .db_manager import load_db


@st.cache_resource(show_spinner="正在加载 Embedding 模型（首次需要下载，请稍候）…")
def _get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("BAAI/bge-small-zh-v1.5")


@st.cache_resource(show_spinner="正在初始化向量数据库…")
def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
    return client.get_or_create_collection(
        name="sessions",
        metadata={"hnsw:space": "cosine"},
    )


def _build_embed_text(session: dict) -> str:
    parts = []
    for key, label in [
        ("content_time", "创建时间"),
        ("description",  "描述"),
        ("feeling",      "感受"),
        ("reason",       "记录原因"),
    ]:
        v = str(session.get(key, "")).strip()
        if v:
            parts.append(f"{label}：{v}")
    tags = session.get("tags", [])
    if tags:
        parts.append(f"标签：{'、'.join(tags)}")
    return "\n".join(parts)


def _parse_date_iso(raw: str) -> tuple[str, int]:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
                "%Y-%m",   "%Y/%m",    "%Y"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d"), int(dt.strftime("%Y%m%d"))
        except ValueError:
            continue
    return "", 0


def _build_chroma_metadata(session: dict) -> dict:
    raw      = str(session.get("content_time", "")).strip()
    iso, num = _parse_date_iso(raw)
    return {
        "session_id":        session["session_id"],
        "content_time_raw":  raw,
        "content_time_iso":  iso,
        "content_time_num":  num,
        "has_exact_date":    iso != "",
        "upload_time":       session.get("upload_time", ""),
        "archive_time":      session.get("archive_time", ""),
        "source_type":       session.get("source_type", ""),
    }


def embed_session(session: dict) -> None:
    try:
        text = _build_embed_text(session)
        if not text.strip():
            return
        embedding = _get_embedder().encode(
            text, normalize_embeddings=True
        ).tolist()
        _get_collection().upsert(
            ids=[session["session_id"]],
            embeddings=[embedding],
            documents=[text],
            metadatas=[_build_chroma_metadata(session)],
        )
    except Exception:
        pass


def delete_embedding(session_id: str) -> None:
    try:
        _get_collection().delete(ids=[session_id])
    except Exception:
        pass


def index_existing_finals() -> int:
    db     = load_db()
    finals = [s for s in db if s.get("status") == "final"]
    if not finals:
        return 0
    existing = set(_get_collection().get(include=[])["ids"])
    to_index = [s for s in finals if s["session_id"] not in existing]
    for s in to_index:
        embed_session(s)
    return len(to_index)


def _ensure_indexed() -> None:
    if st.session_state.get("_vector_db_ready"):
        return
    st.session_state["_vector_db_ready"] = True
    db     = load_db()
    finals = [s for s in db if s.get("status") == "final"]
    if not finals:
        return
    try:
        with st.spinner("🗄️ 正在初始化向量库…"):
            col      = _get_collection()
            existing = col.get(include=["metadatas"])
            existing_ids = set(existing["ids"])

            needs_migration = bool(existing["metadatas"]) and \
                              "content_time_num" not in existing["metadatas"][0]

            if needs_migration:
                for s in finals:
                    embed_session(s)
                count = len(finals)
            else:
                to_index = [s for s in finals if s["session_id"] not in existing_ids]
                for s in to_index:
                    embed_session(s)
                count = len(to_index)

        if count > 0:
            label = "已迁移并重建" if needs_migration else "已补全索引"
            st.toast(f"向量库{label}：{count} 条归档记录", icon="🗄️")
    except Exception as e:
        st.warning(f"向量库初始化失败（搜索功能不可用）：{e}")
