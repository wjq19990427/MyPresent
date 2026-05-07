"""「让AI帮我选标签」前端组件。

用法（在 st.form() 外调用）：
    from components.ai_tagging import render_ai_tag_picker

    render_ai_tag_picker(
        session_data=session,
        model_id=st.session_state.get("llm_selected_model", ""),
        state_key=f"ai_tags_{session['session_id']}",
        apply_key=f"tags_{safe_sid}",   # 表单内标签 multiselect 的 widget key
    )

点击「应用到标签栏」后，组件会把用户勾选的标签写入
session_state["_ai_applied_tags_{state_key}"]，并清除 apply_key 对应的
widget state，触发 st.rerun() 使表单以新 default 重新渲染。

render_ai_tag_picker 必须在 st.form() 外部调用。
"""
from __future__ import annotations

import streamlit as st

from core.db_manager import add_tag, get_tags_registry
from skills.tagging_skill import auto_tag_session


def render_ai_tag_picker(
    session_data: dict,
    model_id: str,
    state_key: str,
    apply_key: str = "",
) -> None:
    """渲染「让AI帮我选标签」交互块。

    Args:
        session_data: 包含 description / feeling 等字段的 session 字典。
        model_id:     当前选中的 LLM model id。
        state_key:    session_state 中存储 AI 分析结果的命名空间键（保证唯一）。
        apply_key:    表单内标签 multiselect 的 widget key；点击「应用」时自动清除，
                      使表单以新 default 重新渲染。传空串则不清除。
    """
    result_key  = f"_ai_tag_result_{state_key}"
    checked_key = f"_ai_tag_checked_{state_key}"
    applied_key = f"_ai_applied_tags_{state_key}"

    with st.expander("✨ 让AI帮我选标签", expanded=False):
        if not model_id:
            st.warning("请先在「📊 运行看板」中配置并选择一个 LLM 模型。")
            return

        col_btn, col_hint = st.columns([2, 5])
        with col_btn:
            clicked = st.button(
                "🤖 开始分析",
                key=f"btn_ai_tag_{state_key}",
                help="AI 将分析记录内容，从现有标签中筛选并生成新情感标签",
            )
        with col_hint:
            st.caption("AI 会评估现有标签的适配度，同时创造新的情感标签供你选择。")

        if clicked:
            with st.spinner("AI 正在分析内容…"):
                tag_result = auto_tag_session(session_data, model_id=model_id)
            st.session_state[result_key]  = tag_result
            st.session_state[checked_key] = list(dict.fromkeys(
                tag_result["suggested_tags"] + tag_result["new_tags"]
            ))

        if result_key not in st.session_state:
            return

        tag_result = st.session_state[result_key]
        reasoning  = tag_result.get("reasoning", "")
        if reasoning:
            st.caption(f"💬 {reasoning}")

        suggested = tag_result.get("suggested_tags", [])
        new_tags  = tag_result.get("new_tags", [])

        if not suggested and not new_tags:
            st.info("未能推荐到合适的标签，请尝试补充描述或感受后再试。")
            return

        prev_checked: list[str] = st.session_state.get(checked_key, suggested + new_tags)
        updated: list[str] = []

        if suggested:
            st.markdown("**从现有标签中推荐**")
            for tag in suggested:
                if st.checkbox(tag, value=(tag in prev_checked),
                               key=f"aitag_s_{state_key}_{tag}"):
                    updated.append(tag)

        if new_tags:
            st.markdown("**AI 新生成的情感标签**")
            for tag in new_tags:
                if st.checkbox(
                    tag,
                    value=(tag in prev_checked),
                    key=f"aitag_n_{state_key}_{tag}",
                    help="选中后将自动加入标签库",
                ):
                    updated.append(tag)

        st.session_state[checked_key] = updated

        if updated:
            st.divider()
            if st.button(
                "✅ 应用选中标签到编辑栏",
                key=f"apply_ai_tags_{state_key}",
                type="primary",
                use_container_width=True,
            ):
                registry = get_tags_registry()
                for tag in updated:
                    if tag not in registry:
                        add_tag(tag)
                st.session_state[applied_key] = updated
                # 清除表单 multiselect 的 widget state，强制下次渲染采用新 default
                if apply_key and apply_key in st.session_state:
                    del st.session_state[apply_key]
                st.rerun()
