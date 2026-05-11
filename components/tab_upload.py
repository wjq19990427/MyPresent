"""记录台 Tab — 文件上传 / 粘贴文字 / 文件夹导入。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.constants import TEXT_EXTS, SUPPORTED_IMPORT_EXTS, FIELD_SCHEMA
from core.db_manager import (
    add_label,
    get_label_registry,
    validate_session,
)
from core.file_io import save_session_pending, save_session_final, import_folder_to_pending
from components.forms import render_field_inputs
from components.ai_analysis import render_ai_analysis


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


def _pasted_filename(text: str) -> str:
    first = text.strip().split("\n")[0][:20].strip()
    safe  = "".join(c for c in first if c not in r'\/:*?"<>|').strip()
    return f"{safe}.txt" if safe else "paste.txt"


def _pick_folder_dialog() -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    folder = filedialog.askdirectory(title="选择导入文件夹")
    root.destroy()
    return folder or ""


def _get_uploaded_filenames() -> set[str]:
    """返回 data/pending/ 和 data/final/ 中已存储文件的原始文件名集合。"""
    import re
    from core.constants import PENDING_DIR, FINAL_DIR
    result: set[str] = set()
    for d in (PENDING_DIR, FINAL_DIR):
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            m = re.search(r"_\d{3}_(.+)$", f.name)
            if m:
                result.add(m.group(1))
    return result


def _build_upload_draft(description: str) -> dict:
    draft = {"description": description}
    for field in FIELD_SCHEMA:
        key = field["key"]
        if key == "description":
            continue
        if field["type"] == "date_or_text":
            text_key = f"upload_{key}_text"
            date_key = f"upload_{key}_date"
            text_value = str(st.session_state.get(text_key, "")).strip()
            draft[key] = text_value or str(st.session_state.get(date_key, "") or "")
        else:
            draft[key] = st.session_state.get(f"upload_{key}", "")
    return draft


def _apply_analysis_to_upload_form(result: dict) -> None:
    for key in ("title", "summary", "feeling", "reason"):
        if key in result:
            st.session_state[f"upload_{key}"] = result.get(key, "")

    for key in ("domains", "attributes", "topics", "emotion_tags"):
        values = _clean_list(result.get(key, []))
        if key == "topics":
            values = list(dict.fromkeys([*values, *_clean_list(result.get("new_topics", []))]))
        st.session_state[f"upload_{key}"] = values

    if "emotion_note" in result:
        st.session_state["upload_emotion_note"] = str(result.get("emotion_note") or "")

    st.rerun()


def _clean_list(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]


def _persist_new_structured_labels(field: str, values: list[str]) -> None:
    label_type = _STRUCTURED_LABEL_TYPES.get(field)
    if not label_type:
        return
    existing = {item["name"] for item in get_label_registry(label_type)}
    for value in values:
        if value not in existing:
            add_label(value, label_type)
            existing.add(value)


def _persist_selected_structured_labels(values: dict) -> None:
    for field in _STRUCTURED_LABEL_TYPES:
        _persist_new_structured_labels(field, _clean_list(values.get(field, [])))


def _render_structured_analysis_fields() -> dict:
    st.markdown("### 🧩 结构化标签")
    st.caption("AI 分析会填入这些字段，也可手动调整。")
    values = {}
    for field, label in _STRUCTURED_LABELS.items():
        st.session_state.setdefault(f"upload_{field}", [])
        options = _structured_options(field)
        values[field] = st.multiselect(label, options=options, key=f"upload_{field}")
    st.session_state.setdefault("upload_emotion_note", "")
    emotion_note = st.text_area("情绪描述", key="upload_emotion_note", height=90)
    return {
        **values,
        "emotion_note": emotion_note,
    }


def _structured_options(field: str) -> list[str]:
    label_type = _STRUCTURED_LABEL_TYPES[field]
    registry = [item["name"] for item in get_label_registry(label_type)]
    current = _clean_list(st.session_state.get(f"upload_{field}", []))
    return list(dict.fromkeys([*registry, *current]))


def _consume_upload_prefill() -> tuple[bool, list[str]]:
    prefill = st.session_state.get("upload_prefill")
    if not isinstance(prefill, dict):
        return False, []

    description = str(prefill.get("description") or "")
    topics = [
        str(topic).strip()
        for topic in (prefill.get("topics") or [])
        if str(topic).strip()
    ]
    st.session_state["source_mode"] = "📝 粘贴文字"
    paste_key = f"paste_{st.session_state.upload_key}"
    st.session_state[paste_key] = description
    st.session_state["upload_prefill"] = None
    return prefill.get("source") == "planning", topics


def _render_folder_import() -> None:
    done = st.session_state.get("folder_import_done", 0)
    if done:
        st.success(f"✅ 已成功导入 **{done}** 条记录到待处理！")
        st.session_state["folder_import_done"] = 0

    folder_str: str = st.session_state.get("folder_selected_path", "")
    col_pick, col_disp = st.columns([1, 3])
    with col_pick:
        if st.button("📂 选择文件夹", key="pick_folder_btn"):
            picked = _pick_folder_dialog()
            if picked:
                st.session_state["folder_selected_path"] = picked
                st.session_state["folder_scan_results"]  = []
                st.rerun()
    with col_disp:
        if folder_str:
            st.caption(f"已选：`{folder_str}`")
        else:
            st.caption("请点击左侧按钮选择文件夹")

    c_scan, c_mode = st.columns([1, 2])
    with c_scan:
        do_scan = st.button(
            "🔍 扫描文件夹",
            type="primary",
            key="scan_folder_btn",
            disabled=not folder_str,
        )
    with c_mode:
        import_mode = st.radio(
            "导入方式",
            ["每个文件独立记录", "所有文件合并一条记录"],
            horizontal=True,
            key="folder_import_mode",
        )

    if do_scan:
        folder = Path(folder_str)
        if not folder.is_dir():
            st.error("该路径不是文件夹")
        else:
            found = sorted(
                [f for f in folder.rglob("*")
                 if f.is_file() and f.suffix.lower() in SUPPORTED_IMPORT_EXTS],
                key=lambda p: p.name,
            )
            uploaded  = _get_uploaded_filenames()
            filtered  = [f for f in found if f.name not in uploaded]
            skipped_n = len(found) - len(filtered)
            st.session_state["folder_scan_results"]   = [str(f) for f in filtered]
            st.session_state["folder_scan_skipped_n"] = skipped_n

    scan_results: list[str] = st.session_state.get("folder_scan_results", [])
    if not scan_results:
        if st.session_state.get("folder_scan_skipped_n", 0):
            st.caption("该文件夹内所有文件均已上传")
            return
        st.caption("支持格式：图片（jpg/png/gif/webp/bmp）、视频（mp4/mov/avi 等）、文本（txt/md）")
        return

    skipped_n = st.session_state.get("folder_scan_skipped_n", 0)
    if skipped_n:
        st.caption(f"⚠️ 已自动跳过 **{skipped_n}** 个文件名与已上传记录重复的文件")
    st.markdown(f"扫描到 **{len(scan_results)}** 个支持格式的文件，请勾选要导入的内容：")

    file_names     = [Path(p).name for p in scan_results]
    selected_names = st.multiselect(
        "选择文件",
        options=file_names,
        default=file_names,
        key="folder_file_select",
        label_visibility="collapsed",
    )

    selected_paths = [Path(p) for p in scan_results if Path(p).name in selected_names]
    if selected_paths:
        total_mb = sum(p.stat().st_size for p in selected_paths if p.exists()) / 1024 / 1024
        as_one   = import_mode == "所有文件合并一条记录"
        n_sess   = 1 if as_one else len(selected_paths)
        st.caption(
            f"已选 **{len(selected_paths)}** 个文件，共约 {total_mb:.1f} MB"
            f" → 将创建 **{n_sess}** 条待处理记录"
        )

        if st.button("📥 导入到待处理", type="primary", key="do_import_btn"):
            with st.spinner(f"正在导入 {len(selected_paths)} 个文件…"):
                count = import_folder_to_pending(selected_paths, as_one_session=as_one)
            st.session_state["folder_scan_results"] = []
            st.session_state["folder_import_done"]  = count
            st.rerun()
    else:
        st.info("请至少选择一个文件")

    if st.button("清除扫描结果", key="clear_scan_btn"):
        st.session_state["folder_scan_results"] = []
        st.session_state["folder_scan_skipped_n"] = 0
        st.rerun()


def render_upload_tab() -> None:
    show_planning_prefill, prefill_topics = _consume_upload_prefill()

    if show_planning_prefill:
        st.info("✍️ 已从今日规划预填内容，可继续扩充")

    source_mode = st.radio(
        "上传方式",
        ["📁 上传文件", "📝 粘贴文字", "📂 导入文件夹"],
        horizontal=True,
        key="source_mode",
    )

    if source_mode == "📂 导入文件夹":
        _render_folder_import()
        return

    files: list      = []
    pasted_text      = ""
    is_text_content  = False
    auto_description = ""

    if source_mode == "📁 上传文件":
        files = st.file_uploader(
            "支持图片、各种格式视频、文本（可多选，本次上传构成一条记录）",
            type=["jpg", "jpeg", "png",
                  "mp4", "mov", "avi", "mkv", "wmv", "webm",
                  "flv", "m4v", "3gp", "ts", "mts", "mpg", "mpeg",
                  "md", "txt"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.upload_key}",
        ) or []
        content_ready = bool(files)
        if files and all(Path(f.name).suffix.lower() in TEXT_EXTS for f in files):
            is_text_content = True
            try:
                auto_description = files[0].getvalue().decode("utf-8")
            except Exception:
                auto_description = ""
    else:
        pasted_text = st.text_area(
            "在此粘贴或输入文字",
            placeholder="将文字内容粘贴到此处……",
            height=200,
            key=f"paste_{st.session_state.upload_key}",
        ) or ""
        content_ready    = bool(pasted_text.strip())
        is_text_content  = True
        auto_description = pasted_text

    if not content_ready:
        st.info("请先提供内容（上传文件 或 粘贴文字）")
        return

    if source_mode == "📁 上传文件":
        st.write(f"已选 **{len(files)}** 个文件，本次作为**一条记录**保存")
        if is_text_content:
            st.info("📝 纯文本文件，描述将自动使用文件内容填充")
    else:
        st.caption(f"文字长度：{len(pasted_text)} 字符")
    st.caption("⏱️ 上传时间将在保存时自动记录")
    st.divider()

    skip = {"description"} if is_text_content else set()

    model_id = st.session_state.get("llm_selected_model") or ""
    draft_for_ai = _build_upload_draft(auto_description)
    analysis_result = render_ai_analysis(
        draft=draft_for_ai,
        model_id=model_id,
        state_key=f"upload_{st.session_state.upload_key}",
    )
    if analysis_result:
        _apply_analysis_to_upload_form(analysis_result)

    if prefill_topics:
        current_topics = st.session_state.get("upload_topics", [])
        st.session_state["upload_topics"] = list(
            dict.fromkeys([*current_topics, *prefill_topics])
        )

    with st.form("upload_meta_form"):
        st.markdown("### 必填信息")
        if is_text_content:
            st.caption("描述已自动使用内容填充，无需手动填写")
        field_values = render_field_inputs("upload", skip_keys=skip)
        if is_text_content:
            field_values["description"] = auto_description
        st.divider()
        structured_values = _render_structured_analysis_fields()
        st.divider()
        st.markdown("### 摘要")
        st.session_state.setdefault("upload_summary", "")
        structured_values["summary"] = st.text_area(
            "摘要",
            key="upload_summary",
            height=90,
        )
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            do_archive = st.form_submit_button(
                "完成并归档", type="primary", use_container_width=True
            )
        with c2:
            do_pending = st.form_submit_button(
                "暂存到待处理", use_container_width=True
            )

    if source_mode == "📁 上传文件":
        file_data = [(f, f.name) for f in files]
        src_type  = "file"
    else:
        file_data = [(pasted_text.encode("utf-8"), _pasted_filename(pasted_text))]
        src_type  = "text"

    if do_archive:
        missing = validate_session(
            {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
        )
        if missing:
            st.error(
                f"以下必填项未填写：**{'、'.join(missing)}**\n\n"
                "请补充后归档，或点「暂存到待处理」先保存。"
            )
        else:
            _persist_selected_structured_labels(structured_values)
            save_session_final(
                file_data,
                src_type,
                field_values,
                tags=_clean_list(structured_values.get("topics", [])),
                **structured_values,
            )
            st.session_state.upload_key += 1
            st.rerun()

    if do_pending:
        _persist_selected_structured_labels(structured_values)
        save_session_pending(
            file_data,
            src_type,
            field_values,
            tags=_clean_list(structured_values.get("topics", [])),
            **structured_values,
        )
        missing = validate_session(
            {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
        )
        if missing:
            st.warning(
                f"已暂存！缺少必填项：**{'、'.join(missing)}**\n\n"
                "请到「待处理」补充完整后再归档。"
            )
        else:
            st.success("已暂存！信息完整，也可在「待处理」直接归档。")
        st.session_state.upload_key += 1
        st.rerun()
