"""「让AI帮我选标签」前端组件。

用法（在 st.form() 外调用）：
    from components.ai_tagging import render_ai_tag_picker

    render_ai_tag_picker(
        session_data=session,
        model_id=st.session_state.get("llm_selected_model", ""),
        state_key=f"ai_tags_{session['session_id']}",
        apply_key=f"tags_{safe_sid}",   # 表单内标签 multiselect 的 widget key
        new_tags_key=f"{safe_sid}_ai_new_tags",
    )

点击按钮后，组件会直接把 AI 建议合并写入 apply_key 对应的 widget state。
new_tags_key 用于记录尚未入库的新标签，由调用方在保存时处理入库。

render_ai_tag_picker 必须在 st.form() 外部调用。
"""
from __future__ import annotations

import streamlit as st

from skills.tagging_skill import auto_tag_session


def render_ai_tag_picker(
    session_data: dict,
    model_id: str,
    state_key: str,
    apply_key: str = "",
    new_tags_key: str = "",
) -> None:
    """渲染「让AI帮我选标签」交互块。

    Args:
        session_data: 包含 description / feeling 等字段的 session 字典。
        model_id:     当前选中的 LLM model id。
        state_key:    session_state 中存储 AI 分析结果的命名空间键（保证唯一）。
        apply_key:    标签 multiselect 的 widget key；点击按钮时自动合并写入。
        new_tags_key: 未入库新标签列表的 session_state key，传空串则不写。
    """
    result_key  = f"_ai_tag_result_{state_key}"
    toast_key = f"_ai_tag_toast_{state_key}"

    if not model_id:
        st.warning("请先在「📊 运行看板」中配置并选择一个 LLM 模型。")
        return

    if st.session_state.pop(toast_key, False):
        st.toast("AI 建议标签已更新，确认后保存生效")

    col_btn, col_hint = st.columns([2, 5])
    with col_btn:
        clicked = st.button(
            "🤖 AI 建议标签",
            key=f"btn_ai_tag_{state_key}",
            help="AI 将分析记录内容，并直接填入标签选择框",
            use_container_width=True,
        )
    with col_hint:
        st.caption("点击后会直接更新下方标签选择框；保存后才会写入新标签。")

    if clicked:
        with st.spinner("AI 正在分析内容…"):
            tag_result = auto_tag_session(session_data, model_id=model_id)
        st.session_state[result_key] = tag_result
        suggested = _clean_tags(tag_result.get("suggested_tags", []))
        new_tags = _clean_tags(tag_result.get("new_tags", []))
        applied = list(dict.fromkeys([*suggested, *new_tags]))
        if not applied:
            st.info("未能推荐到合适的标签，请尝试补充描述或感受后再试。")
            return
        if apply_key:
            current = _clean_tags(st.session_state.get(apply_key, []))
            st.session_state[apply_key] = list(dict.fromkeys([*current, *applied]))
        if new_tags_key:
            current_new = _clean_tags(st.session_state.get(new_tags_key, []))
            st.session_state[new_tags_key] = list(
                dict.fromkeys([*current_new, *new_tags])
            )
        st.session_state[toast_key] = True
        st.rerun()

    tag_result = st.session_state.get(result_key, {})
    reasoning = str(tag_result.get("reasoning") or "").strip()
    if reasoning:
        st.caption(f"💬 {reasoning}")


def _clean_tags(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [
        str(item).strip()
        for item in items
        if item is not None and str(item).strip()
    ]
