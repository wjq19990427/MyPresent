"""统一 AI 分析面板。"""
from __future__ import annotations

import json
from collections.abc import Callable
from html import escape

import streamlit as st

from core.db_manager import get_label_registry
from skills.analysis_skill import AnalysisSkill


_SESSION_SOURCE = "session"
_DRAFT_SOURCE = "draft"

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
_TAG_FIELDS = {
    "domains": "domain",
    "attributes": "attribute",
    "topics": "topic",
    "emotion_tags": "emotion",
}
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


def render_ai_analysis(
    draft: dict,
    model_id: str,
    *,
    state_key: str = "upload",
) -> dict | None:
    """渲染上传草稿 AI 分析面板，确认后返回选中的字段值。"""
    return _render_analysis_panel(
        source_type=_DRAFT_SOURCE,
        source=draft,
        model_id=model_id,
        state_key=state_key,
    )


def render_session_ai_analysis(
    session: dict,
    model_id: str,
    *,
    state_key: str,
) -> dict | None:
    """渲染已存在记录的 AI 分析面板，确认后返回选中的字段值。"""
    return _render_analysis_panel(
        source_type=_SESSION_SOURCE,
        source=session,
        model_id=model_id,
        state_key=state_key,
    )


def _render_analysis_panel(
    *,
    source_type: str,
    source: dict,
    model_id: str,
    state_key: str,
) -> dict | None:
    keys = _keys(state_key)
    _reset_if_source_changed(source, keys)
    applied = st.session_state.pop(keys["apply"], None)

    with st.expander("✨ AI 分析", expanded=keys["result"] in st.session_state):
        if not model_id:
            st.warning("请先在「系统」中配置并选择一个 LLM 模型。")
            return applied

        if st.button("✨ AI 分析", key=f"analysis_run_all_{state_key}", type="primary"):
            _run_analysis(source_type, source, model_id, "all", state_key=state_key)

        result = st.session_state.get(keys["result"])
        if not result:
            st.caption("AI 会一次生成标题、摘要、结构化标签、感受与记录原因。")
            return applied

        st.session_state.setdefault(
            keys["fields"], {field: True for field in result if field != "new_topics"}
        )

        for field in _FIELD_ORDER:
            if field not in result:
                continue
            _render_field_row(
                field, result, source_type, source, model_id, state_key, keys
            )

        st.divider()
        col_all, col_selected = st.columns(2)
        with col_all:
            if st.button("全部采纳", key=f"analysis_apply_all_{state_key}", type="primary"):
                st.session_state[keys["apply"]] = dict(result)
                st.rerun()
        with col_selected:
            if st.button("采纳勾选项", key=f"analysis_apply_checked_{state_key}"):
                states = st.session_state.get(keys["fields"], {})
                st.session_state[keys["apply"]] = {
                    key: value
                    for key, value in result.items()
                    if key == "new_topics" or states.get(key, False)
                }
                st.rerun()

    return applied


def _keys(state_key: str) -> dict[str, str]:
    safe = "".join(c if c.isalnum() else "_" for c in state_key)
    return {
        "result": f"_analysis_result_{safe}",
        "fields": f"_analysis_field_states_{safe}",
        "apply": f"_analysis_apply_payload_{safe}",
        "signature": f"_analysis_signature_{safe}",
    }


def _reset_if_source_changed(source: dict, keys: dict[str, str]) -> None:
    signature = json.dumps(source, ensure_ascii=False, sort_keys=True, default=str)
    if st.session_state.get(keys["signature"]) == signature:
        return
    st.session_state[keys["signature"]] = signature
    st.session_state.pop(keys["result"], None)
    st.session_state.pop(keys["fields"], None)
    st.session_state.pop(keys["apply"], None)


def _render_field_row(
    field: str,
    result: dict,
    source_type: str,
    source: dict,
    model_id: str,
    state_key: str,
    keys: dict[str, str],
) -> None:
    states = st.session_state.setdefault(keys["fields"], {})
    states.setdefault(field, True)

    with st.container(border=True):
        col_check, col_body, col_retry = st.columns([0.7, 5.5, 1.4])
        with col_check:
            states[field] = st.checkbox(
                "采纳",
                value=states.get(field, True),
                key=f"analysis_pick_{state_key}_{field}",
                label_visibility="collapsed",
            )
        with col_body:
            st.markdown(f"**{_FIELD_LABELS[field]}**")
            if field in _TAG_FIELDS:
                st.markdown(_format_badges(field, result), unsafe_allow_html=True)
            else:
                st.write(_format_value(result.get(field)))
        with col_retry:
            if st.button("↺ 重生成", key=f"analysis_retry_open_{state_key}_{field}"):
                states[f"{field}_retry_open"] = not states.get(
                    f"{field}_retry_open", False
                )

        if states.get(f"{field}_retry_open", False):
            _render_retry_controls(field, source_type, source, model_id, state_key)


