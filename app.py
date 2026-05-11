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
from components.tab_insight import render_insight_tab
from components.eval_dashboard import render_eval_dashboard
from components.tab_recycle import render_recycle_tab
from components.tab_planning import render_planning_tab


_TAB_HOME = "🏠 主页"
_TAB_RECORD = "📝 记录台"
_TAB_INSIGHT = "🪞 洞见"
_TAB_PLANNING = "📋 规划台"
_TAB_RECYCLE = "🗑️ 回收站"
_TAB_SYSTEM = "⚙️ 系统"

_NAV_ITEMS = [
    _TAB_HOME,
    _TAB_RECORD,
    _TAB_INSIGHT,
    _TAB_PLANNING,
    _TAB_RECYCLE,
    _TAB_SYSTEM,
]
_RECORD_SUB_TABS = ["⬆️ 上传", "🗂️ 待处理", "📚 已归档"]
_HOME_TARGETS = {
    "home": (_TAB_HOME, None),
    "record": (_TAB_RECORD, None),
    "search": (_TAB_INSIGHT, None),
    "insight": (_TAB_INSIGHT, None),
    "planning": (_TAB_PLANNING, None),
    "recycle": (_TAB_RECYCLE, None),
    "system": (_TAB_SYSTEM, None),
}


def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    init_db()
    ensure_dirs()
    init_state()
    _ensure_indexed()

    _consume_nav_target()
    selected = _render_nav(_NAV_ITEMS, "active_tab")

    if selected == _TAB_HOME:
        render_home(_navigate_to)
    elif selected == _TAB_RECORD:
        _render_record_tab()
    elif selected == _TAB_INSIGHT:
        render_insight_tab()
    elif selected == _TAB_PLANNING:
        render_planning_tab()
    elif selected == _TAB_RECYCLE:
        render_recycle_tab()
    elif selected == _TAB_SYSTEM:
        render_eval_dashboard()


def _consume_nav_target() -> None:
    target = st.session_state.get("_nav_target")
    if not target:
        return
    if isinstance(target, str):
        target = _HOME_TARGETS.get(target)
    if (
        isinstance(target, tuple)
        and len(target) == 2
        and target[0] in _NAV_ITEMS
    ):
        tab_name, sub_tab = target
        st.session_state["active_tab"] = tab_name
        if sub_tab:
            if not isinstance(st.session_state.get("active_sub_tab"), dict):
                st.session_state["active_sub_tab"] = {}
            st.session_state.setdefault("active_sub_tab", {})[tab_name] = sub_tab
    st.session_state["_nav_target"] = None


def _navigate_to(target: str) -> None:
    nav_target = _HOME_TARGETS.get(target)
    if nav_target:
        st.session_state["_nav_target"] = nav_target
        st.rerun()


def _render_nav(options: list[str], state_key: str) -> str:
    current = st.session_state.get(state_key)
    if current not in options:
        current = options[0]
        st.session_state[state_key] = current

    cols = st.columns(len(options))
    for col, option in zip(cols, options):
        with col:
            if st.button(
                option,
                key=f"nav_{state_key}_{option}",
                type="primary" if option == current else "secondary",
                use_container_width=True,
            ):
                st.session_state[state_key] = option
                st.rerun()
    return st.session_state[state_key]


def _render_record_tab() -> None:
    if not isinstance(st.session_state.get("active_sub_tab"), dict):
        st.session_state["active_sub_tab"] = {}
    sub_state = st.session_state.setdefault("active_sub_tab", {})
    selected = sub_state.get(_TAB_RECORD, _RECORD_SUB_TABS[0])
    if selected not in _RECORD_SUB_TABS:
        selected = _RECORD_SUB_TABS[0]
        sub_state[_TAB_RECORD] = selected

    cols = st.columns(len(_RECORD_SUB_TABS))
    for col, option in zip(cols, _RECORD_SUB_TABS):
        with col:
            if st.button(
                option,
                key=f"nav_record_{option}",
                type="primary" if option == selected else "secondary",
                use_container_width=True,
            ):
                sub_state[_TAB_RECORD] = option
                st.rerun()
    selected = sub_state.get(_TAB_RECORD, selected)

    if selected == "⬆️ 上传":
        render_upload_tab()
    elif selected == "🗂️ 待处理":
        render_gallery_tab()
    elif selected == "📚 已归档":
        render_archived_tab()


if __name__ == "__main__":
    main()
