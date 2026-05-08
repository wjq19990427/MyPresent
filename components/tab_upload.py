"""记录舱 Tab — 文件上传 / 粘贴文字 / 文件夹导入。"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.constants import TEXT_EXTS, SUPPORTED_IMPORT_EXTS, FIELD_SCHEMA
from core.db_manager import get_tags_registry, validate_session, add_tag
from core.file_io import save_session_pending, save_session_final, import_folder_to_pending
from components.forms import render_field_inputs
from skills.tagging_skill import auto_tag_session


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


def _render_folder_import() -> None:
    done = st.session_state.get("folder_import_done", 0)
    if done:
        st.success(f"✅ 已成功导入 **{done}** 条记录到灵感墙！")
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
            st.session_state["folder_scan_results"] = [str(f) for f in found]

    scan_results: list[str] = st.session_state.get("folder_scan_results", [])
    if not scan_results:
        st.caption("支持格式：图片（jpg/png/gif/webp/bmp）、视频（mp4/mov/avi 等）、文本（txt/md）")
        return

    st.markdown(f"扫描到 **{len(scan_results)}** 个支持格式的文件，请勾选要导入的内容：")

    file_names     = [Path(p).name for p in scan_results]
    selected_names = st.multiselect(
        "选择文件",
        options=file_names,
        default=file_names,
        key="folder_file_select",
        label_visibility="collapsed",
    )

    st.markdown("**🏷️ 标签** **\\*（必填）**")
    folder_tags = st.multiselect(
        "标签",
        options=get_tags_registry(),
        key="folder_import_tags",
        label_visibility="collapsed",
        placeholder="至少选择一个标签",
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

        if st.button("📥 导入到灵感墙", type="primary", key="do_import_btn"):
            if not folder_tags:
                st.error("❌ 请至少选择一个标签后再导入")
            else:
                with st.spinner(f"正在导入 {len(selected_paths)} 个文件…"):
                    count = import_folder_to_pending(
                        selected_paths, as_one_session=as_one, tags=folder_tags
                    )
                st.session_state["folder_scan_results"] = []
                st.session_state["folder_import_done"]  = count
                st.rerun()
    else:
        st.info("请至少选择一个文件")

    if st.button("清除扫描结果", key="clear_scan_btn"):
        st.session_state["folder_scan_results"] = []
        st.rerun()


def render_upload_tab() -> None:
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

    st.divider()
    st.markdown("**🏷️ 标签** **\\*（必填）**")
    tag_col, ai_col = st.columns([5, 1])
    with tag_col:
        upload_tags = st.multiselect(
            "标签",
            options=get_tags_registry(),
            key=f"upload_tags_{st.session_state.upload_key}",
            label_visibility="collapsed",
            placeholder="至少选择一个标签",
        )
    with ai_col:
        model_id  = st.session_state.get("llm_selected_model") or ""
        ai_ready  = bool(model_id)
        if st.button(
            "✨ AI",
            key="upload_ai_tag_btn",
            disabled=not ai_ready,
            help="在「运行看板」Tab 选择模型后可自动推荐标签" if not ai_ready else "AI 推荐标签",
        ):
            with st.spinner("AI 推荐标签中…"):
                suggestions = auto_tag_session(
                    {"description": auto_description, "feeling": ""},
                    model_id=model_id,
                )
            combined = suggestions["suggested_tags"] + suggestions["new_tags"]
            if combined:
                for tag in suggestions["new_tags"]:
                    add_tag(tag)
                st.session_state[f"upload_tags_{st.session_state.upload_key}"] = combined
                st.rerun()
            else:
                st.warning("未能推荐到标签，请手动选择")

    with st.form("upload_meta_form"):
        st.markdown("### 📋 填写记录信息")
        if is_text_content:
            st.caption("💡 描述已自动使用内容填充，无需手动填写")
        field_values = render_field_inputs("upload", skip_keys=skip)
        if is_text_content:
            field_values["description"] = auto_description
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            do_archive = st.form_submit_button(
                "✅ 完成并归档", type="primary", use_container_width=True
            )
        with c2:
            do_pending = st.form_submit_button(
                "📦 暂存到待处理", use_container_width=True
            )

    if source_mode == "📁 上传文件":
        file_data = [(f, f.name) for f in files]
        src_type  = "file"
    else:
        file_data = [(pasted_text.encode("utf-8"), _pasted_filename(pasted_text))]
        src_type  = "text"

    if do_archive:
        if not upload_tags:
            st.error("❌ 请至少选择一个**标签**后再归档。")
        else:
            missing = validate_session(
                {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
            )
            if missing:
                st.error(
                    f"❌ 以下必填项未填写：**{'、'.join(missing)}**\n\n"
                    "请补充后归档，或点「暂存到待处理」先保存。"
                )
            else:
                save_session_final(file_data, src_type, field_values, tags=upload_tags)
                st.session_state.upload_key += 1
                st.rerun()

    if do_pending:
        if not upload_tags:
            st.error("❌ 请至少选择一个**标签**后再保存。")
        else:
            save_session_pending(file_data, src_type, field_values, tags=upload_tags)
            missing = validate_session(
                {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
            )
            if missing:
                st.warning(
                    f"📦 已暂存！缺少必填项：**{'、'.join(missing)}**\n\n"
                    "请到「灵感墙」补充完整后再归档。"
                )
            else:
                st.success("📦 已暂存！信息完整，也可在「灵感墙」直接归档。")
            st.session_state.upload_key += 1
            st.rerun()
