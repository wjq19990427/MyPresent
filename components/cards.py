"""共用 UI 组件：卡片、详情面板、评论区、标签/分组管理。"""
from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

import streamlit as st

from core.constants import (
    COLS, FIELD_SCHEMA, IMAGE_EXTS, TEXT_EXTS,
    VIDEO_EXTS, VIDEO_EXTS_PLAYABLE,
)
from core.db_manager import (
    get_groups,
    add_label, remove_label, create_group, delete_group,
    get_label_registry,
    validate_session,
    update_session_fields, update_session_tags, add_comment, delete_comment,
    soft_delete_session,
    _is_text_session,
)
from core.file_io import move_to_final
from core.media import video_thumbnail, pil_to_png_bytes
from components.forms import render_field_inputs
from components.ai_analysis import render_session_ai_analysis


_STRUCTURED_LABEL_TYPES = {
    "domains": "domain",
    "attributes": "attribute",
    "topics": "topic",
    "emotion_tags": "emotion",
}
_STRUCTURED_LABELS = {
    "domains": "领域",
    "attributes": "视角",
    "topics": "话题",
    "emotion_tags": "情绪",
}
_CARD_LABEL_COLORS = {
    "domains": ("#eff6ff", "#1d4ed8", "#bfdbfe"),
    "attributes": ("#f0fdf4", "#15803d", "#bbf7d0"),
    "topics": ("#fff7ed", "#c2410c", "#fed7aa"),
}
_RECORD_TYPE_BADGES = {
    "text": "📝 纯文本",
    "image": "📷 图片",
    "video": "🎬 视频",
    "mixed": "🧩 混合",
    "file": "📎 文件",
}


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
    sid = session["session_id"]
    is_sel = st.session_state.get(state_key) == sid
    thumb = _session_thumb(session)
    n_files = len(session.get("files", []))
    n_cmts = len([c for c in session.get("comments", []) if isinstance(c, dict)])
    record_type = _infer_record_type(session)
    title = _card_title(session)
    content_time = str(session.get("content_time") or "").strip()

    with col:
        if thumb:
            st.image(thumb, use_container_width=True)
        elif record_type == "text":
            st.markdown("📝 **文本记录**")
            try:
                fp = Path(session["files"][0]["path"])
                st.caption(fp.read_text(encoding="utf-8")[:50].replace("\n", " ") + "…")
            except (IndexError, KeyError, OSError):
                pass
        else:
            st.markdown("📄 **文件记录**")

        c_title, c_type = st.columns([4, 1.4])
        with c_title:
            st.markdown(f"**{escape(title)}**")
        with c_type:
            st.markdown(_record_type_badge(record_type), unsafe_allow_html=True)

        if content_time:
            st.caption(f"记录时间：{content_time}")
        if n_files > 1:
            st.caption(f"📎 {n_files} 个文件")
        if n_cmts:
            st.caption(f"💬 {n_cmts} 条评论")
        if score is not None:
            st.caption(f"🎯 相似度 {score:.0%}")

        badges = _structured_card_badges(session)
        if badges:
            st.markdown(badges, unsafe_allow_html=True)

        label = "✅ 已选" if is_sel else "🔍 查看 / 编辑"
        if st.button(label, key=f"{state_key}_btn_{sid}", use_container_width=True):
            st.session_state[state_key] = None if is_sel else sid
            st.rerun()


def _infer_record_type(session: dict) -> str:
    files = session.get("files") or []
    if session.get("source_type") == "text":
        return "text"
    if not files:
        source_type = str(session.get("source_type") or "").lower()
        return source_type if source_type in _RECORD_TYPE_BADGES else "file"

    types = []
    for file_entry in files:
        ext = Path(
            str(file_entry.get("filename") or file_entry.get("path") or "")
        ).suffix.lower()
        if ext in TEXT_EXTS:
            types.append("text")
        elif ext in IMAGE_EXTS:
            types.append("image")
        elif ext in VIDEO_EXTS:
            types.append("video")
        else:
            types.append("file")

    non_file_types = [item for item in types if item != "file"]
    if non_file_types and len(set(non_file_types)) > 1:
        return "mixed"
    if non_file_types:
        return Counter(non_file_types).most_common(1)[0][0]
    return "file"


