"""规划控制台 Tab：年度规划 + 日历 & 日志。"""
from __future__ import annotations

import calendar as cal_lib
from collections import defaultdict
from datetime import date, datetime
from html import escape
import re

import streamlit as st

from core.db_manager import (
    GOAL_PRIORITIES,
    GOAL_STATUSES,
    TODO_CATEGORIES,
    TODO_PRIORITIES,
    TODO_RECURRENCES,
    complete_todo,
    create_annual_goal,
    create_calendar_todo,
    delete_annual_goal,
    delete_calendar_todo,
    delete_daily_activity,
    get_annual_goal,
    get_annual_goals,
    get_calendar_todos,
    get_daily_activities,
    get_goal_categories,
    get_monthly_activity_stats,
    get_todos_by_goal,
    migrate_overdue_todos,
    postpone_todo,
    add_goal_category,
    create_daily_activity,
    delete_goal_category,
    update_annual_goal,
    update_daily_activity,
    update_calendar_todo,
)
from core.llm_client import call_llm
from core.prompts import (
    PLANNING_RECORD_MOMENT_SYSTEM,
    PLANNING_RECORD_MOMENT_USER_TMPL,
)


PRIORITY_COLORS = {
    "高": ("#b91c1c", "#fee2e2", "#fecaca"),
    "中": ("#a16207", "#fef3c7", "#fde68a"),
    "低": ("#15803d", "#dcfce7", "#bbf7d0"),
}
CALENDAR_COL_SPEC = [1, 1, 1, 1, 1, 1, 1]
WEEK_HEADERS = ["一", "二", "三", "四", "五", "六", "日"]
MAX_DAY_TODOS = 3


def format_duration(minutes: int) -> str:
    minutes = max(0, int(minutes or 0))
    hours, mins = divmod(minutes, 60)
    if hours == 0:
        return f"{mins}分钟"
    if mins == 0:
        return f"{hours}小时"
    return f"{hours}小时{mins}分钟"


def render_planning_tab() -> None:
    st.session_state.setdefault("planning_sub_tab", "calendar")
    sub1, sub2 = st.tabs(["📅 日历 & 日志", "🎯 年度规划"])
    with sub1:
        _render_calendar_todos()
    with sub2:
        _render_annual_goals()


def _render_annual_goals() -> None:
    categories = get_goal_categories()
    category_names = [c["name"] for c in categories]

    fc1, fc2, fc3, fc4 = st.columns([3, 3, 2, 2])
    with fc1:
        f_status = st.multiselect(
            "状态筛选", GOAL_STATUSES, key="planning_goal_filter_status"
        )
    with fc2:
        f_cat = st.multiselect(
            "分类筛选", category_names, key="planning_goal_filter_cat"
        )
    with fc3:
        if st.button("➕ 新增目标", key="add_goal_btn", type="primary"):
            st.session_state["planning_goal_editing"] = "NEW"
            st.rerun()
    with fc4:
        if st.button("分类管理", key="cat_manager_btn"):
            st.session_state["planning_cat_manager_open"] = not st.session_state.get(
                "planning_cat_manager_open", False
            )
            st.rerun()

    if st.session_state.get("planning_cat_manager_open"):
        _render_category_manager(categories)

    editing = st.session_state.get("planning_goal_editing")
    if editing:
        _render_goal_form(editing, category_names)

    goals = get_annual_goals(status_filter=f_status or None)
    if f_cat:
        goals = [g for g in goals if g["category"] in f_cat]

    if not goals:
        st.info("暂无目标，点击「➕ 新增目标」开始规划。")
        return

    for goal in goals:
        _render_goal_row(goal)


def _render_goal_form(editing: str, category_names: list[str]) -> None:
    is_new = editing == "NEW"
    goal = {} if is_new else (get_annual_goal(editing) or {})
    if not is_new and not goal:
        st.session_state["planning_goal_editing"] = None
        st.rerun()

    if not category_names:
        st.warning("暂无可用分类，请先在分类管理中新增分类。")
        return

    category_value = goal.get("category", category_names[0])
    category_index = (
        category_names.index(category_value) if category_value in category_names else 0
    )
    priority_value = goal.get("priority", "中")
    priority_index = (
        GOAL_PRIORITIES.index(priority_value)
        if priority_value in GOAL_PRIORITIES
        else GOAL_PRIORITIES.index("中")
    )
    status_value = goal.get("status", "未开始")
    status_index = (
        GOAL_STATUSES.index(status_value)
        if status_value in GOAL_STATUSES
        else GOAL_STATUSES.index("未开始")
    )
    deadline_value = _parse_date(goal.get("deadline")) or date.today()

    with st.container(border=True):
        st.markdown("#### ✍️ " + ("新增目标" if is_new else "编辑目标"))
        content = st.text_area(
            "目标内容 *", value=goal.get("content", ""), key="ge_content"
        )
        category = st.selectbox(
            "规划维度 *", category_names, key="ge_cat", index=category_index
        )
        priority = st.selectbox(
            "优先级 *", GOAL_PRIORITIES, key="ge_priority", index=priority_index
        )
        deadline = st.date_input(
            "截止日期 *", value=deadline_value, key="ge_deadline"
        )
        status = st.selectbox(
            "状态", GOAL_STATUSES, key="ge_status", index=status_index
        )

        ca, cb = st.columns(2)
        with ca:
            if st.button("💾 保存", key="ge_save", type="primary"):
                if content.strip() and deadline:
                    if is_new:
                        create_annual_goal(
                            content.strip(), category, priority, str(deadline), status
                        )
                    else:
                        update_annual_goal(
                            goal["id"],
                            content=content.strip(),
                            category=category,
                            priority=priority,
                            deadline=str(deadline),
                            status=status,
                        )
                    st.session_state["planning_goal_editing"] = None
                    st.rerun()
                else:
                    st.warning("目标内容和截止日期为必填项")
        with cb:
            if st.button("取消", key="ge_cancel"):
                st.session_state["planning_goal_editing"] = None
                st.rerun()


