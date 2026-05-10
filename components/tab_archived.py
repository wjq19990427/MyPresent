"""已归档 Tab：分组 / 类型 / 结构化标签过滤 + 编辑。"""
from __future__ import annotations

import streamlit as st

from core.constants import COLS
from core.db_manager import (
    get_groups, get_label_registry, load_db, soft_delete_session,
)
from core.file_io import _session_file_type
from components.cards import (
    _render_batch_row, _render_card, _render_detail,
    _render_group_manager, _render_label_manager,
)


_FILTERS = [
    ("domains", "domain", "领域筛选", "archived_domain_filter", "#2563eb"),
    ("topics", "topic", "话题筛选", "archived_topic_filter", "#16a34a"),
    ("emotion_tags", "emotion", "情绪筛选", "archived_emotion_filter", "#db2777"),
]


def render_archived_tab() -> None:
    all_db = load_db()
    all_finals = sorted(
        [s for s in all_db if s.get("status") == "final"],
        key=lambda s: s.get("upload_time", ""),
        reverse=True,
    )

    if not all_finals:
        st.info("暂无已归档记录。在「灵感墙」补全后归档，或在「记录台」直接完成归档。")
        return

    _, col_batch = st.columns([6, 1])
    with col_batch:
        batch_mode = st.session_state.get("batch_mode_archived", False)
        if st.button(
            "批量管理" if not batch_mode else "退出批量",
            key="toggle_batch_archived",
        ):
            st.session_state["batch_mode_archived"] = not batch_mode
            st.session_state["batch_selected_ids"] = set()
            st.rerun()

    groups = get_groups()
    group_map = {g["id"]: g["name"] for g in groups}
    if groups:
        st.markdown("**分组**")
        btn_labels = ["全部"] + [g["name"] for g in groups]
        btn_ids = [None] + [g["id"] for g in groups]
        gf_current = st.session_state.get("archived_group_filter")
        grp_cols = st.columns(min(len(btn_labels), 8))
        for i, (label, gid) in enumerate(zip(btn_labels, btn_ids)):
            with grp_cols[i]:
                is_active = gf_current == gid
                if st.button(
                    label,
                    key=f"grp_btn_{i}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["archived_group_filter"] = None if is_active else gid
                    st.session_state["archived_selected"] = None
                    st.rerun()

    type_filter = st.radio(
        "文件类型",
        ["全部", "图片", "视频", "文本"],
        horizontal=True,
        key="archived_type_filter",
    )

    selected_filters = {
        field: _render_structured_filter(label_type, label, key, color)
        for field, label_type, label, key, color in _FILTERS
    }

    m1, m2 = st.columns(2)
    with m1:
        with st.expander("管理标签库"):
            _render_label_manager()
    with m2:
        with st.expander("管理分组"):
            _render_group_manager()

    db = all_finals
    gf = st.session_state.get("archived_group_filter")
    if gf:
        db = [s for s in db if gf in s.get("group_ids", [])]

    type_map = {"图片": "images", "视频": "videos", "文本": "text"}
    if type_filter != "全部":
        db = [s for s in db if _session_file_type(s) == type_map.get(type_filter, "")]

    for field, _label_type, _label, key, _color in _FILTERS:
        selected = selected_filters[field]
        options = st.session_state.get(f"{key}_options", [])
        if selected and len(selected) < len(options):
            db = [s for s in db if any(v in s.get(field, []) for v in selected)]

    sel = st.session_state.get("archived_selected")
    if sel and sel not in {s["session_id"] for s in db}:
        st.session_state["archived_selected"] = None
        sel = None

    st.divider()
    total_label = f"共 **{len(all_finals)}** 条已归档"
    if len(db) != len(all_finals):
        total_label += f"，当前筛选显示 **{len(db)}** 条"
    st.caption(total_label)

    if not db:
        st.info("当前筛选条件下没有记录。")
        return

    if batch_mode:
        selected: set = st.session_state.get("batch_selected_ids", set())
        st.markdown(f"已选 **{len(selected)}** 条")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("批量移入回收站", disabled=not selected):
                for sid in list(selected):
                    soft_delete_session(sid)
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        with col_b:
            if st.button("全部取消选择", disabled=not selected):
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        st.divider()
        for session in db:
            _render_batch_row(session)
        st.divider()
        return

    for row_start in range(0, len(db), COLS):
        cols = st.columns(COLS)
        for col, session in zip(cols, db[row_start: row_start + COLS]):
            _render_card(col, session, "archived_selected")

    if not sel:
        return
    target = next((s for s in all_db if s["session_id"] == sel), None)
    if not target:
        st.session_state.archived_selected = None
        return
    st.divider()
    _render_detail(target, "final")


def _render_structured_filter(
    label_type: str,
    label: str,
    key: str,
    color: str,
) -> list[str]:
    options = [item["name"] for item in get_label_registry(label_type)]
    previous_options = st.session_state.get(f"{key}_options", [])
    st.session_state[f"{key}_options"] = options

    current = st.session_state.get(key)
    if current is None or set(current) == set(previous_options):
        st.session_state[key] = list(options)
    else:
        st.session_state[key] = [item for item in current if item in options]

    st.markdown(
        f"<span style='display:inline-block;margin-top:6px;padding:2px 8px;"
        f"border-radius:999px;background:{color};color:white;font-size:12px;'>"
        f"{label}</span>",
        unsafe_allow_html=True,
    )
    return st.multiselect(
        label,
        options=options,
        key=key,
        label_visibility="collapsed",
        placeholder="默认全选；全部勾选等同于不筛选",
    )
