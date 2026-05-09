"""MyPresent 应用入口。运行：streamlit run app.py"""
from __future__ import annotations

import streamlit as st

from core.db_manager import init_db
from core.file_io import ensure_dirs
from core.state import init_state
from core.vector_db import _ensure_indexed
from components.tab_home import render_home
from components.tab_upload import render_upload_tab
from components.tab_gallery import render_gallery_tab
from components.tab_archived import render_archived_tab
from components.tab_search import render_search_tab
from components.eval_dashboard import render_eval_dashboard
from components.tab_recycle import render_recycle_tab
from components.tab_planning import render_planning_tab


_NAV_ITEMS = {
    "home": "🏠 主页",
    "record": "📝 记录台",
    "search": "🔍 探索",
    "planning": "📋 规划台",
    "recycle": "🗑️ 回收站",
    "system": "⚙️ 系统",
}


def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    init_db()
    ensure_dirs()
    init_state()
    _ensure_indexed()

    _sync_nav_value()
    selected = st.segmented_control(
        "主导航",
        options=list(_NAV_ITEMS.keys()),
        format_func=lambda key: _NAV_ITEMS[key],
        key="active_top_nav",
        label_visibility="collapsed",
    )
    if selected is None:
        selected = "home"

    if selected == "home":
        render_home(_navigate_to)
    elif selected == "record":
        _render_record_tab()
    elif selected == "search":
        render_search_tab()
    elif selected == "planning":
        render_planning_tab()
    elif selected == "recycle":
        render_recycle_tab()
    elif selected == "system":
        render_eval_dashboard()


def _sync_nav_value() -> None:
    target = st.session_state.get("_nav_target")
    if target in _NAV_ITEMS:
        st.session_state["active_top_nav"] = target
        st.session_state["_nav_target"] = None


def _navigate_to(target: str) -> None:
    if target in _NAV_ITEMS:
        st.session_state["_nav_target"] = target
        st.rerun()


def _render_record_tab() -> None:
    inner = st.tabs(["⬆️ 上传", "🗂️ 待处理", "📚 已归档"])
    with inner[0]:
        render_upload_tab()
    with inner[1]:
        render_gallery_tab()
    with inner[2]:
        render_archived_tab()


if __name__ == "__main__":
    main()
