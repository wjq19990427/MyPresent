"""灵感墙 Tab（Pending 记录）。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from ..constants import COLS
from ..db import load_db
from .components import _render_card, _render_detail


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

    st.caption(f"共 **{len(db)}** 条待处理记录，按上传时间由近到远排列")
    st.divider()

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