def _render_category_manager(categories: list[dict]) -> None:
    with st.container(border=True):
        st.markdown("#### 分类管理")
        if not categories:
            st.info("暂无分类。")
        for category in categories:
            name = category["name"]
            is_system = bool(category["is_system"])
            c1, c2 = st.columns([5, 1])
            with c1:
                suffix = " · 系统内置" if is_system else " · 自定义"
                st.caption(f"{name}{suffix}")
            with c2:
                if is_system:
                    st.caption("受保护")
                elif st.button("删除", key=f"cat_del_{name}"):
                    delete_goal_category(name)
                    _remove_goal_filter_value(name)
                    st.rerun()

        new_name = st.text_input("新增分类", key="new_goal_category")
        if st.button("添加分类", key="cat_add_btn", type="primary"):
            normalized = new_name.strip()
            if not normalized:
                st.warning("分类名称不能为空")
            elif any(c["name"] == normalized and c["is_system"] for c in categories):
                st.warning("系统内置分类已存在")
            elif any(c["name"] == normalized for c in categories):
                st.warning("分类已存在")
            else:
                add_goal_category(normalized)
                st.rerun()


def _remove_goal_filter_value(name: str) -> None:
    current = st.session_state.get("planning_goal_filter_cat", [])
    st.session_state["planning_goal_filter_cat"] = [c for c in current if c != name]


def _render_goal_row(goal: dict) -> None:
    priority_label = _priority_label(goal["priority"])
    is_done = goal["status"] in ("已完成", "已搁置")
    title = escape(goal["content"][:60])
    if is_done:
        title = f"<s>{title}</s>"
    todos = get_todos_by_goal(goal["id"])
    done_count = sum(1 for t in todos if t["status"] == "已完成")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([5, 2, 1, 1])
        with c1:
            st.markdown(
                f"{priority_label}<span>{title}</span>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"{goal['category']} · 截止 {goal['deadline']} · {goal['status']}"
            )
        with c2:
            new_status = st.selectbox(
                "",
                GOAL_STATUSES,
                key=f"gs_{goal['id']}",
                index=GOAL_STATUSES.index(goal["status"]),
                label_visibility="collapsed",
            )
            if new_status != goal["status"]:
                update_annual_goal(goal["id"], status=new_status)
                st.rerun()
        with c3:
            if st.button("✍️", key=f"ge_{goal['id']}", help="编辑"):
                st.session_state["planning_goal_editing"] = goal["id"]
                st.rerun()
        with c4:
            if st.button("🗑️", key=f"gd_{goal['id']}", help="删除"):
                delete_annual_goal(goal["id"])
                st.rerun()

        if todos:
            progress = done_count / len(todos)
            st.caption(f"关联待办进度：{done_count} / {len(todos)}")
            st.progress(progress)
            with st.expander("查看关联待办", expanded=False):
                for todo in todos:
                    _render_goal_todo_readonly(todo)


def _render_goal_todo_readonly(todo: dict) -> None:
    is_done = todo["status"] == "已完成"
    status = "已完成" if is_done else "待办"
    priority_label = _priority_label(todo["priority"])
    content = escape(todo["content"])
    content_html = f"<s>{content}</s>" if is_done else content
    postponed = (
        f" · 延期 {todo.get('postpone_count', 0)} 次"
        if todo.get("postpone_count", 0) > 0
        else ""
    )
    st.markdown(
        f"{todo['target_date']} · {priority_label} · {status} · "
        f"{content_html}{postponed}",
        unsafe_allow_html=True,
    )


def _render_calendar_todos() -> None:
    year = st.session_state.get("planning_cal_year", datetime.now().year)
    month = st.session_state.get("planning_cal_month", datetime.now().month)

    _maybe_migrate_overdue_todos()
    _render_month_nav(year, month)
    migrated_count = int(st.session_state.pop("_planning_migrated_count", 0) or 0)
    if migrated_count > 0:
        st.info(f"已自动迁移 {migrated_count} 条过期待办至本月")

    todos = get_calendar_todos(year=year, month=month)
    day_map: dict[str, list[dict]] = defaultdict(list)
    for todo in todos:
        if todo["status"] == "已完成":
            continue
        day_map[todo["target_date"]].append(todo)
    activity_map = _load_month_activities(year, month)

    cols = st.columns(CALENDAR_COL_SPEC)
    for i, header in enumerate(WEEK_HEADERS):
        cols[i].markdown(
            f"<div style='text-align:center;font-weight:600'>{header}</div>",
            unsafe_allow_html=True,
        )

    selected_date = st.session_state.get("planning_cal_date")
    for week in cal_lib.monthcalendar(year, month):
        cols = st.columns(CALENDAR_COL_SPEC)
        for i, day_num in enumerate(week):
            with cols[i]:
                _render_calendar_cell(
                    year, month, day_num, selected_date, day_map, activity_map
                )

    _render_monthly_activity_stats(year, month)

    st.divider()
    selected_date = st.session_state.get("planning_cal_date")
    if selected_date:
        st.markdown(f"#### 📌 {selected_date} 的日历 & 日志")
        display_todos = [t for t in todos if t["target_date"] == selected_date]
        display_activities = activity_map.get(selected_date, [])
    else:
        st.markdown(f"#### 📋 {year} 年 {month} 月全部待办")
        display_todos = [t for t in todos if t["status"] != "已完成"]
        display_activities = []

    action_cols = st.columns([1, 1.4, 3.6] if selected_date else [1, 5])
    with action_cols[0]:
        if st.button(
            "➕ 新增待办",
            key="add_todo_btn",
            type="primary",
            use_container_width=True,
        ):
            _reset_todo_form_date()
            st.session_state["planning_activity_adding"] = False
            _close_all_todo_editors()
            _reset_activity_form()
            st.session_state["planning_todo_adding"] = True
            st.rerun()
    if selected_date:
        with action_cols[1]:
            if st.button(
                "返回月份视图",
                key="back_to_month_btn",
                use_container_width=True,
            ):
                st.session_state["planning_cal_date"] = None
                st.session_state["planning_todo_adding"] = False
                st.session_state["planning_activity_adding"] = False
                st.session_state["planning_activity_editing"] = None
                _close_all_todo_editors()
                _reset_todo_form_date()
                _reset_activity_form()
                st.rerun()

    _render_todo_form(selected_date, year, month)

    if selected_date:
        _render_selected_day_todos(display_todos)
        _render_daily_activities(selected_date, display_activities, display_todos)
        return

    if not display_todos:
        st.info("暂无待办。")
        return
    for todo in display_todos:
        _render_todo_row(todo)


