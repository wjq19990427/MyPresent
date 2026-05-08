"""AI 感受与原因自动补全组件。"""
from __future__ import annotations

import streamlit as st

from skills.completion_skill import CompletionSkill


def render_ai_fill_picker(
    session_data: dict,
    model_id: str,
    state_key: str,
    form_prefix: str,
) -> None:
    """渲染「AI 补全感受与原因」交互块。"""
    result_key  = f"_ai_fill_result_{state_key}"
    result = st.session_state.get(result_key)

    if not model_id:
        st.caption("💡 在「运行看板」选择模型后可使用 AI 补全")
        return

    if not result:
        if st.button("✨ AI 补全感受与原因", key=f"ai_fill_btn_{state_key}"):
            desc = (session_data.get("description") or "").strip()
            if not desc:
                st.warning("描述为空，无法生成补全")
            else:
                with st.spinner("AI 生成中…"):
                    skill_result = CompletionSkill().execute(
                        {**session_data, "model_id": model_id}
                    )
                if skill_result.success:
                    st.session_state[result_key] = skill_result.data
                    st.rerun()
                else:
                    st.error(f"生成失败：{skill_result.error}")
    else:
        with st.container(border=True):
            st.caption("✨ **AI 补全建议**（点「应用」写入表单，不满意可重新生成）")
            st.markdown(f"**感受**：{result['feeling']}")
            if result.get("reason"):
                st.markdown(f"**记录原因**：{result['reason']}")
            ca, cb = st.columns(2)
            with ca:
                if st.button("✅ 应用", key=f"ai_fill_apply_{state_key}", type="primary"):
                    st.session_state[f"{form_prefix}_feeling"] = result["feeling"]
                    st.session_state[f"{form_prefix}_reason"] = result.get("reason", "")
                    st.session_state.pop(result_key, None)
                    st.rerun()
            with cb:
                if st.button("🔄 重新生成", key=f"ai_fill_retry_{state_key}"):
                    st.session_state.pop(result_key, None)
                    st.rerun()