def _card_title(session: dict) -> str:
    title = str(session.get("title") or "").strip()
    if title:
        return title
    description = str(session.get("description") or "").strip().replace("\n", " ")
    if description:
        return description[:30] + ("…" if len(description) > 30 else "")
    return "（未命名）"


def _record_type_badge(record_type: str) -> str:
    text = escape(_RECORD_TYPE_BADGES.get(record_type, _RECORD_TYPE_BADGES["file"]))
    return (
        "<span style='display:inline-block;padding:2px 7px;border-radius:999px;"
        "font-size:12px;line-height:1.6;background:#f3f4f6;color:#374151;"
        f"border:1px solid #e5e7eb;white-space:nowrap;'>{text}</span>"
    )


def _structured_card_badges(session: dict) -> str:
    items: list[tuple[str, str]] = []
    for field in ("domains", "attributes", "topics"):
        items.extend((field, value) for value in _clean_list(session.get(field, [])))

    visible = items[:6]
    hidden_count = max(0, len(items) - len(visible))
    badges = [_label_badge(field, value) for field, value in visible]
    if hidden_count:
        badges.append(_count_badge(hidden_count))
    return " ".join(badges)


def _label_badge(field: str, value: str) -> str:
    bg, fg, border = _CARD_LABEL_COLORS[field]
    return (
        "<span style='display:inline-block;margin:2px 4px 2px 0;padding:2px 7px;"
        "border-radius:999px;font-size:12px;line-height:1.6;"
        f"background:{bg};color:{fg};border:1px solid {border};'>"
        f"{escape(value)}</span>"
    )


def _count_badge(count: int) -> str:
    return (
        "<span style='display:inline-block;margin:2px 4px 2px 0;padding:2px 7px;"
        "border-radius:999px;font-size:12px;line-height:1.6;"
        "background:#f3f4f6;color:#4b5563;border:1px solid #e5e7eb;'>"
        f"+{count}</span>"
    )


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

    text_file_path    = None
    current_text_body = ""
    if is_text and session.get("files"):
        text_file_path = Path(session["files"][0]["path"])
        try:
            current_text_body = text_file_path.read_text(encoding="utf-8")
        except OSError:
            current_text_body = str(session.get("description", ""))

    model_id = st.session_state.get("llm_selected_model") or ""
    analysis_session = {
        **session,
        "description": current_text_body if is_text else session.get("description", ""),
    }
    analysis_result = render_session_ai_analysis(
        analysis_session,
        model_id=model_id,
        state_key=f"detail_{safe_sid}",
    )
    if analysis_result:
        _apply_analysis_to_detail_form(analysis_result, edit_prefix, safe_sid)

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

    st.session_state.setdefault(f"{safe_sid}_summary", str(session.get("summary", "")))
    field_values["summary"] = st.text_area(
        "摘要",
        key=f"{safe_sid}_summary",
        height=90,
    )
    structured_values = _render_structured_detail_fields(session, safe_sid)

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
            do_save = st.button("💾 保存更改", key=f"save_{safe_sid}", use_container_width=True)
        with c2:
            do_archive = st.button(
                "✅ 完成并归档", key=f"archive_{safe_sid}", type="primary",
                use_container_width=True,
            )
        with c3:
            do_cancel = st.button("取消", key=f"cancel_{safe_sid}", use_container_width=True)
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            do_save = st.button(
                "💾 保存更改", key=f"save_{safe_sid}", type="primary",
                use_container_width=True,
            )
        with c2:
            do_cancel = st.button("取消", key=f"cancel_{safe_sid}", use_container_width=True)
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
        topics = _clean_list(structured_values.get("topics", []))
        field_values["group_ids"] = selected_gids
        field_values.update(structured_values)
        update_session_fields(sid, field_values)
        update_session_tags(sid, topics)
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
            topics = _clean_list(structured_values.get("topics", []))
            field_values["group_ids"] = selected_gids
            field_values.update(structured_values)
            update_session_fields(sid, field_values)
            update_session_tags(sid, topics)
            move_to_final(sid)
            st.session_state[state_key] = None
            st.rerun()

    st.divider()
    if st.button("🗑️ 移入回收站", key=f"delete_btn_{safe_sid}", type="secondary"):
        soft_delete_session(sid)
        st.session_state[state_key] = None
        st.rerun()

    st.divider()
    _render_comments(session)


