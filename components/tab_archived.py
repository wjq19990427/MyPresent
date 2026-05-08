"""已归档 Tab — 分组 / 类型 / 标签过滤 + 编辑。"""
from __future__ import annotations

import streamlit as st

from core.constants import COLS
from core.db_manager import (
    get_groups, get_session, get_tags_registry, load_db,
    soft_delete_session, update_session_tags,
)
from core.file_io import _session_file_type
from components.cards import (
    _render_batch_row, _render_card, _render_detail,
    _render_group_manager, _render_tag_manager,
)


def render_archived_tab() -> None:
    all_db     = load_db()
    all_finals = sorted(
        [s for s in all_db if s.get("status") == "final"],
        key=lambda s: s.get("upload_time", ""),
        reverse=True,
    )

    if not all_finals:
        st.info("暂无已归档记录。在「灵感墙」补全后归档，或在「记录舱」直接完成归档。")
        return

    col_title, col_batch = st.columns([6, 1])
    with col_batch:
        batch_mode = st.session_state.get("batch_mode_archived", False)
        if st.button(
            "🔲 批量管理" if not batch_mode else "✅ 退出批量",
            key="toggle_batch_archived",
        ):
            st.session_state["batch_mode_archived"] = not batch_mode
            st.session_state["batch_selected_ids"] = set()
            st.rerun()

    no_tag_count = sum(1 for s in all_finals if not s.get("tags"))
    if no_tag_count:
        with st.container():
            c_warn, c_btn = st.columns([5, 2])
            with c_warn:
                st.warning(
                    f"🏷️ 有 **{no_tag_count}** 条归档记录尚未添加标签，"
                    "建议补全以便分类检索。"
                )
            with c_btn:
                if st.button("🔍 只看无标签记录", key="filter_no_tag_btn"):
                    st.session_state["archived_tag_filter"] = []
                    st.session_state["_show_no_tag_only"] = True
                    st.rerun()

    groups    = get_groups()
    group_map = {g["id"]: g["name"] for g in groups}
    if groups:
        st.markdown("**📁 分组**")
        btn_labels = ["全部"] + [g["name"] for g in groups]
        btn_ids    = [None]   + [g["id"]   for g in groups]
        gf_current = st.session_state.get("archived_group_filter")
        grp_cols   = st.columns(min(len(btn_labels), 8))
        for i, (label, gid) in enumerate(zip(btn_labels, btn_ids)):
            with grp_cols[i]:
                is_active = (gf_current == gid)
                btn_type  = "primary" if is_active else "secondary"
                if st.button(label, key=f"grp_btn_{i}", type=btn_type,
                             use_container_width=True):
                    st.session_state["archived_group_filter"] = None if is_active else gid
                    st.session_state["archived_selected"] = None
                    st.rerun()

    fc1, fc2 = st.columns([2, 3])
    with fc1:
        type_filter = st.radio(
            "文件类型",
            ["全部", "📷 图片", "🎬 视频", "📝 文本"],
            horizontal=True,
            key="archived_type_filter",
        )
    with fc2:
        tag_filter = st.multiselect(
            "标签筛选（OR 逻辑）",
            options=get_tags_registry(),
            key="archived_tag_filter",
            placeholder="选择标签过滤，多选取并集",
        )

    m1, m2 = st.columns(2)
    with m1:
        with st.expander("⚙️ 管理标签"):
            _render_tag_manager()
    with m2:
        with st.expander("⚙️ 管理分组"):
            _render_group_manager()

    db = all_finals
    gf = st.session_state.get("archived_group_filter")
    if gf:
        db = [s for s in db if gf in s.get("group_ids", [])]

    type_map = {"📷 图片": "images", "🎬 视频": "videos", "📝 文本": "text"}
    if type_filter != "全部":
        db = [s for s in db if _session_file_type(s) == type_map.get(type_filter, "")]

    if tag_filter:
        db = [s for s in db if any(t in s.get("tags", []) for t in tag_filter)]

    if st.session_state.get("_show_no_tag_only"):
        db = [s for s in db if not s.get("tags")]
        st.info("📋 当前仅显示**无标签**记录，请逐一进入编辑添加标签。")
        if st.button("取消无标签筛选", key="cancel_no_tag_filter"):
            st.session_state["_show_no_tag_only"] = False
            st.rerun()

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
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("🗑️ 批量移入回收站", disabled=not selected):
                for sid in list(selected):
                    soft_delete_session(sid)
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        with col_b:
            new_tags = st.multiselect("选择要添加的标签", get_tags_registry(), key="batch_add_tags")
            if st.button("🏷️ 添加标签", disabled=not selected or not new_tags):
                for sid in list(selected):
                    s = get_session(sid)
                    if s:
                        merged = list(dict.fromkeys(s.get("tags", []) + new_tags))
                        update_session_tags(sid, merged)
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        with col_c:
            if st.button("↩️ 全部取消选择", disabled=not selected):
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        st.divider()
        for session in db:
            _render_batch_row(session)
        st.divider()
        return
    else:
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
