"""洞见 Tab：检索 / 情绪趋势 / 洞察报告。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

import streamlit as st

from components.cards import _render_card
from components.tab_search import render_search_tab
from core.db_manager import get_emotion_scores, get_label_registry, load_db
from skills.emotion_scoring_skill import EmotionScoringSkill


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
        st.info("洞察报告功能即将上线")


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