def _apply_analysis_to_detail_form(
    result: dict, edit_prefix: str, safe_sid: str
) -> None:
    for key in ("title", "feeling", "reason"):
        if key in result:
            st.session_state[f"{edit_prefix}_{key}"] = result.get(key, "")
    if "summary" in result:
        st.session_state[f"{safe_sid}_summary"] = str(result.get("summary") or "")

    for key in ("domains", "attributes", "topics", "emotion_tags"):
        values = _clean_list(result.get(key, []))
        if key == "topics":
            values = list(
                dict.fromkeys([*values, *_clean_list(result.get("new_topics", []))])
            )
        st.session_state[f"{safe_sid}_{key}"] = values
        _register_structured_labels(key, values)

    if "emotion_note" in result:
        st.session_state[f"{safe_sid}_emotion_note"] = str(
            result.get("emotion_note") or ""
        )
    st.rerun()


def _render_structured_detail_fields(session: dict, safe_sid: str) -> dict:
    st.markdown("### 🧩 结构化标签")
    st.caption("AI 分析会填入这些字段，也可手动调整。")
    values = {}
    for field, label in _STRUCTURED_LABELS.items():
        state_key = f"{safe_sid}_{field}"
        st.session_state.setdefault(state_key, _clean_list(session.get(field, [])))
        options = _structured_options(field, session)
        values[field] = st.multiselect(
            label,
            options=options,
            key=state_key,
        )
    st.session_state.setdefault(
        f"{safe_sid}_emotion_note", str(session.get("emotion_note", ""))
    )
    values["emotion_note"] = st.text_area(
        "情绪描述",
        key=f"{safe_sid}_emotion_note",
        height=90,
    )
    return values


def _structured_options(field: str, session: dict) -> list[str]:
    label_type = _STRUCTURED_LABEL_TYPES[field]
    registry = [item["name"] for item in get_label_registry(label_type)]
    current = _clean_list(session.get(field, []))
    state_values = _clean_list(
        st.session_state.get(f"{session_state_safe_id(session)}_{field}", [])
    )
    return list(dict.fromkeys([*registry, *current, *state_values]))


def session_state_safe_id(session: dict) -> str:
    sid = str(session.get("session_id", ""))
    return "".join(c if c.isalnum() else "_" for c in sid)


def _clean_list(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]


def _register_structured_labels(field: str, values: list[str]) -> None:
    label_type = _STRUCTURED_LABEL_TYPES.get(field)
    if not label_type:
        return
    for value in values:
        add_label(value, label_type)


# ─── 标签 / 分组 管理面板 ────────────────────────────────────────────────────────

def _render_label_manager() -> None:
    tabs = st.tabs(["领域", "视角", "话题", "情绪"])
    for tab, (field, label) in zip(tabs, _STRUCTURED_LABELS.items()):
        label_type = _STRUCTURED_LABEL_TYPES[field]
        with tab:
            labels = get_label_registry(label_type)
            if labels:
                for item in labels:
                    name = item["name"]
                    c_name, c_del = st.columns([5, 1])
                    with c_name:
                        st.markdown(f"🏷️ {name}")
                    with c_del:
                        if item.get("is_system"):
                            st.caption("🔒 系统")
                        elif st.button(
                            "🗑️",
                            key=f"del_label_{label_type}_{name}",
                            help=f"删除「{name}」",
                        ):
                            remove_label(name, label_type)
                            st.rerun()
                st.divider()
            else:
                st.caption(f"暂无{label}")
                st.divider()

            input_key = f"new_label_input_{label_type}"
            new_label = st.text_input(
                f"新{label}标签名",
                key=input_key,
                placeholder="输入后点添加",
            )
            if st.button(f"➕ 添加{label}", key=f"add_label_btn_{label_type}"):
                if new_label.strip():
                    add_label(new_label, label_type)
                    if input_key in st.session_state:
                        del st.session_state[input_key]
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
