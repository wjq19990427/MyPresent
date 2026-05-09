"""规划控制台 Tab：年度规划 + 日历 & 日志。"""
from __future__ import annotations

import calendar as cal_lib
from collections import defaultdict
from datetime import date, datetime
from html import escape

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
    get_todos_by_goal,
    postpone_todo,
    add_goal_category,
    create_daily_activity,
    delete_goal_category,
    update_annual_goal,
    update_calendar_todo,
)


PRIORITY_COLORS = {
    "高": ("#b91c1c", "#fee2e2", "#fecaca"),
    "中": ("#a16207", "#fef3c7", "#fde68a"),
    "低": ("#15803d", "#dcfce7", "#bbf7d0"),
}
CALENDAR_COL_SPEC = [1, 1, 1, 1, 1, 1, 1]
WEEK_HEADERS = ["一", "二", "三", "四", "五", "六", "日"]
MAX_DAY_TODOS = 3


def render_planning_tab() -> None:
    sub1, sub2 = st.tabs(["🎯 年度规划", "📅 日历 & 日志"])
    with sub1:
        _render_annual_goals()
    with sub2:
        _render_calendar_todos()


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

    _render_month_nav(year, month)

    todos = get_calendar_todos(year=year, month=month)
    day_map: dict[str, list[dict]] = defaultdict(list)
    for todo in todos:
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

    st.divider()
    selected_date = st.session_state.get("planning_cal_date")
    if selected_date:
        st.markdown(f"#### 📌 {selected_date} 的日历 & 日志")
        display_todos = [t for t in todos if t["target_date"] == selected_date]
        display_activities = activity_map.get(selected_date, [])
    else:
        st.markdown(f"#### 📋 {year} 年 {month} 月全部待办")
        display_todos = todos
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
                _reset_todo_form_date()
                _reset_activity_form()
                st.rerun()

    _render_todo_form(selected_date, year, month)

    if selected_date:
        _render_selected_day_todos(display_todos)
        _render_daily_activities(selected_date, display_activities)
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
    _reset_todo_form_date()
    _reset_activity_form()
    st.rerun()


def _reset_todo_form_date() -> None:
    st.session_state.pop("tf_date", None)


def _reset_activity_form() -> None:
    for key in ("af_description", "af_category", "af_duration"):
        st.session_state.pop(key, None)


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
            "<div style='min-height:7.5rem;border:1px solid transparent'></div>",
            unsafe_allow_html=True,
        )
        return

    d_str = f"{year:04d}-{month:02d}-{day_num:02d}"
    is_today = d_str == str(date.today())
    is_selected = d_str == selected_date
    day_todos = day_map.get(d_str, [])
    day_activities = activity_map.get(d_str, [])
    if st.button(
        _calendar_cell_label(day_num, is_today, day_todos, day_activities),
        key=f"cal_{d_str}",
        type="primary" if is_selected else "secondary",
        use_container_width=True,
        help=f"选择 {d_str}",
    ):
        st.session_state["planning_cal_date"] = d_str
        st.session_state["planning_activity_adding"] = False
        _reset_activity_form()
        _reset_todo_form_date()
        st.rerun()


def _calendar_cell_label(
    day_num: int,
    is_today: bool,
    todos: list[dict],
    activities: list[dict],
) -> str:
    day_label = f"📍 **{day_num}**" if is_today else str(day_num)
    summaries = [_calendar_todo_summary(t) for t in todos[:MAX_DAY_TODOS]]
    if len(todos) > MAX_DAY_TODOS:
        summaries.append(f"+{len(todos) - MAX_DAY_TODOS} 更多")
    if activities:
        summaries.append(f"📝 事务 {len(activities)} 条")
    if not summaries:
        summaries = [" "]
    return "\n\n".join([day_label, *summaries])


def _calendar_todo_summary(todo: dict) -> str:
    priority_text = _priority_text(todo["priority"])
    content = todo["content"][:18]
    if todo["status"] == "已完成":
        content = f"~~{content}~~"
    return f"{priority_text} {content}"


