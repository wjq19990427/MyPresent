"""洞见 Tab：检索 / 情绪趋势 / 洞察报告。"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

import streamlit as st

from components.cards import _render_card
from components.eval_dashboard import render_model_selector
from components.tab_search import render_search_tab
from core.db_manager import (
    get_emotion_scores,
    get_label_registry,
    get_linked_goals_for_session,
    get_llm_models,
    load_db,
)
from skills.emotion_scoring_skill import EmotionScoringSkill
from skills.insight_report_skill import InsightReportSkill


_INSIGHT_SUB_TABS = ["🔍 检索", "🌈 情绪趋势", "📋 洞察报告"]
_DEFAULT_EMOTION_COLORS = {
    "喜悦": "#f59e0b",
    "平静": "#0ea5e9",
    "充实": "#22c55e",
    "期待": "#8b5cf6",
    "疲惫": "#64748b",
    "焦虑": "#ef4444",
    "愤怒": "#dc2626",
    "失落": "#6366f1",
    "迷茫": "#14b8a6",
}
_EMOTION_FALLBACK_COLORS = [
    "#ec4899",
    "#06b6d4",
    "#84cc16",
    "#f97316",
    "#a855f7",
    "#10b981",
    "#eab308",
    "#3b82f6",
]
_GRAIN_LABELS = {"week": "周", "month": "月", "year": "年"}
_MODE_LABELS = {"quick": "快速（频次）", "precise": "精准（LLM）"}
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
        _render_emotion_trend()
    elif selected == "📋 洞察报告":
        _render_insight_report()


def _render_emotion_trend() -> None:
    controls = _render_emotion_controls()
    sessions = _filter_emotion_sessions(controls["start"], controls["end"])
    if not sessions:
        st.info("所选时间范围内暂无已归档记录。")
        return

    emotions = _collect_emotions(sessions)
    if not emotions:
        st.info("当前记录暂无情绪标签，请先在记录详情中完善情绪标签。")
        return

    if controls["mode"] == "precise":
        st.caption("精准模式将消耗 LLM 调用，首次计算后缓存")
        _render_precise_action(sessions)

    scores = _load_scores(sessions, controls["mode"])
    periods = _period_labels(controls["start"], controls["end"], controls["grain"])
    matrix, buckets = _build_emotion_matrix(
        sessions, emotions, periods, controls["grain"], scores
    )
    selected = _render_heatmap(emotions, periods, matrix)
    selected = _render_drilldown_selector(emotions, periods, selected)
    _render_drilldown(selected, buckets, scores, controls["mode"])


def _render_emotion_controls() -> dict:
    today = date.today()
    default_start = today - timedelta(days=90)
    col_start, col_end, col_grain, col_mode = st.columns([1.2, 1.2, 1.2, 1.5])
    with col_start:
        start_value = st.date_input(
            "开始日期",
            value=st.session_state.get("emotion_trend_start", default_start),
            key="emotion_trend_start",
        )
    with col_end:
        end_value = st.date_input(
            "结束日期",
            value=st.session_state.get("emotion_trend_end", today),
            key="emotion_trend_end",
        )
    with col_grain:
        grain_label = st.radio(
            "时间粒度",
            list(_GRAIN_LABELS.values()),
            index=1,
            horizontal=True,
            key="emotion_trend_grain_label",
        )
    with col_mode:
        mode_label = st.radio(
            "评分模式",
            list(_MODE_LABELS.values()),
            horizontal=True,
            key="emotion_trend_mode_label",
        )

    start = _coerce_date(start_value, default_start)
    end = _coerce_date(end_value, today)
    if start > end:
        st.warning("开始日期不能晚于结束日期，已自动交换。")
        start, end = end, start

    grain = _label_to_key(_GRAIN_LABELS, grain_label, "month")
    mode = _label_to_key(_MODE_LABELS, mode_label, "quick")
    return {"start": start, "end": end, "grain": grain, "mode": mode}


def _render_precise_action(sessions: list[dict]) -> None:
    model_id = st.session_state.get("llm_selected_model") or ""
    if not model_id:
        st.warning("请先在「系统」中选择一个 LLM 模型。")
    if st.button(
        "开始精准分析",
        key="emotion_trend_precise_run",
        type="primary",
        disabled=not model_id,
    ):
        with st.spinner("正在计算情绪强度…"):
            EmotionScoringSkill().score_precise(sessions, model_id)
        st.rerun()


def _filter_emotion_sessions(start: date, end: date) -> list[dict]:
    sessions = []
    for session in load_db():
        if session.get("status") != "final":
            continue
        session_date = _session_date(session)
        if not session_date or not (start <= session_date <= end):
            continue
        sessions.append({**session, "_emotion_trend_date": session_date})
    return sessions


def _session_date(session: dict) -> date | None:
    return _parse_date(session.get("content_time")) or _parse_date(
        session.get("upload_time")
    )


def _parse_date(value) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


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


def _collect_emotions(sessions: list[dict]) -> list[str]:
    seen = set()
    emotions = []
    registry_order = [item["name"] for item in get_label_registry("emotion")]
    all_tags = set()
    for session in sessions:
        all_tags.update(_emotion_tags(session))

    for emotion in registry_order:
        if emotion in all_tags and emotion not in seen:
            seen.add(emotion)
            emotions.append(emotion)
    for emotion in sorted(all_tags):
        if emotion not in seen:
            seen.add(emotion)
            emotions.append(emotion)
    return emotions


def _emotion_tags(session: dict) -> list[str]:
    tags = session.get("emotion_tags", [])
    if not isinstance(tags, list):
        return []
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def _load_scores(sessions: list[dict], mode: str) -> dict[str, dict[str, float]]:
    if mode == "quick":
        return EmotionScoringSkill().score_quick(sessions)
    session_ids = [session["session_id"] for session in sessions]
    return get_emotion_scores(session_ids, "precise")


def _period_labels(start: date, end: date, grain: str) -> list[str]:
    labels = []
    cursor = start
    while cursor <= end:
        label = _period_label(cursor, grain)
        if not labels or labels[-1] != label:
            labels.append(label)
        cursor += timedelta(days=1)
    return labels


def _period_label(value: date, grain: str) -> str:
    if grain == "week":
        iso = value.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if grain == "year":
        return f"{value.year:04d}"
    return f"{value.year:04d}-{value.month:02d}"


def _build_emotion_matrix(
    sessions: list[dict],
    emotions: list[str],
    periods: list[str],
    grain: str,
    scores: dict[str, dict[str, float]],
) -> tuple[list[list[float]], dict[tuple[str, str], list[dict]]]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for session in sessions:
        session_id = session["session_id"]
        session_date = session.get("_emotion_trend_date")
        if not isinstance(session_date, date):
            continue
        period = _period_label(session_date, grain)
        session_scores = scores.get(session_id, {})
        for emotion in _emotion_tags(session):
            score = float(session_scores.get(emotion, 0.0) or 0.0)
            score = max(0.0, min(1.0, score))
            values[(emotion, period)].append(score)
            buckets[(emotion, period)].append(session)

    matrix = []
    for emotion in emotions:
        row = []
        for period in periods:
            cell_values = values.get((emotion, period), [])
            row.append(sum(cell_values) / len(cell_values) if cell_values else 0.0)
        matrix.append(row)
    return matrix, buckets


def _render_heatmap(
    emotions: list[str], periods: list[str], matrix: list[list[float]]
) -> tuple[str, str] | None:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError:
        st.error("当前环境缺少 plotly，无法渲染情绪热力矩阵。请安装 plotly 后重试。")
        return None

    fig = go.Figure()
    colors = _emotion_colors(emotions)
    for index, emotion in enumerate(emotions):
        fig.add_trace(
            go.Heatmap(
                z=[matrix[index]],
                x=periods,
                y=[emotion],
                zmin=0,
                zmax=1,
                colorscale=[[0, "#f8fafc"], [1, colors[emotion]]],
                showscale=False,
                hovertemplate=(
                    "情绪：%{y}<br>周期：%{x}<br>强度：%{z:.0%}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        margin={"l": 20, "r": 20, "t": 10, "b": 20},
        height=max(280, 42 * len(emotions) + 120),
        xaxis_title="时间周期",
        yaxis_title="情绪",
        plot_bgcolor="white",
    )
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        key="emotion_trend_heatmap",
        on_select="rerun",
        selection_mode="points",
    )
    return _selected_heatmap_cell(event)


def _selected_heatmap_cell(event) -> tuple[str, str] | None:
    selection = getattr(event, "selection", None)
    points = []
    if isinstance(selection, dict):
        points = selection.get("points") or []
    elif selection is not None:
        points = getattr(selection, "points", []) or []
    if not points:
        return None
    point = points[0]
    if not isinstance(point, dict):
        return None
    emotion = str(point.get("y") or "").strip()
    period = str(point.get("x") or "").strip()
    if not emotion or not period:
        return None
    return emotion, period


def _render_drilldown_selector(
    emotions: list[str],
    periods: list[str],
    selected: tuple[str, str] | None,
) -> tuple[str, str] | None:
    option_labels = ["选择情绪与周期"] + [
        f"{emotion} · {period}" for emotion in emotions for period in periods
    ]
    option_values: list[tuple[str, str] | None] = [None] + [
        (emotion, period) for emotion in emotions for period in periods
    ]
    if not option_values:
        return None

    if selected is not None:
        index = option_values.index(selected)
        st.session_state["emotion_trend_drilldown_select"] = option_labels[index]

    label = st.selectbox(
        "下钻查看",
        option_labels,
        key="emotion_trend_drilldown_select",
    )
    selected_value = option_values[option_labels.index(label)]
    return selected_value


def _render_drilldown(
    selected: tuple[str, str] | None,
    buckets: dict[tuple[str, str], list[dict]],
    scores: dict[str, dict[str, float]],
    mode: str,
) -> None:
    if not selected:
        return
    emotion, period = selected
    sessions = buckets.get((emotion, period), [])
    st.markdown(f"#### {emotion} · {period} 的记录")
    if not sessions:
        st.info("该时段暂无包含此情绪的记录。")
        return

    for row_start in range(0, len(sessions), 3):
        cols = st.columns(3)
        for col, session in zip(cols, sessions[row_start : row_start + 3]):
            score = scores.get(session["session_id"], {}).get(emotion)
            _render_card(
                col,
                session,
                state_key=f"emotion_trend_{mode}_{emotion}_{period}",
                score=score,
            )


def _emotion_colors(emotions: list[str]) -> dict[str, str]:
    registry = [item["name"] for item in get_label_registry("emotion")]
    colors = {}
    for index, emotion in enumerate(registry):
        if emotion in _DEFAULT_EMOTION_COLORS:
            colors[emotion] = _DEFAULT_EMOTION_COLORS[emotion]
        else:
            colors[emotion] = _EMOTION_FALLBACK_COLORS[
                index % len(_EMOTION_FALLBACK_COLORS)
            ]
    for index, emotion in enumerate(emotions):
        colors.setdefault(
            emotion, _EMOTION_FALLBACK_COLORS[index % len(_EMOTION_FALLBACK_COLORS)]
        )
    return colors


def _coerce_date(value, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return fallback


def _label_to_key(mapping: dict[str, str], label: str, fallback: str) -> str:
    for key, value in mapping.items():
        if value == label:
            return key
    return fallback


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
