"""灵感墙 Tab（Pending 记录）。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.constants import COLS
from core.db_manager import load_db, soft_delete_session
from core.file_io import move_to_final
from components.cards import _render_card, _render_batch_row, _render_detail


def render_gallery_tab() -> None:
    all_db = load_db()
    db = sorted(
        [s for s in all_db
         if s.get("status") == "pending"
         and any(Path(fe["path"]).exists() for fe in s.get("files", []))],
        key=lambda s: s.get("upload_time", ""),
        reverse=True,
    )

    if not db:
        st.info("🎉 待处理队列为空！去「记录舱」上传内容吧。")
        return

    col_title, col_batch = st.columns([6, 1])
    with col_batch:
        batch_mode = st.session_state.get("batch_mode_gallery", False)
        if st.button(
            "🔲 批量管理" if not batch_mode else "✅ 退出批量",
            key="toggle_batch_gallery",
        ):
            st.session_state["batch_mode_gallery"] = not batch_mode
            st.session_state["batch_selected_ids"] = set()
            st.rerun()

    st.caption(f"共 **{len(db)}** 条待处理记录，按上传时间由近到远排列")
    st.divider()

    if batch_mode:
        selected: set = st.session_state.get("batch_selected_ids", set())
        st.markdown(f"已选 **{len(selected)}** 条")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("🗑️ 批量移入回收站", disabled=not selected):
                for sid in list(selected):
                    soft_delete_session(sid)
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        with col_b:
            if st.button("📁 批量归档", disabled=not selected):
                for sid in list(selected):
                    move_to_final(sid)
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        with col_c:
            if st.button("↩️ 全部取消选择", disabled=not selected):
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        st.divider()
        for session in db:
            _render_batch_row(session)
        st.divider()
        return
    else:
        for row_start in range(0, len(db), COLS):
            cols = st.columns(COLS)
            for col, session in zip(cols, db[row_start: row_start + COLS]):
                _render_card(col, session, "pending_selected")

    sel = st.session_state.pending_selected
    if not sel:
        return
    target = next((s for s in db if s["session_id"] == sel), None)
    if not target:
        st.session_state.pending_selected = None
        return
    st.divider()
    _render_detail(target, "pending")