def _priority_text(priority: str) -> str:
    return f"优先级：{priority}" if priority in PRIORITY_COLORS else "优先级：未定"


def _priority_label(priority: str) -> str:
    color, bg, border = PRIORITY_COLORS.get(
        priority, ("#475569", "#f8fafc", "#cbd5e1")
    )
    return (
        "<span style=\""
        "display:inline-flex;"
        "align-items:center;"
        "padding:0.08rem 0.42rem;"
        "border-radius:0.35rem;"
        f"border:1px solid {border};"
        f"background:{bg};"
        f"color:{color};"
        "font-size:0.78rem;"
        "font-weight:600;"
        "line-height:1.35;"
        "white-space:nowrap;"
        "vertical-align:middle;"
        "margin-right:0.35rem;"
        f"\">优先级：{escape(priority) if priority else '未定'}</span>"
    )


def _render_selected_day_todos(todos: list[dict]) -> None:
    st.markdown("#### ✅ 待办事宜")
    if not todos:
        st.info("当日暂无待办。")
        return
    for todo in todos:
        _render_todo_row(todo)


def _render_daily_activities(selected_date: str, activities: list[dict]) -> None:
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
            st.session_state["planning_activity_adding"] = True
            st.rerun()

    _render_activity_form(selected_date)

    if not activities:
        st.info("当日暂无事务记录。")
        return
    for activity in activities:
        _render_activity_row(activity)


def _render_activity_form(selected_date: str) -> None:
    if not st.session_state.get("planning_activity_adding"):
        return

    with st.container(border=True):
        st.markdown("#### 📝 记录今日事务")
        description = st.text_area("事务描述 *", key="af_description")
        category = st.selectbox("分类 *", TODO_CATEGORIES, key="af_category")
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
                if description.strip():
                    create_daily_activity(
                        selected_date,
                        description.strip(),
                        category,
                        int(duration),
                    )
                    st.session_state["planning_activity_adding"] = False
                    st.rerun()
                else:
                    st.warning("事务描述为必填项")
        with cb:
            if st.button("取消", key="af_cancel"):
                st.session_state["planning_activity_adding"] = False
                st.rerun()


def _render_activity_row(activity: dict) -> None:
    duration = int(activity.get("duration") or 0)
    duration_text = f"{duration} 分钟" if duration > 0 else "未记录时长"
    description = escape(activity["description"])
    with st.container(border=True):
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(description, unsafe_allow_html=True)
            st.caption(f"{activity['category']} · {duration_text}")
        with c2:
            if st.button("🗑️", key=f"ad_{activity['id']}", help="删除"):
                delete_daily_activity(activity["id"])
                st.rerun()


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
                st.rerun()


def _render_todo_row(todo: dict) -> None:
    tid = todo["id"]
    is_done = todo["status"] == "已完成"
    priority_label = _priority_label(todo["priority"])
    content = escape(todo["content"])
    content_html = f"<s>{content}</s>" if is_done else content
    color_style = "color:gray;" if is_done else ""
    reflection_open = st.session_state.get("_reflection_open", {}).get(tid, False)
    postpone_open = st.session_state.get("_postpone_open", {}).get(tid, False)

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

        if reflection_open:
            _render_reflection_box(tid)

        if postpone_open:
            _render_postpone_box(tid)

        if is_done and todo.get("reflection"):
            st.caption(f"💬 {todo['reflection']}")


def _render_reflection_box(todo_id: str) -> None:
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
                complete_todo(todo_id, reflection)
                _close_reflection(todo_id)
                st.rerun()
        with cb:
            if st.button("跳过", key=f"ref_skip_{todo_id}"):
                complete_todo(todo_id, "")
                _close_reflection(todo_id)
                st.rerun()


def _close_reflection(todo_id: str) -> None:
    reflection_state = st.session_state.get("_reflection_open", {})
    reflection_state.pop(todo_id, None)
    st.session_state["_reflection_open"] = reflection_state


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
