"""MyPresent 应用入口。运行：streamlit run app.py"""
from __future__ import annotations

import streamlit as st

from mypresent.file_io import ensure_dirs
from mypresent.state import init_state
from mypresent.vector_db import _ensure_indexed
from mypresent.ui.tab_upload import render_upload_tab
from mypresent.ui.tab_gallery import render_gallery_tab
from mypresent.ui.tab_archived import render_archived_tab
from mypresent.ui.tab_search import render_search_tab


def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    ensure_dirs()
    init_state()
    _ensure_indexed()

    st.title("🗂️ 灵感记录工具")
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗂️ 记录舱（上传）",
        "🖼️ 灵感墙（待处理）",
        "📚 已归档",
        "🔍 搜索",
    ])

    with tab1:
        render_upload_tab()
    with tab2:
        render_gallery_tab()
    with tab3:
        render_archived_tab()
    with tab4:
        render_search_tab()


if __name__ == "__main__":
    main()
