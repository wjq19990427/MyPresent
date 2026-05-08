"""共用 UI 组件：卡片、详情面板、评论区、标签/分组管理、AI 摘要。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.constants import (
    COLS, DEFAULT_TAGS, FIELD_SCHEMA,
    VIDEO_EXTS, VIDEO_EXTS_PLAYABLE,
)
from core.db_manager import (
    get_tags_registry, get_groups,
    add_tag, remove_tag, create_group, delete_group,
    load_db, validate_session,
    update_session_fields, add_comment, delete_comment,
    soft_delete_session,
    _is_text_session,
)
from core.file_io import _write_md, move_to_final
from core.media import video_thumbnail, pil_to_png_bytes
from components.forms import render_field_inputs
from components.ai_fill import render_ai_fill_picker
from components.ai_tagging import render_ai_tag_picker


# ─── 缩略图 ─────────────────────────────────────────────────────────────────────

def _session_thumb(session: dict) -> bytes | str | None:
    if not session.get("files"):
        return None
    fp  = Path(session["files"][0]["path"])
    ext = fp.suffix.lower()
    if not fp.exists():
        return None
    if ext in {".jpg", ".jpeg", ".png"}:
        return str(fp)
    if ext in VIDEO_EXTS:
        thumb = video_thumbnail(fp)
        return pil_to_png_bytes(thumb) if thumb else None
    return None


def _completion_badge(session: dict) -> str:
    missing = validate_session(session)
    return "✅ 信息完整" if not missing else f"⚠️ 待补充：{'、'.join(missing)}"


# ─── 卡片 ────────────────────────────────────────────────────────────────────────

def _render_card(
    col, session: dict, state_key: str, score: float | None = None
) -> None:
    sid     = session["session_id"]
    is_sel  = st.session_state.get(state_key) == sid
    thumb   = _session_thumb(session)
    n_files = len(session.get("files", []))
    n_cmts  = len([c for c in session.get("comments", []) if isinstance(c, dict)])

    with col:
        if thumb:
            st.image(thumb, use_container_width=True)
        elif session.get("source_type") == "text":
            st.markdown("📄 **文本记录**")
            try:
                fp = Path(session["files"][0]["path"])
                st.caption(fp.read_text(encoding="utf-8")[:50].replace("\n", " ") + "…")
            except OSError:
                pass
        else:
            st.markdown("📎 **文件记录**")

        if n_files > 1:
            st.caption(f"📎 共 {n_files} 个文件")
        if n_cmts:
            st.caption(f"💬 {n_cmts} 条评论")
        if score is not None:
            st.caption(f"🎯 相似度 {score:.0%}")
        st.caption(f"🕐 {session.get('upload_time', '')}")
        st.caption(_completion_badge(session))
        tags = session.get("tags", [])
        if tags:
            st.caption("🏷️ " + "  ".join(tags))

        label = "✅ 已选" if is_sel else "🔍 查看 / 编辑"
        if st.button(label, key=f"{state_key}_btn_{sid}", use_container_width=True):
            st.session_state[state_key] = None if is_sel else sid
            st.rerun()


def _render_batch_row(session: dict, selected_key: str = "batch_selected_ids") -> None:
    sid      = session["session_id"]
    safe_sid = "".join(c if c.isalnum() else "_" for c in sid)
    selected: set = st.session_state.get(selected_key, set())

    cols = st.columns([0.5, 1, 5, 3])
    with cols[0]:
        checked = st.checkbox(
            "",
            value=sid in selected,
            key=f"bchk_{safe_sid}",
            label_visibility="collapsed",
        )
        if checked and sid not in selected:
            selected.add(sid)
            st.session_state[selected_key] = selected
            st.rerun()
        elif not checked and sid in selected:
            selected.discard(sid)
            st.session_state[selected_key] = selected
            st.rerun()
    with cols[1]:
        thumb = _session_thumb(session)
        if isinstance(thumb, str) and Path(thumb).exists():
            st.image(thumb, width=60)
        elif isinstance(thumb, bytes):
            st.image(thumb, width=60)
    with cols[2]:
        desc = (session.get("description") or "（无描述）")[:80]
        st.markdown(f"**{desc}**")
        st.caption(session.get("upload_time", ""))
    with cols[3]:
        tags = session.get("tags", [])
        st.caption(" · ".join(tags[:5]) if tags else "无标签")


# ─── 评论区 ──────────────────────────────────────────────────────────────────────

def _render_comments(session: dict) -> None:
    sid       = session["session_id"]
    comments  = [c for c in session.get("comments", []) if isinstance(c, dict)]
    input_key = f"new_cmt_{sid}"

    st.markdown("#### 💬 评论区")

    if comments:
        for c in comments:
            col_text, col_del = st.columns([11, 1])
            with col_text:
                st.markdown(
                    f"<small style='color:gray'>{c.get('created_at', '')}</small>  \n"
                    f"{c.get('text', '')}",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("🗑️", key=f"del_cmt_{c['id']}", help="删除此评论"):
                    delete_comment(sid, c["id"])
                    st.rerun()
        st.divider()
    else:
        st.caption("暂无评论，发表第一条吧～")

    new_text = st.text_area(
        "发表评论",
        placeholder="写点什么……",
        height=80,
        key=input_key,
        label_visibility="collapsed",
    )
    if st.button("发送评论", key=f"send_cmt_{sid}"):
        if new_text.strip():
            add_comment(sid, new_text)
            if input_key in st.session_state:
                del st.session_state[input_key]
            st.rerun()
        else:
            st.warning("评论内容不能为空")


# ─── AI 摘要 ──────────────────────────────────────────────────────────────────────

def _render_ai_summary(session: dict) -> None:
    """AI 摘要面板（仅 final 记录展示）。"""
    model_id = st.session_state.get("llm_selected_model") or ""
    cache_key = f"_story_{session['session_id']}"

    cached = st.session_state.get(cache_key)
    with st.expander("✨ AI 摘要", expanded=bool(cached)):
        if not model_id:
            st.caption("请先在「搜索」Tab 选择模型，即可生成此记忆的文学化摘要。")
            return
        if cached:
            st.markdown(cached)
            if st.button("🔄 重新生成", key=f"regen_story_{session['session_id']}"):
                del st.session_state[cache_key]
                st.rerun()
        else:
            if st.button(
                "✨ 生成 AI 摘要", key=f"gen_story_{session['session_id']}", type="primary"
            ):
                from skills.story_skill import StorySkill
                with st.spinner("生成中…"):
                    result = StorySkill().run(session, model_id=model_id)
                if result.success:
                    st.session_state[cache_key] = result.data["story"]
                    st.rerun()
                else:
                    st.error(f"生成失败：{result.error}")


# ─── 详情 + 编辑表单 ──────────────────────────────────────────────────────────────

def _render_detail(
    session: dict, mode: str, state_key: str | None = None
) -> None:
    sid = session["session_id"]
    if state_key is None:
        state_key = "pending_selected" if mode == "pending" else "archived_selected"
    title   = session["files"][0]["original_name"] if session["files"] else "记录"
    is_text = _is_text_session(session)

    heading = "编辑待处理记录" if mode == "pending" else "编辑已归档记录"
    st.subheader(f"📝 {heading}：{title}")

    time_info = f"上传时间：{session.get('upload_time', '')}"
    if mode == "final" and session.get("archive_time"):
        time_info += f"  ·  归档时间：{session['archive_time']}"
    st.caption(time_info)

    missing_now = validate_session(session)
    if missing_now and mode == "pending":
        st.warning(f"⚠️ 以下必填项尚未填写：**{'、'.join(missing_now)}**")
    elif not missing_now:
        st.success("✅ 所有必填项已完整")

    with st.expander(f"查看文件（{len(session.get('files', []))} 个）", expanded=False):
        for fe in session.get("files", []):
            fp  = Path(fe["path"])
            ext = fp.suffix.lower()
            st.markdown(f"**{fe['original_name']}**")
            if not fp.exists():
                st.warning("文件不存在")
                continue
            if ext in {".jpg", ".jpeg", ".png"}:
                st.image(str(fp), use_container_width=True)
            elif ext in VIDEO_EXTS_PLAYABLE:
                st.video(str(fp))
            elif ext in VIDEO_EXTS:
                size_mb = fp.stat().st_size / 1024 / 1024
                st.info(
                    f"🎬 {fe['original_name']}（{size_mb:.1f} MB）\n\n"
                    "该格式浏览器不支持直接播放，请用本地播放器打开文件。"
                )
                with open(fp, "rb") as fh:
                    st.download_button(
                        "⬇️ 下载文件",
                        data=fh,
                        file_name=fe["original_name"],
                        key=f"dl_{fe['filename']}",
                    )
            else:
                try:
                    st.text_area(
                        "内容预览",
                        fp.read_text(encoding="utf-8"),
                        height=150,
                        disabled=True,
                        key=f"prev_{fe['filename']}",
                    )
                except OSError:
                    st.warning("无法读取文件内容")

    if mode == "final" and session.get("edit_history"):
        with st.expander(f"编辑历史（{len(session['edit_history'])} 次）"):
            for edit in reversed(session["edit_history"]):
                st.markdown(f"**{edit['edited_at']}**")
                for fk, change in edit["changes"].items():
                    lbl = next((f["label"] for f in FIELD_SCHEMA if f["key"] == fk), fk)
                    st.markdown(f"- **{lbl}**：「{change['from']}」→「{change['to']}」")
                st.divider()

    safe_sid         = "".join(c if c.isalnum() else "_" for c in sid)
    edit_prefix      = f"edit_{safe_sid}"
    skip_keys        = {"description"} if is_text else set()
    ai_picker_key    = f"ai_tags_{sid}"
    tags_widget_key  = f"tags_{safe_sid}"
    # AI 标签组件应用过来的标签（点击「应用到标签栏」后写入）
    ai_applied_tags  = st.session_state.get(f"_ai_applied_tags_{ai_picker_key}", [])

    text_file_path    = None
    current_text_body = ""
    if is_text and session.get("files"):
        text_file_path = Path(session["files"][0]["path"])
        try:
            current_text_body = text_file_path.read_text(encoding="utf-8")
        except OSError:
            current_text_body = str(session.get("description", ""))

    model_id = st.session_state.get("llm_selected_model") or ""
    fill_state_key = f"fill_{safe_sid}"
    fill_session = {
        **session,
        "description": current_text_body if is_text else session.get("description", ""),
    }
    render_ai_fill_picker(
        session_data=fill_session,
        model_id=model_id,
        state_key=fill_state_key,
        form_prefix=edit_prefix,
    )

    with st.form(f"form_{safe_sid}"):
        st.markdown("#### ✏️ 编辑字段")

        if is_text:
            st.markdown("**📝 文本内容**（可直接编辑，保存后同步写入文件）")
            text_body = st.text_area(
                "文本内容",
                value=current_text_body,
                height=300,
                key=f"text_body_{safe_sid}",
                label_visibility="collapsed",
            )
        else:
            text_body = ""

        field_values = render_field_inputs(edit_prefix, defaults=session, skip_keys=skip_keys)
        if is_text:
            field_values["description"] = text_body

        st.divider()
        st.markdown("**🏷️ 标签**（可多选，不计入编辑历史）")
        all_tags     = get_tags_registry()
        # AI 新生成的标签（不在注册表中）也作为可选项临时加入
        ai_new_tags  = [t for t in ai_applied_tags if t not in all_tags]
        extra_tags   = [t for t in session.get("tags", []) if t not in all_tags]
        tag_options  = all_tags + extra_tags + ai_new_tags
        # 合并现有标签 + AI 应用标签作为默认勾选
        merged_default = list(dict.fromkeys(
            [t for t in session.get("tags", []) if t in tag_options] +
            [t for t in ai_applied_tags if t in tag_options]
        ))
        selected_tags = st.multiselect(
            "标签",
            options=tag_options,
            default=merged_default,
            key=tags_widget_key,
            label_visibility="collapsed",
        )
        if ai_applied_tags:
            st.caption("💡 已含 AI 推荐标签，保存时新标签将自动注册到标签库。")

        groups = get_groups()
        if groups:
            st.markdown("**📁 所属分组**")
            group_map    = {g["id"]: g["name"] for g in groups}
            current_gids = [gid for gid in session.get("group_ids", []) if gid in group_map]
            selected_gids = st.multiselect(
                "分组",
                options=list(group_map.keys()),
                default=current_gids,
                format_func=lambda gid: group_map.get(gid, gid),
                key=f"groups_{safe_sid}",
                label_visibility="collapsed",
            )
        else:
            selected_gids = session.get("group_ids", [])

        st.divider()

        if mode == "pending":
            c1, c2, c3 = st.columns(3)
            with c1:
                do_save    = st.form_submit_button("💾 保存更改", use_container_width=True)
            with c2:
                do_archive = st.form_submit_button(
                    "✅ 完成并归档", type="primary", use_container_width=True
                )
            with c3:
                do_cancel  = st.form_submit_button("取消", use_container_width=True)
        else:
            c1, c2 = st.columns([3, 1])
            with c1:
                do_save   = st.form_submit_button(
                    "💾 保存更改", type="primary", use_container_width=True
                )
            with c2:
                do_cancel = st.form_submit_button("取消", use_container_width=True)
            do_archive = False

    if do_cancel:
        st.session_state[state_key] = None
        st.rerun()

    if do_save:
        if is_text and text_file_path:
            try:
                text_file_path.write_text(text_body, encoding="utf-8")
            except OSError as e:
                st.error(f"文件写入失败：{e}")
        # 将 AI 新生成、不在注册表中的标签自动注册
        existing_reg = get_tags_registry()
        for t in selected_tags:
            if t not in existing_reg:
                add_tag(t)
        field_values["tags"]      = selected_tags
        field_values["group_ids"] = selected_gids
        update_session_fields(sid, field_values)
        st.session_state[state_key] = sid
        st.rerun()

    if do_archive:
        merged  = {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
        missing = validate_session(merged)
        if missing:
            st.error(f"❌ 以下必填项仍未填写：**{'、'.join(missing)}**，请补充后再归档。")
        else:
            if is_text and text_file_path:
                try:
                    text_file_path.write_text(text_body, encoding="utf-8")
                except OSError as e:
                    st.error(f"文件写入失败：{e}")
                    st.stop()
            existing_reg = get_tags_registry()
            for t in selected_tags:
                if t not in existing_reg:
                    add_tag(t)
            field_values["tags"]      = selected_tags
            field_values["group_ids"] = selected_gids
            update_session_fields(sid, field_values)
            move_to_final(sid)
            st.session_state[state_key] = None
            st.rerun()

    st.divider()
    if st.button("🗑️ 移入回收站", key=f"delete_btn_{safe_sid}", type="secondary"):
        soft_delete_session(sid)
        st.session_state[state_key] = None
        st.rerun()

    render_ai_tag_picker(
        session_data=session,
        model_id=model_id,
        state_key=ai_picker_key,
        apply_key=tags_widget_key,
    )
    if mode == "final":
        _render_ai_summary(session)

    st.divider()
    _render_comments(session)


# ─── 标签 / 分组 管理面板 ────────────────────────────────────────────────────────

def _render_tag_manager() -> None:
    tags = get_tags_registry()
    for tag in tags:
        c_name, c_del = st.columns([5, 1])
        with c_name:
            st.markdown(f"🏷️ {tag}")
        with c_del:
            if tag in DEFAULT_TAGS:
                st.caption("默认")
            elif st.button("🗑️", key=f"del_tag_{tag}", help=f"删除「{tag}」"):
                remove_tag(tag)
                st.rerun()
    st.divider()
    new_tag = st.text_input("新标签名", key="new_tag_input", placeholder="输入后点添加")
    if st.button("➕ 添加标签", key="add_tag_btn"):
        if new_tag.strip():
            add_tag(new_tag)
            if "new_tag_input" in st.session_state:
                del st.session_state["new_tag_input"]
            st.rerun()
        else:
            st.warning("标签名不能为空")


def _render_group_manager() -> None:
    groups = get_groups()
    if groups:
        for g in groups:
            c_name, c_del = st.columns([5, 1])
            with c_name:
                st.markdown(f"📁 **{g['name']}**")
                st.caption(g.get("created_at", ""))
            with c_del:
                if st.button("🗑️", key=f"del_grp_{g['id']}", help=f"删除「{g['name']}」"):
                    delete_group(g["id"])
                    if st.session_state.get("archived_group_filter") == g["id"]:
                        st.session_state["archived_group_filter"] = None
                    st.rerun()
        st.divider()
    else:
        st.caption("暂无分组")
        st.divider()
    new_grp = st.text_input("新分组名", key="new_group_input", placeholder="输入后点创建")
    if st.button("➕ 创建分组", key="create_group_btn"):
        if new_grp.strip():
            create_group(new_grp)
            if "new_group_input" in st.session_state:
                del st.session_state["new_group_input"]
            st.rerun()
        else:
            st.warning("分组名不能为空")
