"""洞见 Tab：检索 / 情绪趋势 / 洞察报告。"""
from __future__ import annotations

import streamlit as st

from components.tab_search import render_search_tab


_INSIGHT_SUB_TABS = ["🔍 检索", "🌈 情绪趋势", "📋 洞察报告"]


def render_insight_tab() -> None:
    """渲染洞见 Tab 的内部子页框架。"""
    current = st.session_state.get("insight_sub_tab", _INSIGHT_SUB_TABS[0])
    if current not in _INSIGHT_SUB_TABS:
        current = _INSIGHT_SUB_TABS[0]
        st.session_state["insight_sub_tab"] = current

    cols = st.columns(len(_INSIGHT_SUB_TABS))
    for col, option in zip(cols, _INSIGHT_SUB_TABS):
        with col:
            if st.button(
                option,
                key=f"nav_insight_{option}",
                type="primary" if option == current else "secondary",
                use_container_width=True,
            ):
                st.session_state["insight_sub_tab"] = option
                st.rerun()

    selected = st.session_state.get("insight_sub_tab", current)
    st.divider()
    if selected == "🔍 检索":
        render_search_tab()
    elif selected == "🌈 情绪趋势":
        st.info("情绪趋势功能即将上线")
    elif selected == "📋 洞察报告":
        st.info("洞察报告功能即将上线")
