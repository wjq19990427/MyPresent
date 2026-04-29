"""已归档 Tab — 分组 / 类型 / 标签过滤 + 编辑。"""
from __future__ import annotations

import streamlit as st

from ..constants import COLS
from ..config import get_groups, get_tags_registry
from ..db import load_db
from ..file_io import _session_file_type
from .components import _render_card, _render_detail, _render_tag_manager, _render_group_manager


def render_archived_tab() -> None:
    all_db     = load_db()
    all_finals = sorted(
        [s for s in all_db if s.get("status") == "final"],
        key=lambda s: s.get("upload_time", ""),
        reverse=True,
    )

    if not all_finals:
        st.info("暂无已归档记录。在「灵感墙」补全后归档，或在「记录舱」直接完成归档。")
        return

    # ── 分组导航 ────────────────────────────────────────────────────────────
    groups    = get_groups()
    group_map = {g["id"]: g["name"] for g in groups}
    if groups:
        st.markdown("**📁 分组**")
        btn_labels = ["全部"] + [g["name"] for g in groups]
        btn_ids    = [None]   + [g["id"]   for g in groups]
        gf_current = st.session_state.get("archived_group_filter")
        grp_cols   = st.columns(min(len(btn_labels), 8))
        for i, (label, gid) in enumerate(zip(btn_labels, btn_ids)):
            with grp_cols[i]:
                is_active = (gf_current == gid)
                btn_type  = "primary" if is_active else "secondary"
                if st.button(label, key=f"grp_btn_{i}", type=btn_type,
                             use_container_width=True):
                    st.session_state["archived_group_filter"] = None if is_active else gid
                    st.session_state["archived_selected"] = None
                    st.rerun()

    # ── 文件类型 + 标签过滤 ─────────────────────────────────────────────────
    fc1, fc2 = st.columns([2, 3])
    with fc1:
        type_filter = st.radio(
            "文件类型",
            ["全部", "📷 图片", "🎬 视频", "📝 文本"],
            horizontal=True,
            key="archived_type_filter",
        )
    with fc2:
        tag_filter = st.multiselect(
            "标签筛选（OR 逻辑）",
            options=get_tags_registry(),
            key="archived_tag_filter",
            placeholder="选择标签过滤，多选取并集",
        )

    # ── 管理工具 ────────────────────────────────────────────────────────────
    m1, m2 = st.columns(2)
    with m1:
        with st.expander("⚙️ 管理标签"):
            _render_tag_manager()
    with m2:
        with st.expander("⚙️ 管理分组"):
            _render_group_manager()

    # ── 过滤 ────────────────────────────────────────────────────────────────
    db = all_finals

    gf = st.session_state.get("archived_group_filter")
    if gf:
        db = [s for s in db if gf in s.get("group_ids", [])]

    type_map = {"📷 图片": "images", "🎬 视频": "videos", "📝 文本": "text"}
    if type_filter != "全部":
        db = [s for s in db if _session_file_type(s) == type_map.get(type_filter, "")]

    if tag_filter:
        db = [s for s in db if any(t in s.get("tags", []) for t in tag_filter)]

    sel = st.session_state.get("archived_selected")
    if sel and sel not in {s["session_id"] for s in db}:
        st.session_state["archived_selected"] = None
        sel = None

    st.divider()
    total_label = f"共 **{len(all_finals)}** 条已归档"
    if len(db) != len(all_finals):
        total_label += f"，当前筛选显示 **{len(db)}** 条"
    st.caption(total_label)

    if not db:
        st.info("当前筛选条件下没有记录。")
        return

    for row_start in range(0, len(db), COLS):
        cols = st.columns(COLS)
        for col, session in zip(cols, db[row_start: row_start + COLS]):
            _render_card(col, session, "archived_selected")

    if not sel:
        return
    target = next((s for s in all_db if s["session_id"] == sel), None)
    if not target:
        st.session_state.archived_selected = None
        return
    st.divider()
    _render_detail(target, "final")