def _render_month_nav(year: int, month: int) -> None:
    nav_cols = st.columns([1, 1.2, 1, 1, 1])
    with nav_cols[0]:
        if st.button("◀", key="cal_prev", use_container_width=True):
            if month == 1:
                _set_calendar_month(year - 1, 12)
            else:
                _set_calendar_month(year, month - 1)
    with nav_cols[1]:
        st.markdown(
            f"<h4 style='text-align:center;margin-top:.35rem'>{year} 年 {month} 月</h4>",
            unsafe_allow_html=True,
        )
    with nav_cols[2]:
        jump_year = st.number_input(
            "年份",
            min_value=1970,
            max_value=2100,
            value=int(year),
            step=1,
            key=f"cal_jump_year_{year}_{month}",
        )
    with nav_cols[3]:
        jump_month = st.selectbox(
            "月份",
            list(range(1, 13)),
            index=int(month) - 1,
            key=f"cal_jump_month_{year}_{month}",
            format_func=lambda m: f"{m} 月",
        )
    with nav_cols[4]:
        if st.button("▶", key="cal_next", use_container_width=True):
            if month == 12:
                _set_calendar_month(year + 1, 1)
            else:
                _set_calendar_month(year, month + 1)

    if int(jump_year) != year or int(jump_month) != month:
        _set_calendar_month(int(jump_year), int(jump_month))


def _set_calendar_month(year: int, month: int) -> None:
    st.session_state["planning_cal_year"] = year
    st.session_state["planning_cal_month"] = month
    st.session_state["planning_cal_date"] = None
    st.session_state["planning_activity_adding"] = False
    st.session_state["planning_activity_editing"] = None
    _reset_todo_form_date()
    _reset_activity_form()
    st.rerun()


def _maybe_migrate_overdue_todos() -> None:
    now = datetime.now()
    current_key = f"{now.year:04d}-{now.month:02d}"
    if st.session_state.get("_planning_migrated_month") == current_key:
        return
    migrated_count = migrate_overdue_todos(now.year, now.month)
    st.session_state["_planning_migrated_month"] = current_key
    st.session_state["_planning_migrated_count"] = migrated_count


def _reset_todo_form_date() -> None:
    st.session_state.pop("tf_date", None)


def _reset_todo_form() -> None:
    for key in ("tf_content", "tf_cat", "tf_pri", "tf_date", "tf_rec", "tf_goal"):
        st.session_state.pop(key, None)


def _reset_activity_form() -> None:
    for key in (
        "af_description",
        "af_category",
        "af_duration",
        "af_start_time",
        "af_end_time",
        "af_start_time_custom",
        "af_end_time_custom",
    ):
        st.session_state.pop(key, None)
    st.session_state.pop("_af_time_pair", None)
    st.session_state["planning_activity_prefill"] = None


def _reset_activity_edit_form(activity_id: str) -> None:
    for suffix in (
        "description",
        "category",
        "duration",
        "start_time",
        "end_time",
        "start_time_custom",
        "end_time_custom",
    ):
        st.session_state.pop(f"ae_{suffix}_{activity_id}", None)
    st.session_state.pop(f"_ae_time_pair_{activity_id}", None)


def _load_month_activities(year: int, month: int) -> dict[str, list[dict]]:
    activity_map: dict[str, list[dict]] = defaultdict(list)
    for day_num in range(1, cal_lib.monthrange(year, month)[1] + 1):
        d_str = f"{year:04d}-{month:02d}-{day_num:02d}"
        activities = get_daily_activities(d_str)
        if activities:
            activity_map[d_str] = activities
    return activity_map


def _render_calendar_cell(
    year: int,
    month: int,
    day_num: int,
    selected_date: str | None,
    day_map: dict[str, list[dict]],
    activity_map: dict[str, list[dict]],
) -> None:
    if day_num == 0:
        st.markdown(
            "<div style='min-height:8.9rem;border:1px solid transparent'></div>",
            unsafe_allow_html=True,
        )
        return

    d_str = f"{year:04d}-{month:02d}-{day_num:02d}"
    is_today = d_str == str(date.today())
    is_selected = d_str == selected_date
    day_todos = day_map.get(d_str, [])
    day_activities = activity_map.get(d_str, [])
    st.markdown(
        _calendar_cell_html(day_num, is_today, is_selected, day_todos, day_activities),
        unsafe_allow_html=True,
    )
    if st.button(
        "已选中" if is_selected else "查看",
        key=f"cal_{d_str}",
        type="primary" if is_selected else "secondary",
        use_container_width=True,
        help=f"选择 {d_str}",
    ):
        st.session_state["planning_cal_date"] = d_str
        st.session_state["planning_activity_adding"] = False
        st.session_state["planning_activity_editing"] = None
        _reset_activity_form()
        _reset_todo_form_date()
        st.rerun()