def _render_retry_controls(
    field: str,
    source_type: str,
    source: dict,
    model_id: str,
    state_key: str,
) -> None:
    with st.container(border=True):
        if st.button("再试一次", key=f"analysis_retry_plain_{state_key}_{field}"):
            _run_analysis(
                source_type, source, model_id, [field], field=field, state_key=state_key
            )

        for hint in _HINTS.get(field, []):
            if st.button(hint, key=f"analysis_retry_{state_key}_{field}_{hint}"):
                _run_analysis(
                    source_type,
                    source,
                    model_id,
                    [field],
                    hint=hint,
                    field=field,
                    state_key=state_key,
                )

        st.caption("自定义")
        custom = st.text_input(
            "自定义提示",
            key=f"analysis_custom_hint_{state_key}_{field}",
            label_visibility="collapsed",
            placeholder="告诉 AI 你想怎么调整",
        )
        if st.button("提交自定义提示", key=f"analysis_retry_custom_{state_key}_{field}"):
            _run_analysis(
                source_type,
                source,
                model_id,
                [field],
                hint=custom,
                field=field,
                state_key=state_key,
            )


def _run_analysis(
    source_type: str,
    source: dict,
    model_id: str,
    fields: str | list[str],
    *,
    hint: str = "",
    field: str = "",
    state_key: str,
) -> None:
    keys = _keys(state_key)
    with st.spinner("AI 正在分析…"):
        runner: Callable = (
            _run_draft_analysis
            if source_type == _DRAFT_SOURCE
            else _run_session_analysis
        )
        skill_result = runner(source, model_id, fields=fields, hint=hint)
    if not skill_result.success:
        st.error(f"AI 分析失败：{skill_result.error}")
        return

    if field:
        current = dict(st.session_state.get(keys["result"], {}))
        current.update(skill_result.data)
        st.session_state[keys["result"]] = current
    else:
        st.session_state[keys["result"]] = skill_result.data
        st.session_state[keys["fields"]] = {
            key: True for key in skill_result.data if key != "new_topics"
        }
    st.rerun()


def _run_draft_analysis(
    draft: dict,
    model_id: str,
    *,
    fields: str | list[str],
    hint: str,
):
    return AnalysisSkill().execute_draft(
        draft,
        model_id,
        fields=fields,
        hint=hint,
    )


def _run_session_analysis(
    session: dict,
    model_id: str,
    *,
    fields: str | list[str],
    hint: str,
):
    return AnalysisSkill().execute_draft(
        session,
        model_id,
        fields=fields,
        hint=hint,
    )


def _format_value(value) -> str:
    if isinstance(value, list):
        return "、".join(str(v) for v in value if str(v).strip()) or "（空）"
    if value is None:
        return "（空）"
    return str(value).strip() or "（空）"


def _format_badges(field: str, result: dict) -> str:
    values = _clean_list(result.get(field))
    new_values: set[str] = set()
    if field == "topics":
        extra_topics = _clean_list(result.get("new_topics"))
        values = list(dict.fromkeys([*values, *extra_topics]))
        new_values.update(extra_topics)

    if not values:
        return "<span style='color:#6b7280;'>（空）</span>"

    existing = {
        item["name"]
        for item in get_label_registry(_TAG_FIELDS[field])
    }
    return " ".join(
        _badge_html(value, is_new=value in new_values or value not in existing)
        for value in values
    )


def _badge_html(value: str, *, is_new: bool) -> str:
    text = escape(value)
    if is_new:
        text = f"✨ {text}（新）"
        bg, fg, border = "#fff7ed", "#9a3412", "#fdba74"
    else:
        bg, fg, border = "#eef2ff", "#3730a3", "#c7d2fe"
    return (
        "<span style='display:inline-block;margin:2px 6px 2px 0;"
        "padding:3px 8px;border-radius:999px;font-size:12px;"
        f"line-height:1.6;background:{bg};color:{fg};border:1px solid {border};'>"
        f"{text}</span>"
    )


def _clean_list(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]
