"""洞见 Tab：检索 / 情绪趋势 / 洞察报告。"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time

import streamlit as st

from components.eval_dashboard import render_model_selector
from components.tab_search import render_search_tab
from core.db_manager import get_linked_goals_for_session, get_llm_models, load_db
from skills.emotion_scoring_skill import EmotionScoringSkill
from skills.insight_report_skill import InsightReportSkill


_INSIGHT_SUB_TABS = ["🔍 检索", "🌈 情绪趋势", "📋 洞察报告"]
_REPORT_SECTIONS = [
    ("emotions", "🌈 情绪画像"),
    ("topics", "🗺️ 话题聚焦"),
    ("patterns", "🔄 行为规律"),
    ("goals", "🎯 目标追踪"),
    ("quotes", "💬 代表语录"),
]
_REPORT_CACHE_KEYS = [f"_insight_report_{section}" for section, _ in _REPORT_SECTIONS]


def render_insight_tab() -> None:
    """渲染洞见 Tab 的内部子页框架。"""
    current = st.session_state.get("insight_sub_tab", _INSIGHT_SUB_TABS[0])
    if current not in _INSIGHT_SUB_TABS:
        current = _INSIGHT_SUB_TABS[0]
        st.session_state["insight_sub_tab"] = current

    cols = st.columns(len(_INSIGHT_SUB_TABS))
    for col, option in zip(cols, _INSIGHT_SUB_TABS):
        with col:
            if st.button(
                option,
                key=f"nav_insight_{option}",
                type="primary" if option == current else "secondary",
                use_container_width=True,
            ):
                st.session_state["insight_sub_tab"] = option
                st.rerun()

    selected = st.session_state.get("insight_sub_tab", current)
    st.divider()
    if selected == "🔍 检索":
        render_search_tab()
    elif selected == "🌈 情绪趋势":
        st.info("情绪趋势功能即将上线")
    elif selected == "📋 洞察报告":
        _render_insight_report()


def _render_insight_report() -> None:
    sessions = _final_sessions(load_db())
    _ensure_report_cache_defaults()

    st.markdown("### 📋 洞察报告")
    if not sessions:
        st.info("暂无已归档记录可生成洞察报告。")
        return

    min_date, max_date = _session_date_bounds(sessions)
    if min_date and max_date:
        _init_date_range(min_date, max_date)
        start, end = _render_date_controls(min_date, max_date)
    else:
        start = end = None
        st.info("已归档记录缺少可识别日期，报告将基于全部记录生成。")

    scoring_mode = st.radio(
        "评分模式",
        ["快速", "精准"],
        horizontal=True,
        key="insight_report_scoring_mode",
        help="快速模式基于已有情绪标签；精准模式会调用 LLM 对情绪强度评分。",
    )
    model_id = _render_report_model_selector(scoring_mode)
    filtered = _filter_sessions_by_range(sessions, start, end)
    period_label = _period_label(start, end)
    _clear_report_cache_if_needed(start, end, scoring_mode, [s["session_id"] for s in filtered])
    st.session_state["_insight_report_linked_goal_ids"] = [
        item["id"] for item in _linked_goal_summary(filtered)
    ]

    st.caption(f"当前范围：{period_label} · {len(filtered)} 条记录")
    if not filtered:
        st.warning("当前时间范围内没有已归档记录。")
        _render_report_sections([], period_label, model_id, scoring_mode)
        return

    if st.button(
        "📋 一键生成全部",
        key="insight_report_generate_all",
        type="primary",
        use_container_width=True,
        disabled=not model_id,
    ):
        _generate_report_sections(filtered, period_label, model_id, scoring_mode, "all")
        st.rerun()

    _render_report_sections(filtered, period_label, model_id, scoring_mode)


def _render_report_model_selector(scoring_mode: str) -> str | None:
    if not get_llm_models():
        st.info("请先前往「📊 运行看板」 Tab 添加 Provider 和模型。")
        return None

    model_id = render_model_selector(widget_key="llm_model_select_insight_report")
    if scoring_mode == "精准" and not model_id:
        st.warning("精准评分需要先选择可用模型。")
    return model_id


def _render_date_controls(min_date: date, max_date: date) -> tuple[date, date]:
    col_start, col_end = st.columns(2)
    with col_start:
        start = st.date_input(
            "开始日期",
            value=st.session_state.get("insight_date_start") or min_date,
            min_value=min_date,
            max_value=max_date,
            key="insight_date_start",
        )
    with col_end:
        end = st.date_input(
            "结束日期",
            value=st.session_state.get("insight_date_end") or max_date,
            min_value=min_date,
            max_value=max_date,
            key="insight_date_end",
        )
    if start > end:
        st.warning("开始日期晚于结束日期，已临时按反向区间处理。")
        start, end = end, start
    return start, end


def _render_report_sections(
    sessions: list[dict],
    period_label: str,
    model_id: str | None,
    scoring_mode: str,
) -> None:
    linked_goal_ids = st.session_state.get("_insight_report_linked_goal_ids", [])
    for section, title in _REPORT_SECTIONS:
        if section == "goals" and sessions and not linked_goal_ids:
            with st.expander(title, expanded=False):
                st.info("本时段无关联目标记录")
            continue

        with st.expander(title, expanded=bool(st.session_state.get(f"_insight_report_{section}"))):
            _render_section_content(section)
            button_label = "↺ 重新生成" if st.session_state.get(f"_insight_report_{section}") else "生成"
            disabled = not sessions or not model_id
            if st.button(
                button_label,
                key=f"insight_report_generate_{section}",
                disabled=disabled,
                use_container_width=True,
            ):
                _generate_report_sections(sessions, period_label, model_id or "", scoring_mode, [section])
                st.rerun()


def _render_section_content(section: str) -> None:
    value = st.session_state.get(f"_insight_report_{section}")
    if section == "quotes":
        quotes = value if isinstance(value, list) else []
        if not quotes:
            st.caption("点击右上角「生成」按钮生成本段内容")
            return
        for quote in quotes:
            st.markdown(f"> {quote}")
        return

    if value:
        st.markdown(str(value))
    else:
        st.caption("点击右上角「生成」按钮生成本段内容")


def _generate_report_sections(
    sessions: list[dict],
    period_label: str,
    model_id: str,
    scoring_mode: str,
    sections: list[str] | str,
) -> None:
    if not model_id:
        st.warning("请先选择模型。")
        return

    requested = [section for section, _ in _REPORT_SECTIONS] if sections == "all" else list(sections)
    with st.spinner("正在生成洞察报告…"):
        stats = _build_report_stats(sessions, scoring_mode, model_id)
        result = InsightReportSkill().execute(
            sessions,
            stats,
            period_label,
            model_id,
            sections=requested,
        )

    if not result.success:
        st.error(result.error or "洞察报告生成失败")
    else:
        for section in requested:
            if section in result.data:
                st.session_state[f"_insight_report_{section}"] = result.data[section]
        st.session_state["_insight_report_linked_goal_ids"] = stats.get("linked_goal_ids", [])


def _build_report_stats(sessions: list[dict], scoring_mode: str, model_id: str) -> dict:
    scoring = EmotionScoringSkill()
    if scoring_mode == "精准":
        emotion_scores = scoring.score_precise(sessions, model_id)
    else:
        emotion_scores = scoring.score_quick(sessions)

    emotion_freq = Counter()
    topic_freq = Counter()
    domain_freq = Counter()
    record_dates = []
    weekday_freq = Counter()
    time_bucket_freq = Counter()

    for session in sessions:
        emotion_freq.update(_string_list(session.get("emotion_tags")))
        topic_freq.update(_string_list(session.get("topics")))
        domain_freq.update(_string_list(session.get("domains")))
        dt = _parse_content_datetime(session.get("content_time"))
        if not dt:
            continue
        record_dates.append(dt.date().isoformat())
        weekday_freq[_weekday_label(dt.weekday())] += 1
        time_bucket_freq[_time_bucket(dt.time())] += 1

    linked_goal_summary = _linked_goal_summary(sessions)
    return {
        "emotion_scores": emotion_scores,
        "emotion_freq": dict(emotion_freq),
        "topic_freq": dict(topic_freq),
        "domain_freq": dict(domain_freq),
        "record_dates": record_dates,
        "linked_goal_ids": [item["id"] for item in linked_goal_summary],
        "weekday_freq": dict(weekday_freq),
        "time_bucket_freq": dict(time_bucket_freq),
        "linked_goal_summary": linked_goal_summary,
    }


def _linked_goal_summary(sessions: list[dict]) -> list[dict]:
    by_goal: dict[str, dict] = {}
    for session in sessions:
        session_id = str(session.get("session_id") or session.get("id") or "").strip()
        if not session_id:
            continue
        for goal in get_linked_goals_for_session(session_id):
            goal_id = str(goal.get("id", "")).strip()
            if not goal_id:
                continue
            item = by_goal.setdefault(
                goal_id,
                {
                    "id": goal_id,
                    "content": str(goal.get("content", "")).strip(),
                    "category": str(goal.get("category", "")).strip(),
                    "priority": str(goal.get("priority", "")).strip(),
                    "deadline": str(goal.get("deadline", "")).strip(),
                    "status": str(goal.get("status", "")).strip(),
                    "count": 0,
                },
            )
            item["count"] += 1
    return sorted(by_goal.values(), key=lambda item: (-item["count"], item["content"]))


def _final_sessions(sessions: list[dict]) -> list[dict]:
    return [session for session in sessions if session.get("status") == "final"]


def _session_date_bounds(sessions: list[dict]) -> tuple[date | None, date | None]:
    dates = [
        parsed.date()
        for session in sessions
        if (parsed := _parse_content_datetime(session.get("content_time")))
    ]
    if not dates:
        return None, None
    return min(dates), max(dates)


def _init_date_range(min_date: date, max_date: date) -> None:
    if st.session_state.get("insight_date_start") is None:
        st.session_state["insight_date_start"] = min_date
    if st.session_state.get("insight_date_end") is None:
        st.session_state["insight_date_end"] = max_date


def _filter_sessions_by_range(
    sessions: list[dict],
    start: date | None,
    end: date | None,
) -> list[dict]:
    if not start or not end:
        return sessions

    filtered = []
    for session in sessions:
        parsed = _parse_content_datetime(session.get("content_time"))
        if parsed and start <= parsed.date() <= end:
            filtered.append(session)
    return filtered


def _clear_report_cache_if_needed(
    start: date | None,
    end: date | None,
    scoring_mode: str,
    session_ids: list[str],
) -> None:
    sig = (
        start.isoformat() if start else "",
        end.isoformat() if end else "",
        scoring_mode,
        tuple(session_ids),
    )
    if st.session_state.get("_insight_report_signature") == sig:
        return
    for key in _REPORT_CACHE_KEYS:
        st.session_state[key] = [] if key.endswith("_quotes") else None
    st.session_state["_insight_report_linked_goal_ids"] = []
    st.session_state["_insight_report_signature"] = sig


def _ensure_report_cache_defaults() -> None:
    for section, _ in _REPORT_SECTIONS:
        key = f"_insight_report_{section}"
        if key not in st.session_state:
            st.session_state[key] = [] if section == "quotes" else None
    st.session_state.setdefault("_insight_report_linked_goal_ids", [])


def _period_label(start: date | None, end: date | None) -> str:
    if start and end:
        if start == end:
            return start.isoformat()
        return f"{start.isoformat()} ~ {end.isoformat()}"
    return "全部可用记录"


def _parse_content_datetime(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    for fmt, length in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y/%m/%d %H:%M", 16),
        ("%Y.%m.%d %H:%M", 16),
        ("%Y-%m-%d", 10),
        ("%Y/%m/%d", 10),
        ("%Y.%m.%d", 10),
    ):
        try:
            return datetime.strptime(text[:length], fmt)
        except ValueError:
            continue
    return None


def _weekday_label(index: int) -> str:
    return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][index]


def _time_bucket(value: time) -> str:
    hour = value.hour
    if 5 <= hour < 12:
        return "早晨/上午"
    if 12 <= hour < 18:
        return "下午"
    if 18 <= hour < 24:
        return "晚上"
    return "深夜"


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
