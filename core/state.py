"""Streamlit session state 初始化。"""
from __future__ import annotations

from datetime import datetime

import streamlit as st


def init_state() -> None:
    for k, v in {
        "active_tab":           "🏠 主页",
        "active_sub_tab":       {},
        "_nav_target":          None,
        "upload_key":            0,
        "upload_prefill":        None,
        "pending_selected":      None,
        "archived_selected":     None,
        "search_selected":       None,
        "batch_selected_ids":    set(),
        "batch_mode_gallery":    False,
        "batch_mode_archived":   False,
        "semantic_results":      None,
        "semantic_query_used":   "",
        "date_filter_exact":     None,
        "date_filter_fuzzy":     None,
        "date_filter_range":     ("", ""),
        "_search_mode_prev":     None,
        "archived_type_filter":  "全部",
        "archived_tag_filter":   [],
        "archived_group_filter": None,
        "archived_view_mode":    "all",
        "archived_group_selected": None,
        "folder_selected_path":  "",
        "folder_scan_results":   [],
        "folder_scan_skipped_n": 0,
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
        "planning_sub_tab":       "calendar",
        "planning_goal_editing":  None,
        "planning_cat_manager_open": False,
        "planning_goal_filter_status": [],
        "planning_goal_filter_cat":    [],
        "planning_cal_year":      datetime.now().year,
        "planning_cal_month":     datetime.now().month,
        "planning_cal_date":      None,
        "planning_todo_adding":   False,
        "planning_activity_adding": False,
        "planning_record_moment_date": None,
        "_reflection_open":       {},
        "_postpone_open":         {},
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v
