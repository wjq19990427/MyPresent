"""Streamlit session state 初始化。"""
from __future__ import annotations

import streamlit as st


def init_state() -> None:
    for k, v in {
        "upload_key":            0,
        "pending_selected":      None,
        "archived_selected":     None,
        "search_selected":       None,
        "semantic_results":      None,
        "semantic_query_used":   "",
        "date_filter_exact":     None,
        "date_filter_fuzzy":     None,
        "date_filter_range":     ("", ""),
        "_search_mode_prev":     None,
        "archived_type_filter":  "全部",
        "archived_tag_filter":   [],
        "archived_group_filter": None,
        "folder_scan_results":   [],
        "folder_import_done":    0,
        "_show_no_tag_only":     False,
        # 智能问答
        "llm_selected_model":    None,
        "llm_chat_history":      [],
        "_editing_pvd":          None,
        "_editing_mdl":          None,
        # 新增/编辑配置测试流程
        "_draft_provider":       None,
        "_draft_model":          None,
        "_test_result":          None,
        "_draft_test_passed":    False,
        "_confirm_edit_pvd":     None,
        "_confirm_edit_mdl":     None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v
