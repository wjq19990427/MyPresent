"""MyPresent 应用入口。运行：streamlit run app.py"""
from __future__ import annotations

import streamlit as st

from core.db_manager import init_db
from core.file_io import ensure_dirs
from core.state import init_state
from core.vector_db import _ensure_indexed
from components.tab_upload import render_upload_tab
from components.tab_gallery import render_gallery_tab
from components.tab_archived import render_archived_tab
from components.tab_search import render_search_tab
from components.eval_dashboard import render_eval_dashboard
from components.tab_recycle import render_recycle_tab


def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    init_db()
    ensure_dirs()
    init_state()
    _ensure_indexed()

    st.title("🗂️ MyPresent 智能个人记录整理助手")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🗂️ 记录舱（上传）",
        "🖼️ 灵感墙（待处理）",
        "📚 已归档",
        "🔍 搜索",
        "📊 运行看板",
        "🗑️ 回收站",
    ])

    with tab1:
        render_upload_tab()
    with tab2:
        render_gallery_tab()
    with tab3:
        render_archived_tab()
    with tab4:
        render_search_tab()
    with tab5:
        render_eval_dashboard()
    with tab6:
        render_recycle_tab()


if __name__ == "__main__":
    main()
