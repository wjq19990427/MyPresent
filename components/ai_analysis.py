"""上传草稿的统一 AI 分析面板。"""
from __future__ import annotations

import json

import streamlit as st

from skills.analysis_skill import AnalysisSkill


_RESULT_KEY = "_analysis_result"
_FIELD_STATES_KEY = "_analysis_field_states"
_APPLY_KEY = "_analysis_apply_payload"
_DRAFT_SIGNATURE_KEY = "_analysis_draft_signature"

_FIELD_LABELS = {
    "title": "标题",
    "summary": "摘要",
    "domains": "领域",
    "attributes": "视角",
    "topics": "话题",
    "emotion_tags": "情绪",
    "emotion_note": "情绪描述",
    "feeling": "感受",
    "reason": "原因",
}
_FIELD_ORDER = [
    "title",
    "summary",
    "domains",
    "attributes",
    "topics",
    "emotion_tags",
    "emotion_note",
    "feeling",
    "reason",
]
_HINTS = {
    "title": ["太长", "太正式", "太模糊", "换个角度"],
    "domains": ["分类不对", "太宽泛", "换个方向"],
    "attributes": ["分类不对", "太宽泛", "换个方向"],
    "emotion_tags": ["分类不对", "太宽泛", "换个方向"],
    "topics": ["太技术性", "太笼统", "更具体一些"],
    "summary": ["太简短", "换个表达", "更口语化"],
    "feeling": ["太简短", "换个表达", "更口语化"],
    "reason": ["太简短", "换个表达", "更口语化"],
}


def render_ai_analysis(draft: dict, model_id: str) -> dict | None:
    """渲染上传草稿 AI 分析面板，确认后返回选中的字段值。"""
    _reset_if_draft_changed(draft)
    applied = st.session_state.pop(_APPLY_KEY, None)

    with st.expander("✨ AI 分析", expanded=_RESULT_KEY in st.session_state):
        if not model_id:
            st.warning("请先在「运行看板」中配置并选择一个 LLM 模型。")
            return applied

        if st.button("✨ AI 分析", key="analysis_run_all", type="primary"):
            _run_analysis(draft, model_id, "all")

        result = st.session_state.get(_RESULT_KEY)
        if not result:
            st.caption("AI 会一次生成标题、摘要、结构化标签、感受与记录原因。")
            return applied

        st.session_state.setdefault(
            _FIELD_STATES_KEY, {field: True for field in result if field != "new_topics"}
        )

        for field in _FIELD_ORDER:
            if field not in result:
                continue
            _render_field_row(field, result, draft, model_id)
        if result.get("new_topics"):
            st.caption(f"建议新增话题：{_format_value(result['new_topics'])}")

        st.divider()
        col_all, col_selected = st.columns(2)
        with col_all:
            if st.button("全部采纳", key="analysis_apply_all", type="primary"):
                st.session_state[_APPLY_KEY] = dict(result)
                st.rerun()
        with col_selected:
            if st.button("采纳勾选项", key="analysis_apply_checked"):
                states = st.session_state.get(_FIELD_STATES_KEY, {})
                st.session_state[_APPLY_KEY] = {
                    key: value
                    for key, value in result.items()
                    if key == "new_topics" or states.get(key, False)
                }
                st.rerun()

    return applied


def _reset_if_draft_changed(draft: dict) -> None:
    signature = json.dumps(draft, ensure_ascii=False, sort_keys=True, default=str)
    if st.session_state.get(_DRAFT_SIGNATURE_KEY) == signature:
        return
    st.session_state[_DRAFT_SIGNATURE_KEY] = signature
    st.session_state.pop(_RESULT_KEY, None)
    st.session_state.pop(_FIELD_STATES_KEY, None)
    st.session_state.pop(_APPLY_KEY, None)


def _render_field_row(field: str, result: dict, draft: dict, model_id: str) -> None:
    states = st.session_state.setdefault(_FIELD_STATES_KEY, {})
    states.setdefault(field, True)

    with st.container(border=True):
        col_check, col_body, col_retry = st.columns([0.7, 5.5, 1.4])
        with col_check:
            states[field] = st.checkbox(
                "采纳",
                value=states.get(field, True),
                key=f"analysis_pick_{field}",
                label_visibility="collapsed",
            )
        with col_body:
            st.markdown(f"**{_FIELD_LABELS[field]}**")
            st.write(_format_value(result.get(field)))
        with col_retry:
            if st.button("↺ 重生成", key=f"analysis_retry_open_{field}"):
                states[f"{field}_retry_open"] = not states.get(
                    f"{field}_retry_open", False
                )

        if states.get(f"{field}_retry_open", False):
            _render_retry_controls(field, draft, model_id)


def _render_retry_controls(field: str, draft: dict, model_id: str) -> None:
    with st.container(border=True):
        if st.button("再试一次", key=f"analysis_retry_plain_{field}"):
            _run_analysis(draft, model_id, [field], field=field)

        for hint in _HINTS.get(field, []):
            if st.button(hint, key=f"analysis_retry_{field}_{hint}"):
                _run_analysis(draft, model_id, [field], hint=hint, field=field)

        st.caption("自定义")
        custom = st.text_input(
            "自定义提示",
            key=f"analysis_custom_hint_{field}",
            label_visibility="collapsed",
            placeholder="告诉 AI 你想怎么调整",
        )
        if st.button("提交自定义提示", key=f"analysis_retry_custom_{field}"):
            _run_analysis(draft, model_id, [field], hint=custom, field=field)


def _run_analysis(
    draft: dict,
    model_id: str,
    fields: str | list[str],
    *,
    hint: str = "",
    field: str = "",
) -> None:
    with st.spinner("AI 正在分析…"):
        skill_result = AnalysisSkill().execute_draft(
            draft,
            model_id,
            fields=fields,
            hint=hint,
        )
    if not skill_result.success:
        st.error(f"AI 分析失败：{skill_result.error}")
        return

    if field:
        current = dict(st.session_state.get(_RESULT_KEY, {}))
        current.update(skill_result.data)
        st.session_state[_RESULT_KEY] = current
    else:
        st.session_state[_RESULT_KEY] = skill_result.data
        st.session_state[_FIELD_STATES_KEY] = {
            key: True for key in skill_result.data if key != "new_topics"
        }
    st.rerun()


def _format_value(value) -> str:
    if isinstance(value, list):
        return "、".join(str(v) for v in value if str(v).strip()) or "（空）"
    if value is None:
        return "（空）"
    return str(value).strip() or "（空）"