def _calendar_cell_html(
    day_num: int,
    is_today: bool,
    is_selected: bool,
    todos: list[dict],
    activities: list[dict],
) -> str:
    border = "#2563eb" if is_selected else "#d1d5db"
    background = "#eff6ff" if is_selected else "#ffffff"
    shadow = "0 0 0 1px rgba(37,99,235,.14)" if is_selected else "none"
    day_label = f"📍 {day_num}" if is_today else str(day_num)
    summaries = [_calendar_todo_summary(t) for t in todos[:MAX_DAY_TODOS]]
    if len(todos) > MAX_DAY_TODOS:
        summaries.append(
            "<div style='font-size:.68rem;color:#64748b;margin-top:.14rem;'>"
            f"+{len(todos) - MAX_DAY_TODOS} 更多</div>"
        )
    activity_html = ""
    if activities:
        separator = ""
        if summaries:
            separator = (
                "<div style='height:1px;background:#e5e7eb;margin:.32rem 0 .26rem;'>"
                "</div>"
            )
        activity_html = (
            f"{separator}<div style='font-size:.68rem;color:#334155;"
            "background:#f8fafc;border:1px solid #e2e8f0;border-radius:.35rem;"
            "padding:.08rem .28rem;display:inline-block;'>📝 事务｜"
            f"{len(activities)} 条</div>"
        )
    summaries_html = "".join(summaries) or "&nbsp;"
    return (
        f"<div style='min-height:7.35rem;border:1px solid {border};"
        f"background:{background};box-shadow:{shadow};border-radius:.45rem;"
        "padding:.42rem .46rem;overflow:hidden;'>"
        f"<div style='font-size:.86rem;font-weight:700;color:#111827;"
        f"margin-bottom:.32rem;'>{escape(day_label)}</div>"
        f"{summaries_html}{activity_html}</div>"
    )


def _calendar_todo_summary(todo: dict) -> str:
    priority_label = _priority_label(todo["priority"], compact=True)
    content = escape(todo["content"][:18])
    if todo["status"] == "已完成":
        content = f"<s>{content}</s>"
    return (
        "<div style='font-size:.69rem;line-height:1.38;margin:.16rem 0;"
        "color:#334155;white-space:normal;'>"
        f"{priority_label}<span>{content}</span></div>"
    )


def _priority_text(priority: str) -> str:
    return f"优先级：{priority}" if priority in PRIORITY_COLORS else "优先级：未定"


def _priority_label(priority: str, compact: bool = False) -> str:
    color, bg, border = PRIORITY_COLORS.get(
        priority, ("#475569", "#f8fafc", "#cbd5e1")
    )
    padding = "0.02rem 0.26rem" if compact else "0.08rem 0.42rem"
    font_size = "0.66rem" if compact else "0.78rem"
    margin_right = "0.18rem" if compact else "0.35rem"
    return (
        "<span style=\""
        "display:inline-flex;"
        "align-items:center;"
        f"padding:{padding};"
        "border-radius:0.35rem;"
        f"border:1px solid {border};"
        f"background:{bg};"
        f"color:{color};"
        f"font-size:{font_size};"
        "font-weight:600;"
        "line-height:1.35;"
        "white-space:nowrap;"
        "vertical-align:middle;"
        f"margin-right:{margin_right};"
        f"\">优先级：{escape(priority) if priority else '未定'}</span>"
    )


def _render_selected_day_todos(todos: list[dict]) -> None:
    st.markdown("#### ✅ 待办事宜")
    if not todos:
        st.info("当日暂无待办。")
        return
    for todo in todos:
        _render_todo_row(todo)


def _render_daily_activities(
    selected_date: str, activities: list[dict], todos: list[dict]
) -> None:
    st.markdown("#### 📝 今日事务")
    action_cols = st.columns([2, 4])
    with action_cols[0]:
        if st.button(
            "📝 记录今日事务",
            key="add_activity_btn",
            type="primary",
            use_container_width=True,
        ):
            _reset_activity_form()
            st.session_state["planning_todo_adding"] = False
            st.session_state["planning_activity_editing"] = None
            st.session_state["planning_activity_adding"] = True
            st.rerun()

    _render_activity_form(selected_date)

    if not activities:
        st.info("当日暂无事务记录。")
        return
    for activity in activities:
        _render_activity_row(activity)
    _render_daily_activity_stats(activities)
    _render_record_moment_prompt(selected_date, activities, todos)


