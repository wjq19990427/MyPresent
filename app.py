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


def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    init_db()
    ensure_dirs()
    init_state()
    _ensure_indexed()

    tabs = st.tabs([
        "🏠 主页",
        "📝 记录台",
        "🔍 探索",
        "📋 规划台",
        "🗑️ 回收站",
        "⚙️ 系统",
    ])

    with tabs[0]:
        render_home()
    with tabs[1]:
        inner = st.tabs(["⬆️ 上传", "🗂️ 待处理", "📚 已归档"])
        with inner[0]:
            render_upload_tab()
        with inner[1]:
            render_gallery_tab()
        with inner[2]:
            render_archived_tab()
    with tabs[2]:
        render_search_tab()
    with tabs[3]:
        render_planning_tab()
    with tabs[4]:
        render_recycle_tab()
    with tabs[5]:
        render_eval_dashboard()


if __name__ == "__main__":
    main()
