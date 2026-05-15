"""「让AI帮我选标签」前端组件。"""
from __future__ import annotations

import streamlit as st

from skills.tagging_skill import auto_tag_session


_FIELDS = ("domains", "attributes", "topics", "emotion_tags")


def render_ai_tag_picker(
    session_data: dict,
    model_id: str,
    state_key: str,
    apply_keys: dict[str, str] | None = None,
    new_tags_key: str = "",
) -> None:
    """渲染「让AI帮我选标签」交互块。"""
    apply_keys = apply_keys or {}
    result_key = f"_ai_tag_result_{state_key}"
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
            help="AI 将分析记录内容，并直接填入下方四维标签选择框",
            use_container_width=True,
        )
    with col_hint:
        st.caption("点击后会直接更新下方四维标签选择框；保存后才会写入新标签。")

    if clicked:
        with st.spinner("AI 正在分析标签…"):
            tag_result = auto_tag_session(session_data, model_id=model_id)
        st.session_state[result_key] = tag_result
        suggested = _clean_tag_map(tag_result.get("suggested", {}))
        new_labels = _clean_tag_map(tag_result.get("new_labels", {}))
        applied_any = False

        for field in _FIELDS:
            applied = list(dict.fromkeys([*suggested[field], *new_labels[field]]))
            if not applied:
                continue
            applied_any = True
            target_key = apply_keys.get(field, "")
            if target_key:
                current = _clean_tags(st.session_state.get(target_key, []))
                st.session_state[target_key] = list(dict.fromkeys([*current, *applied]))

        if new_tags_key:
            current_new = _clean_new_tag_state(st.session_state.get(new_tags_key, {}))
            for field in _FIELDS:
                current_new[field] = list(
                    dict.fromkeys([*current_new[field], *new_labels[field]])
                )
            st.session_state[new_tags_key] = current_new

        if not applied_any:
            st.info("未能推荐到合适的标签，请尝试补充描述或感受后再试。")
            return
        st.session_state[toast_key] = True
        st.rerun()

    tag_result = st.session_state.get(result_key, {})
    reasoning = str(tag_result.get("reasoning") or "").strip()
    if reasoning:
        st.caption(f"💬 {reasoning}")


def _clean_tag_map(value) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        value = {}
    return {field: _clean_tags(value.get(field, [])) for field in _FIELDS}


def _clean_new_tag_state(value) -> dict[str, list[str]]:
    if isinstance(value, dict):
        return _clean_tag_map(value)
    return {field: [] for field in _FIELDS}


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