def _activity_duration_totals(activities: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for activity in activities:
        duration = int(activity.get("duration") or 0)
        if duration <= 0:
            continue
        category = str(activity.get("category") or "未分类").strip() or "未分类"
        totals[category] += duration
    return dict(totals)


def _ordered_duration_items(stats: dict[str, int]) -> list[tuple[str, int]]:
    category_order = {category: i for i, category in enumerate(TODO_CATEGORIES)}
    return sorted(
        stats.items(),
        key=lambda item: (category_order.get(item[0], len(category_order)), item[0]),
    )


def _render_daily_activity_stats(activities: list[dict]) -> None:
    stats = _activity_duration_totals(activities)
    if not stats:
        return
    total = sum(stats.values())
    parts = [
        f"{category} {format_duration(minutes)}"
        for category, minutes in _ordered_duration_items(stats)
    ]
    parts.append(f"合计 {format_duration(total)}")
    st.caption("⏱ 今日：" + " · ".join(parts))


def _render_monthly_activity_stats(year: int, month: int) -> None:
    stats = get_monthly_activity_stats(year, month)
    with st.expander("📊 本月时长统计", expanded=False):
        if not stats:
            st.info("本月暂无事务记录")
            return
        for category, minutes in _ordered_duration_items(stats):
            cols = st.columns([2, 4])
            cols[0].markdown(f"**{category}**")
            cols[1].markdown(format_duration(minutes))
        st.divider()
        st.markdown(f"**合计：{format_duration(sum(stats.values()))}**")


def _render_activity_form(selected_date: str) -> None:
    if not st.session_state.get("planning_activity_adding"):
        return

    had_prefill = _consume_activity_prefill()

    with st.container(border=True):
        st.markdown("#### 📝 记录今日事务")
        if had_prefill:
            st.info("💡 也可以只填时长（分钟）来快速记录，时间段为选填")
        description = st.text_area("事务描述 *", key="af_description")
        category = st.selectbox("分类 *", TODO_CATEGORIES, key="af_category")
        start_time, start_error = _render_time_select("开始时间", "af_start_time")
        end_time, end_error = _render_time_select("结束时间", "af_end_time")
        computed_duration = _duration_between(start_time, end_time)
        if computed_duration is not None:
            current_pair = (start_time, end_time)
            if st.session_state.get("_af_time_pair") != current_pair:
                st.session_state["af_duration"] = computed_duration
                st.session_state["_af_time_pair"] = current_pair
        duration = st.number_input(
            "时长（分钟）",
            min_value=0,
            max_value=1440,
            value=0,
            step=5,
            key="af_duration",
        )

        ca, cb = st.columns(2)
        with ca:
            if st.button("💾 保存", key="af_save", type="primary"):
                time_error = _time_range_error(start_time, end_time)
                if start_error or end_error or time_error:
                    st.warning(start_error or end_error or time_error)
                elif description.strip():
                    create_daily_activity(
                        selected_date,
                        description.strip(),
                        category,
                        int(duration),
                        start_time=start_time,
                        end_time=end_time,
                    )
                    st.session_state["planning_activity_adding"] = False
                    st.session_state["planning_record_moment_date"] = selected_date
                    st.rerun()
                else:
                    st.warning("事务描述为必填项")
        with cb:
            if st.button("取消", key="af_cancel"):
                st.session_state["planning_activity_adding"] = False
                _reset_activity_form()
                st.rerun()


def _render_record_moment_prompt(
    selected_date: str, activities: list[dict], todos: list[dict]
) -> None:
    if st.session_state.get("planning_record_moment_date") != selected_date:
        return

    with st.container(border=True):
        st.markdown("📝 记录此刻的想法？")
        go_col, no_col, _ = st.columns([1, 1, 4])
        with go_col:
            if st.button("去记录", key=f"record_moment_go_{selected_date}", type="primary"):
                _go_record_moment(selected_date, activities, todos)
        with no_col:
            if st.button("不了", key=f"record_moment_no_{selected_date}"):
                st.session_state["planning_record_moment_date"] = None
                st.rerun()


def _go_record_moment(
    selected_date: str, activities: list[dict], todos: list[dict]
) -> None:
    model_id = st.session_state.get("llm_selected_model") or ""
    if not model_id:
        st.warning("请先在「系统」中选择一个 LLM 模型。")
        return

    user_prompt = PLANNING_RECORD_MOMENT_USER_TMPL.format(
        date=selected_date,
        activities=_format_activities_for_prompt(activities),
        todos=_format_todos_for_prompt(todos),
    )
    try:
        with st.spinner("正在整理今日记录草稿…"):
            draft_text = call_llm(
                PLANNING_RECORD_MOMENT_SYSTEM,
                user_prompt,
                model_id=model_id,
                expect_json=False,
                skill_name="planning_record_moment",
            )
    except Exception as exc:
        st.error(f"草稿生成失败：{exc}")
        return

    st.session_state["upload_prefill"] = {
        "description": str(draft_text).strip(),
        "topics": _infer_activity_topics(activities),
        "source": "planning",
    }
    st.session_state["planning_record_moment_date"] = None
    st.session_state["_nav_target"] = ("📝 记录台", "⬆️ 上传")
    st.rerun()


def _format_activities_for_prompt(activities: list[dict]) -> str:
    if not activities:
        return "无"
    lines = []
    for activity in activities:
        duration = int(activity.get("duration") or 0)
        duration_text = f"，时长 {duration} 分钟" if duration > 0 else ""
        lines.append(
            f"- [{activity.get('category', '未分类')}] "
            f"{activity.get('description', '').strip()}{duration_text}"
        )
    return "\n".join(lines)


def _format_todos_for_prompt(todos: list[dict]) -> str:
    if not todos:
        return "无"
    lines = []
    for todo in todos:
        status = "已完成" if todo.get("status") == "已完成" else "未完成"
        reflection = str(todo.get("reflection") or "").strip()
        reflection_text = f"，完成心得：{reflection}" if reflection else ""
        lines.append(
            f"- [{status}] [{todo.get('category', '未分类')}] "
            f"{todo.get('content', '').strip()}{reflection_text}"
        )
    return "\n".join(lines)


def _infer_activity_topics(activities: list[dict]) -> list[str]:
    topics = []
    for activity in activities:
        category = str(activity.get("category") or "").strip()
        if category and category not in topics:
            topics.append(category)
    return topics


def _render_activity_row(activity: dict) -> None:
    aid = activity["id"]
    duration = int(activity.get("duration") or 0)
    duration_text = f"{duration} 分钟" if duration > 0 else "未记录时长"
    time_range = _format_time_range(
        str(activity.get("start_time") or ""), str(activity.get("end_time") or "")
    )
    if time_range:
        duration_text = f"{time_range} · {duration_text}"
    description = escape(activity["description"])
    with st.container(border=True):
        c1, c2, c3 = st.columns([5, 1, 1])
        with c1:
            st.markdown(description, unsafe_allow_html=True)
            st.caption(f"{activity['category']} · {duration_text}")
        with c2:
            if st.button("编辑", key=f"ae_{aid}", help="编辑"):
                st.session_state["planning_activity_editing"] = aid
                st.session_state["planning_activity_adding"] = False
                _reset_activity_form()
                st.rerun()
        with c3:
            if st.button("🗑️", key=f"ad_{aid}", help="删除"):
                delete_daily_activity(aid)
                st.rerun()

        if st.session_state.get("planning_activity_editing") == aid:
            _render_activity_edit_form(activity)


def _render_activity_edit_form(activity: dict) -> None:
    aid = activity["id"]
    category_index = _option_index(TODO_CATEGORIES, activity.get("category"))
    with st.container(border=True):
        st.markdown("#### ✏️ 编辑事务")
        description = st.text_area(
            "事务描述 *",
            value=str(activity.get("description") or ""),
            key=f"ae_description_{aid}",
        )
        category = st.selectbox(
            "分类 *",
            TODO_CATEGORIES,
            index=category_index,
            key=f"ae_category_{aid}",
        )
        _ensure_time_select_default(f"ae_start_time_{aid}", activity.get("start_time"))
        _ensure_time_select_default(f"ae_end_time_{aid}", activity.get("end_time"))
        start_time, start_error = _render_time_select(
            "开始时间", f"ae_start_time_{aid}"
        )
        end_time, end_error = _render_time_select("结束时间", f"ae_end_time_{aid}")
        computed_duration = _duration_between(start_time, end_time)
        if computed_duration is not None:
            current_pair = (start_time, end_time)
            pair_key = f"_ae_time_pair_{aid}"
            if st.session_state.get(pair_key) != current_pair:
                st.session_state[f"ae_duration_{aid}"] = computed_duration
                st.session_state[pair_key] = current_pair
        duration = st.number_input(
            "时长（分钟）",
            min_value=0,
            max_value=1440,
            value=int(activity.get("duration") or 0),
            step=5,
            key=f"ae_duration_{aid}",
        )

        ca, cb = st.columns(2)
        with ca:
            if st.button("💾 保存", key=f"ae_save_{aid}", type="primary"):
                time_error = _time_range_error(start_time, end_time)
                if start_error or end_error or time_error:
                    st.warning(start_error or end_error or time_error)
                elif description.strip():
                    update_daily_activity(
                        aid,
                        description=description.strip(),
                        category=category,
                        duration=int(duration),
                        start_time=start_time,
                        end_time=end_time,
                    )
                    st.session_state["planning_activity_editing"] = None
                    _reset_activity_edit_form(aid)
                    st.rerun()
                else:
                    st.warning("事务描述为必填项")
        with cb:
            if st.button("取消", key=f"ae_cancel_{aid}"):
                st.session_state["planning_activity_editing"] = None
                _reset_activity_edit_form(aid)
                st.rerun()


def _ensure_time_select_default(key: str, value: str | None) -> None:
    if key in st.session_state:
        return
    value = str(value or "").strip()
    st.session_state[key] = (
        value if value in _time_options() else ("自定义…" if value else "")
    )
    if value and value not in _time_options():
        st.session_state[f"{key}_custom"] = value


def _render_time_select(label: str, key: str) -> tuple[str, str]:
    options = [""] + _time_options() + ["自定义…"]
    current = str(st.session_state.get(key) or "")
    index = options.index(current) if current in options else 0
    selected = st.selectbox(label, options, index=index, key=key)
    if selected != "自定义…":
        return selected, ""

    custom = st.text_input(
        f"{label}（HH:MM）",
        key=f"{key}_custom",
        placeholder="HH:MM",
    ).strip()
    if not custom:
        return "", ""
    if not _is_valid_time_text(custom):
        return "", f"{label}格式应为 HH:MM"
    return _normalize_time_text(custom), ""


def _time_options() -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 30)]


