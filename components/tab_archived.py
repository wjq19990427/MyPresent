"""已归档 Tab：全部筛选 / 分组相册浏览 + 编辑。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.constants import COLS, IMAGE_EXTS, VIDEO_EXTS
from core.db_manager import (
    create_group,
    delete_group,
    get_groups,
    get_label_registry,
    load_db,
    soft_delete_session,
    update_session_groups,
)
from core.file_io import _session_file_type
from core.media import pil_to_png_bytes, video_thumbnail
from components.cards import (
    _render_batch_row,
    _render_card,
    _render_detail,
    _render_group_manager,
    _render_label_manager,
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

    view_mode = _render_view_switch()
    if view_mode == "groups":
        _render_groups_view(all_db, all_finals)
    else:
        _render_all_view(all_db, all_finals)


def _render_view_switch() -> str:
    current = st.session_state.get("archived_view_mode", "all")
    col_all, col_groups, spacer, col_batch = st.columns([1, 1, 4, 1.2])
    with col_all:
        if st.button(
            "📋 全部",
            key="archived_view_all",
            type="primary" if current == "all" else "secondary",
            use_container_width=True,
        ):
            st.session_state["archived_view_mode"] = "all"
            st.session_state["archived_group_selected"] = None
            st.session_state["archived_selected"] = None
            st.rerun()
    with col_groups:
        if st.button(
            "📁 分组",
            key="archived_view_groups",
            type="primary" if current == "groups" else "secondary",
            use_container_width=True,
        ):
            st.session_state["archived_view_mode"] = "groups"
            st.session_state["archived_selected"] = None
            st.rerun()
    with col_batch:
        batch_mode = st.session_state.get("batch_mode_archived", False)
        if st.button(
            "批量管理" if not batch_mode else "退出批量",
            key="toggle_batch_archived",
            use_container_width=True,
        ):
            st.session_state["batch_mode_archived"] = not batch_mode
            st.session_state["batch_selected_ids"] = set()
            st.rerun()
    return st.session_state.get("archived_view_mode", "all")


def _render_all_view(all_db: list[dict], all_finals: list[dict]) -> None:
    groups = get_groups()
    _render_group_filter(groups)

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

    db = _filter_finals(all_finals, type_filter, selected_filters)
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

    if st.session_state.get("batch_mode_archived", False):
        _render_batch_tools(db, groups, mode="all")
        return

    _render_session_grid(db, "archived_selected")

    if not sel:
        return
    target = next((s for s in all_db if s["session_id"] == sel), None)
    if not target:
        st.session_state.archived_selected = None
        return
    st.divider()
    _render_detail(target, "final")


def _render_groups_view(all_db: list[dict], all_finals: list[dict]) -> None:
    groups = get_groups()
    selected_gid = st.session_state.get("archived_group_selected")
    group_map = {g["id"]: g for g in groups}

    if selected_gid and selected_gid in group_map:
        _render_group_detail(all_db, all_finals, group_map[selected_gid])
        return
    if selected_gid:
        st.session_state["archived_group_selected"] = None

    st.markdown("#### 分组")
    _render_create_group("group_album_create")
    if not groups:
        st.info("暂无分组。先新建分组，再从全部模式批量加入记录。")
        return

    counts = {
        group["id"]: sum(1 for s in all_finals if group["id"] in s.get("group_ids", []))
        for group in groups
    }
    first_sessions = {
        group["id"]: next(
            (s for s in all_finals if group["id"] in s.get("group_ids", [])),
            None,
        )
        for group in groups
    }

    for row_start in range(0, len(groups), COLS):
        cols = st.columns(COLS)
        for col, group in zip(cols, groups[row_start: row_start + COLS]):
            _render_group_tile(
                col,
                group,
                counts.get(group["id"], 0),
                first_sessions.get(group["id"]),
                all_finals,
            )


def _render_group_detail(
    all_db: list[dict],
    all_finals: list[dict],
    group: dict,
) -> None:
    gid = group["id"]
    top_cols = st.columns([1.2, 5])
    with top_cols[0]:
        if st.button("← 返回", key=f"back_group_{gid}", use_container_width=True):
            st.session_state["archived_group_selected"] = None
            st.session_state["archived_selected"] = None
            st.session_state["batch_selected_ids"] = set()
            st.rerun()
    with top_cols[1]:
        st.subheader(f"📁 {group['name']}")

    db = [s for s in all_finals if gid in s.get("group_ids", [])]
    st.caption(f"共 **{len(db)}** 条记录")

    if not db:
        st.info("这个分组里还没有记录。")
        return

    if st.session_state.get("batch_mode_archived", False):
        _render_batch_tools(db, get_groups(), mode="group", group_id=gid)
        return

    _render_session_grid(db, "archived_selected")

    sel = st.session_state.get("archived_selected")
    if not sel:
        return
    target = next((s for s in all_db if s["session_id"] == sel), None)
    if not target:
        st.session_state.archived_selected = None
        return
    st.divider()
    _render_detail(target, "final")


def _render_group_filter(groups: list[dict]) -> None:
    if not groups:
        return
    st.markdown("**分组**")
    btn_labels = ["全部"] + [g["name"] for g in groups]
    btn_ids = [None] + [g["id"] for g in groups]
    gf_current = st.session_state.get("archived_group_filter")
    for row_start in range(0, len(btn_labels), 8):
        grp_cols = st.columns(min(len(btn_labels) - row_start, 8))
        for i, (label, gid) in enumerate(
            zip(btn_labels[row_start: row_start + 8], btn_ids[row_start: row_start + 8])
        ):
            with grp_cols[i]:
                is_active = gf_current == gid
                key_gid = gid or "all"
                if st.button(
                    label,
                    key=f"grp_btn_{row_start}_{key_gid}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["archived_group_filter"] = None if is_active else gid
                    st.session_state["archived_selected"] = None
                    st.rerun()


def _filter_finals(
    all_finals: list[dict],
    type_filter: str,
    selected_filters: dict[str, list[str]],
) -> list[dict]:
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
    return db


def _render_batch_tools(
    sessions: list[dict],
    groups: list[dict],
    *,
    mode: str,
    group_id: str | None = None,
) -> None:
    selected: set = st.session_state.get("batch_selected_ids", set())
    st.markdown(f"已选 **{len(selected)}** 条")

    if mode == "group":
        col_a, col_b, col_c = st.columns(3)
    else:
        col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("批量移入回收站", disabled=not selected):
            for sid in list(selected):
                soft_delete_session(sid)
            st.session_state["batch_selected_ids"] = set()
            st.rerun()
    with col_b:
        if mode == "group":
            if st.button("移出分组", disabled=not selected):
                for session in _selected_sessions(sessions, selected):
                    new_gids = [gid for gid in session.get("group_ids", []) if gid != group_id]
                    update_session_groups(session["session_id"], new_gids)
                st.session_state["batch_selected_ids"] = set()
                st.rerun()
        else:
            if st.button("📁 加入分组", disabled=not selected or not groups):
                st.session_state["_archived_add_group_open"] = True
                st.rerun()
    with col_c:
        if st.button("全部取消选择", disabled=not selected):
            st.session_state["batch_selected_ids"] = set()
            st.rerun()

    if mode == "all":
        _render_batch_add_group(groups, sessions, selected)

    st.divider()
    for session in sessions:
        _render_batch_row(session)
    st.divider()


def _render_batch_add_group(
    groups: list[dict],
    sessions: list[dict],
    selected: set,
) -> None:
    if not st.session_state.get("_archived_add_group_open"):
        return
    if not groups:
        st.warning("暂无可加入的分组，请先创建分组。")
        return
    group_map = {g["id"]: g["name"] for g in groups}
    target_gid = st.selectbox(
        "选择目标分组",
        options=[g["id"] for g in groups],
        format_func=lambda gid: group_map.get(gid, gid),
        key="archived_batch_target_group",
    )
    col_apply, col_cancel = st.columns(2)
    with col_apply:
        if st.button("确认加入", disabled=not selected, type="primary"):
            for session in _selected_sessions(sessions, selected):
                existing = list(session.get("group_ids", []))
                if target_gid not in existing:
                    update_session_groups(session["session_id"], [*existing, target_gid])
            st.session_state["batch_selected_ids"] = set()
            st.session_state["_archived_add_group_open"] = False
            st.rerun()
    with col_cancel:
        if st.button("取消加入"):
            st.session_state["_archived_add_group_open"] = False
            st.rerun()


def _selected_sessions(sessions: list[dict], selected: set) -> list[dict]:
    return [s for s in sessions if s["session_id"] in selected]


def _render_session_grid(sessions: list[dict], state_key: str) -> None:
    for row_start in range(0, len(sessions), COLS):
        cols = st.columns(COLS)
        for col, session in zip(cols, sessions[row_start: row_start + COLS]):
            _render_card(col, session, state_key)


def _render_create_group(key_prefix: str) -> None:
    with st.expander("⊕ 新建分组"):
        input_key = f"{key_prefix}_input"
        new_group = st.text_input("分组名称", key=input_key, placeholder="输入分组名称")
        if st.button("创建", key=f"{key_prefix}_btn", type="primary"):
            if new_group.strip():
                create_group(new_group)
                if input_key in st.session_state:
                    del st.session_state[input_key]
                st.rerun()
            else:
                st.warning("分组名不能为空")


def _render_group_tile(
    col,
    group: dict,
    count: int,
    first_session: dict | None,
    all_finals: list[dict],
) -> None:
    gid = group["id"]
    with col:
        with st.container(border=True):
            thumb = _group_cover(first_session)
            if thumb:
                st.image(thumb, use_container_width=True)
            else:
                st.markdown(
                    _placeholder_html(group.get("name", "")),
                    unsafe_allow_html=True,
                )
            st.markdown(f"**{group['name']}**")
            st.caption(f"{count} 条记录")
            if st.button("打开", key=f"open_group_{gid}", use_container_width=True):
                st.session_state["archived_group_selected"] = gid
                st.session_state["archived_selected"] = None
                st.rerun()

            c_rename, c_delete = st.columns(2)
            with c_rename:
                if st.button("✎", key=f"rename_group_{gid}", help="改名"):
                    st.session_state["_renaming_group"] = gid
                    st.rerun()
            with c_delete:
                if st.button("🗑️", key=f"delete_group_{gid}", help="删除分组"):
                    st.session_state["_deleting_group"] = gid
                    st.rerun()

            if st.session_state.get("_renaming_group") == gid:
                _render_group_rename(group, all_finals)
            if st.session_state.get("_deleting_group") == gid:
                _render_group_delete(group)


def _render_group_rename(group: dict, all_finals: list[dict]) -> None:
    gid = group["id"]
    input_key = f"rename_group_input_{gid}"
    new_name = st.text_input("新名称", value=group["name"], key=input_key)
    c_save, c_cancel = st.columns(2)
    with c_save:
        if st.button("保存", key=f"save_rename_group_{gid}", type="primary"):
            new_gid = create_group(new_name)
            if not new_gid:
                st.warning("分组名不能为空")
                return
            for session in all_finals:
                gids = session.get("group_ids", [])
                if gid not in gids:
                    continue
                next_gids = [new_gid if item == gid else item for item in gids]
                update_session_groups(session["session_id"], next_gids)
            delete_group(gid)
            st.session_state["_renaming_group"] = None
            if st.session_state.get("archived_group_filter") == gid:
                st.session_state["archived_group_filter"] = new_gid
            if st.session_state.get("archived_group_selected") == gid:
                st.session_state["archived_group_selected"] = new_gid
            st.rerun()
    with c_cancel:
        if st.button("取消", key=f"cancel_rename_group_{gid}"):
            st.session_state["_renaming_group"] = None
            st.rerun()


def _render_group_delete(group: dict) -> None:
    gid = group["id"]
    st.warning(f"确认删除分组「{group['name']}」？记录本身不会删除。")
    c_confirm, c_cancel = st.columns(2)
    with c_confirm:
        if st.button("确认删除", key=f"confirm_delete_group_{gid}", type="primary"):
            delete_group(gid)
            st.session_state["_deleting_group"] = None
            if st.session_state.get("archived_group_filter") == gid:
                st.session_state["archived_group_filter"] = None
            if st.session_state.get("archived_group_selected") == gid:
                st.session_state["archived_group_selected"] = None
            st.rerun()
    with c_cancel:
        if st.button("取消", key=f"cancel_delete_group_{gid}"):
            st.session_state["_deleting_group"] = None
            st.rerun()


def _group_cover(session: dict | None) -> bytes | str | None:
    if not session:
        return None
    for file_entry in session.get("files", []):
        fp = Path(file_entry.get("path", ""))
        if not fp.exists():
            continue
        ext = fp.suffix.lower()
        if ext in IMAGE_EXTS:
            return str(fp)
        if ext in VIDEO_EXTS:
            thumb = video_thumbnail(fp)
            return pil_to_png_bytes(thumb) if thumb else None
    return None


def _placeholder_html(name: str) -> str:
    first = (name.strip() or "组")[0]
    return (
        "<div style='height:180px;display:flex;align-items:center;justify-content:center;"
        "border:1px solid #e5e7eb;border-radius:8px;background:#f8fafc;"
        "font-size:56px;font-weight:700;color:#64748b;'>"
        f"{first}</div>"
    )


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