def _is_valid_time_text(value: str) -> bool:
    match = re.fullmatch(r"\d{1,2}:\d{2}", value.strip())
    if not match:
        return False
    hour_text, minute_text = value.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _normalize_time_text(value: str) -> str:
    hour_text, minute_text = value.strip().split(":", 1)
    return f"{int(hour_text):02d}:{int(minute_text):02d}"


def _duration_between(start_time: str, end_time: str) -> int | None:
    if not (start_time and end_time):
        return None
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
    except ValueError:
        return None
    delta_minutes = int((end - start).total_seconds() // 60)
    return delta_minutes if delta_minutes >= 0 else None


def _time_range_error(start_time: str, end_time: str) -> str:
    if start_time and end_time and _duration_between(start_time, end_time) is None:
        return "结束时间不能早于开始时间"
    return ""


def _format_time_range(start_time: str, end_time: str) -> str:
    if start_time and end_time:
        return f"{start_time}-{end_time}"
    return start_time or end_time


def _render_todo_form(selected_date: str | None, year: int, month: int) -> None:
    if not st.session_state.get("planning_todo_adding"):
        return

    linkable_goals = get_annual_goals(status_filter=["未开始", "进行中"])

    with st.container(border=True):
        st.markdown("#### ➕ 新增待办")
        content = st.text_area("待办内容 *", key="tf_content")
        category = st.selectbox("分类 *", TODO_CATEGORIES, key="tf_cat")
        priority = st.selectbox("优先级 *", TODO_PRIORITIES, key="tf_pri")
        default_date = (
            date.fromisoformat(selected_date) if selected_date else date(year, month, 1)
        )
        target_date = st.date_input("执行日期 *", value=default_date, key="tf_date")
        recurrence = st.selectbox("重复规则", TODO_RECURRENCES, key="tf_rec")

        goal_options = {None: "（不关联）"}
        goal_options.update({g["id"]: g["content"][:40] for g in linkable_goals})
        linked_goal = st.selectbox(
            "关联年度目标（选填）",
            options=list(goal_options.keys()),
            format_func=lambda k: goal_options[k],
            key="tf_goal",
        )

        ta, tb = st.columns(2)
        with ta:
            if st.button("💾 保存", key="tf_save", type="primary"):
                if content.strip():
                    create_calendar_todo(
                        content.strip(),
                        category,
                        priority,
                        str(target_date),
                        recurrence,
                        linked_goal_id=linked_goal,
                    )
                    st.session_state["planning_todo_adding"] = False
                    st.rerun()
                else:
                    st.warning("待办内容为必填项")
        with tb:
            if st.button("取消", key="tf_cancel"):
                st.session_state["planning_todo_adding"] = False
                _reset_todo_form()
                st.rerun()


def _render_todo_edit_form(todo: dict) -> None:
    tid = todo["id"]
    linkable_goals = get_annual_goals(status_filter=["未开始", "进行中"])
    linked_goal_id = todo.get("linked_goal_id")
    if linked_goal_id and not any(g["id"] == linked_goal_id for g in linkable_goals):
        linkable_goals.append({"id": linked_goal_id, "content": "当前关联目标"})

    category_index = _option_index(TODO_CATEGORIES, todo.get("category"))
    priority_index = _option_index(TODO_PRIORITIES, todo.get("priority"))
    recurrence_index = _option_index(TODO_RECURRENCES, todo.get("recurrence"))
    target_date = _parse_date(todo.get("target_date")) or date.today()

    with st.container(border=True):
        st.markdown("#### ✏️ 编辑待办")
        content = st.text_area(
            "待办内容 *", value=todo.get("content", ""), key=f"te_content_{tid}"
        )
        category = st.selectbox(
            "分类 *", TODO_CATEGORIES, index=category_index, key=f"te_cat_{tid}"
        )
        priority = st.selectbox(
            "优先级 *", TODO_PRIORITIES, index=priority_index, key=f"te_pri_{tid}"
        )
        new_date = st.date_input("执行日期 *", value=target_date, key=f"te_date_{tid}")
        recurrence = st.selectbox(
            "重复规则",
            TODO_RECURRENCES,
            index=recurrence_index,
            key=f"te_rec_{tid}",
        )

        goal_options = {None: "（不关联）"}
        goal_options.update({g["id"]: g["content"][:40] for g in linkable_goals})
        goal_ids = list(goal_options.keys())
        goal_index = goal_ids.index(linked_goal_id) if linked_goal_id in goal_ids else 0
        linked_goal = st.selectbox(
            "关联年度目标（选填）",
            options=goal_ids,
            index=goal_index,
            format_func=lambda k: goal_options[k],
            key=f"te_goal_{tid}",
        )

        ca, cb = st.columns(2)
        with ca:
            if st.button("💾 保存", key=f"te_save_{tid}", type="primary"):
                if content.strip():
                    update_calendar_todo(
                        tid,
                        content=content.strip(),
                        category=category,
                        priority=priority,
                        target_date=str(new_date),
                        recurrence=recurrence,
                        linked_goal_id=linked_goal,
                    )
                    _close_todo_editor(tid)
                    st.rerun()
                else:
                    st.warning("待办内容为必填项")
        with cb:
            if st.button("取消", key=f"te_cancel_{tid}"):
                _close_todo_editor(tid)
                st.rerun()


def _option_index(options: list[str], value: str | None) -> int:
    return options.index(value) if value in options else 0


def _render_todo_row(todo: dict) -> None:
    tid = todo["id"]
    is_done = todo["status"] == "已完成"
    priority_label = _priority_label(todo["priority"])
    content = escape(todo["content"])
    content_html = f"<s>{content}</s>" if is_done else content
    color_style = "color:gray;" if is_done else ""
    reflection_open = st.session_state.get("_reflection_open", {}).get(tid, False)
    postpone_open = st.session_state.get("_postpone_open", {}).get(tid, False)
    editing_open = st.session_state.get(f"_todo_editing_{tid}", False)

    with st.container(border=True):
        rc1, rc2, rc3, rc4 = st.columns([0.5, 5.5, 1, 1])
        with rc1:
            checked = st.checkbox(
                "",
                value=is_done,
                key=f"chk_{tid}",
                label_visibility="collapsed",
            )
            if checked and not is_done:
                reflection_state = st.session_state.get("_reflection_open", {})
                reflection_state[tid] = True
                st.session_state["_reflection_open"] = reflection_state
                reflection_open = True
            elif not checked and is_done:
                update_calendar_todo(tid, status="待办", reflection="")
                st.rerun()
        with rc2:
            st.markdown(
                f"{priority_label}<span style='{color_style}'>{content_html}</span>",
                unsafe_allow_html=True,
            )
            linked = " · 🔗 关联目标" if todo.get("linked_goal_id") else ""
            postponed = (
                f" · 延期 {todo.get('postpone_count', 0)} 次"
                if todo.get("postpone_count", 0) > 0
                else ""
            )
            st.caption(
                f"{todo['target_date']} · {todo['category']} · "
                f"{todo['recurrence']}{linked}{postponed}"
            )
            if st.button("编辑", key=f"te_{tid}", help="编辑"):
                _open_todo_editor(tid)
                st.rerun()
        with rc3:
            if not is_done and st.button("延期", key=f"tp_{tid}", help="延期"):
                postpone_state = st.session_state.get("_postpone_open", {})
                postpone_state[tid] = True
                st.session_state["_postpone_open"] = postpone_state
                postpone_open = True
        with rc4:
            if st.button("🗑️", key=f"td_{tid}", help="删除"):
                delete_calendar_todo(tid)
                st.rerun()

        if editing_open:
            _render_todo_edit_form(todo)

        if reflection_open:
            _render_reflection_box(tid)

        if postpone_open:
            _render_postpone_box(tid)

        if is_done and todo.get("reflection"):
            st.caption(f"💬 {todo['reflection']}")


def _open_todo_editor(todo_id: str) -> None:
    _close_all_todo_editors()
    st.session_state[f"_todo_editing_{todo_id}"] = True
    st.session_state["planning_todo_adding"] = False
    _close_reflection(todo_id)
    _close_postpone(todo_id)


def _close_todo_editor(todo_id: str) -> None:
    st.session_state.pop(f"_todo_editing_{todo_id}", None)


def _close_all_todo_editors() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("_todo_editing_"):
            st.session_state.pop(key, None)


def _render_reflection_box(todo_id: str) -> None:
    selected_date = st.session_state.get("planning_cal_date")
    if selected_date:
        _render_completion_activity_box(todo_id, selected_date)
        return

    with st.container(border=True):
        st.caption("🎉 完成了！记录一下心得吧（选填）")
        reflection = st.text_area(
            "完成心得",
            key=f"ref_{todo_id}",
            placeholder="这件事给我带来了...",
            label_visibility="collapsed",
        )
        ca, cb = st.columns(2)
        with ca:
            if st.button("✅ 确认完成", key=f"ref_ok_{todo_id}", type="primary"):
                _complete_todo_and_prefill_activity(todo_id, reflection)
        with cb:
            if st.button("跳过", key=f"ref_skip_{todo_id}"):
                _complete_todo_and_prefill_activity(todo_id, "")


def _render_completion_activity_box(todo_id: str, selected_date: str) -> None:
    with st.container(border=True):
        st.caption("🎉 完成了！选择时间并记录一下心得吧（选填）")
        time_cols = st.columns(2)
        with time_cols[0]:
            start_time = _render_completion_time_select(
                "开始时间", f"_compl_start_{todo_id}"
            )
        with time_cols[1]:
            end_time = _render_completion_time_select(
                "终止时间", f"_compl_end_{todo_id}"
            )

        computed_duration = _duration_between(start_time, end_time)
        if computed_duration is not None:
            st.caption(f"自动计算时长：{format_duration(computed_duration)}")

        reflection = st.text_area(
            "完成心得",
            key=f"ref_{todo_id}",
            placeholder="这件事给我带来了...",
        )
        ca, cb = st.columns(2)
        with ca:
            if st.button("✅ 确认完成", key=f"ref_ok_{todo_id}", type="primary"):
                if end_time and not start_time:
                    st.warning("请先选择起始时间")
                    return
                if start_time and end_time and computed_duration is None:
                    st.warning("终止时间不能早于起始时间")
                    return
                _complete_todo_with_activity_time(
                    todo_id,
                    selected_date,
                    reflection,
                    start_time,
                    end_time,
                    computed_duration,
                )
        with cb:
            if st.button("跳过", key=f"ref_skip_{todo_id}"):
                _complete_todo_only(todo_id, "")


def _render_completion_time_select(label: str, key: str) -> str:
    time_options = [""] + [f"{i:02d}" for i in range(24)]
    minute_options = [""] + [f"{i:02d}" for i in range(60)]
    st.markdown(f"**{label}**")
    hour_col, minute_col = st.columns(2)
    with hour_col:
        hour = st.selectbox(
            "小时",
            time_options,
            format_func=lambda value: value or "未选",
            key=f"{key}_hour",
        )
    with minute_col:
        minute = st.selectbox(
            "分钟",
            minute_options,
            format_func=lambda value: value or "未选",
            key=f"{key}_minute",
        )
    return f"{hour}:{minute}" if hour and minute else ""


def _complete_todo_with_activity_time(
    todo_id: str,
    selected_date: str,
    reflection: str,
    start_time: str,
    end_time: str,
    duration: int | None,
) -> None:
    todo = _find_todo_in_render_state(todo_id)
    complete_todo(todo_id, reflection)
    if todo and start_time:
        create_daily_activity(
            selected_date,
            str(todo.get("content") or "").strip(),
            str(todo.get("category") or "").strip(),
            duration=int(duration or 0),
            start_time=start_time,
            end_time=end_time or None,
        )
        st.session_state["planning_record_moment_date"] = selected_date
    _close_reflection(todo_id)
    _reset_completion_time(todo_id)
    st.rerun()


def _complete_todo_only(todo_id: str, reflection: str) -> None:
    complete_todo(todo_id, reflection)
    _close_reflection(todo_id)
    _reset_completion_time(todo_id)
    st.rerun()


def _complete_todo_and_prefill_activity(todo_id: str, reflection: str) -> None:
    todo = _find_todo_in_render_state(todo_id)
    complete_todo(todo_id, reflection)
    _close_reflection(todo_id)
    if todo:
        _reset_activity_form()
        if not st.session_state.get("planning_activity_adding"):
            st.session_state["planning_activity_adding"] = True
        st.session_state["planning_todo_adding"] = False
        target_date = str(todo.get("target_date") or "").strip()
        if target_date:
            st.session_state["planning_cal_date"] = target_date
        st.session_state["planning_activity_prefill"] = {
            "description": str(todo.get("content") or "").strip(),
            "category": str(todo.get("category") or "").strip(),
        }
    st.rerun()


def _find_todo_in_render_state(todo_id: str) -> dict | None:
    year = st.session_state.get("planning_cal_year", datetime.now().year)
    month = st.session_state.get("planning_cal_month", datetime.now().month)
    for todo in get_calendar_todos(year=year, month=month):
        if todo["id"] == todo_id:
            return todo
    return None


def _consume_activity_prefill() -> bool:
    prefill = st.session_state.get("planning_activity_prefill")
    if not isinstance(prefill, dict):
        return False

    description = str(prefill.get("description") or "").strip()
    category = str(prefill.get("category") or "").strip()
    if description:
        st.session_state["af_description"] = description
    if category in TODO_CATEGORIES:
        st.session_state["af_category"] = category
    st.session_state["planning_activity_prefill"] = None
    return True


def _close_reflection(todo_id: str) -> None:
    reflection_state = st.session_state.get("_reflection_open", {})
    reflection_state.pop(todo_id, None)
    st.session_state["_reflection_open"] = reflection_state
    _reset_completion_time(todo_id)


def _reset_completion_time(todo_id: str) -> None:
    for suffix in ("start", "end"):
        st.session_state.pop(f"_compl_{suffix}_{todo_id}_hour", None)
        st.session_state.pop(f"_compl_{suffix}_{todo_id}_minute", None)


def _render_postpone_box(todo_id: str) -> None:
    with st.container(border=True):
        st.caption("选择延期天数")
        days = st.number_input(
            "延期天数",
            min_value=1,
            max_value=365,
            value=1,
            step=1,
            key=f"postpone_days_{todo_id}",
            label_visibility="collapsed",
        )
        ca, cb = st.columns(2)
        with ca:
            if st.button("确认延期", key=f"postpone_ok_{todo_id}", type="primary"):
                postpone_todo(todo_id, int(days))
                _close_postpone(todo_id)
                st.rerun()
        with cb:
            if st.button("取消", key=f"postpone_cancel_{todo_id}"):
                _close_postpone(todo_id)
                st.rerun()


def _close_postpone(todo_id: str) -> None:
    postpone_state = st.session_state.get("_postpone_open", {})
    postpone_state.pop(todo_id, None)
    st.session_state["_postpone_open"] = postpone_state


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
