# Task #18 — UI：月度日历待办 Tab

## 目标

实现「规划控制台」的月度日历待办子页，包含：月份导航、日历网格（优先级色标）、待办列表（Checkbox + 复盘弹窗）、新增待办表单（含关联年度目标）、视觉优先级与完成态反馈。

## 依赖

**必须在 task-16 和 task-17 均合并后执行。**

## 必读契约

- `docs/api/core.md` # `calendar_todos` 相关函数（task-16 新增）
- `docs/api/core.md` # `annual_goals` 相关函数（task-16 新增，用于关联下拉框）
- `docs/api/components.md` # `tab_planning.py` 节（task-17 新增的骨架结构）

## 改动范围

- **修改**：`components/tab_planning.py`（替换 `_render_calendar_todos` stub，完整实现）
- **修改**：`core/state.py`（新增日历相关 session_state 键）
- **更新**：`docs/api/components.md`（更新 `tab_planning.py` 节）
- **不许碰**：`core/db_manager.py` / `app.py` / 其他组件

## 实现要点

### 1. `core/state.py` 新增键

```python
"planning_cal_year":      datetime.now().year,
"planning_cal_month":     datetime.now().month,
"planning_cal_date":      None,           # 当前选中的日期字符串 YYYY-MM-DD
"planning_todo_adding":   False,          # 是否显示新增表单
"_reflection_open":       {},             # {todo_id: True} 复盘弹窗开关
```

`datetime` import 已在 state.py 中，如未引入则补 `from datetime import datetime`。

### 2. 月份导航

```python
from core.db_manager import (
    get_calendar_todos, create_calendar_todo, complete_todo,
    update_calendar_todo, delete_calendar_todo,
    get_annual_goals,
    TODO_CATEGORIES, TODO_RECURRENCES, TODO_PRIORITIES,
)
import calendar as cal_lib
from datetime import date, datetime

year  = st.session_state.get("planning_cal_year",  datetime.now().year)
month = st.session_state.get("planning_cal_month", datetime.now().month)

nc1, nc2, nc3 = st.columns([1, 3, 1])
with nc1:
    if st.button("◀", key="cal_prev"):
        if month == 1:
            st.session_state["planning_cal_year"]  = year - 1
            st.session_state["planning_cal_month"] = 12
        else:
            st.session_state["planning_cal_month"] = month - 1
        st.session_state["planning_cal_date"] = None
        st.rerun()
with nc2:
    st.markdown(f"<h4 style='text-align:center'>{year} 年 {month} 月</h4>",
                unsafe_allow_html=True)
with nc3:
    if st.button("▶", key="cal_next"):
        if month == 12:
            st.session_state["planning_cal_year"]  = year + 1
            st.session_state["planning_cal_month"] = 1
        else:
            st.session_state["planning_cal_month"] = month + 1
        st.session_state["planning_cal_date"] = None
        st.rerun()
```

### 3. 日历网格

```python
PRIORITY_BADGE = {"高": "🔴", "中": "🟡", "低": "🟢"}

todos = get_calendar_todos(year=year, month=month)

# 按日期分组（仅精确日期匹配，重复任务显示在 target_date 当天）
from collections import defaultdict
day_map: dict[str, list] = defaultdict(list)
for t in todos:
    day_map[t["target_date"]].append(t)

# 星期标题
headers = ["一", "二", "三", "四", "五", "六", "日"]
cols = st.columns(7)
for i, h in enumerate(headers):
    cols[i].markdown(f"**{h}**")

# 日历网格
month_cal = cal_lib.monthcalendar(year, month)
selected_date = st.session_state.get("planning_cal_date")

for week in month_cal:
    cols = st.columns(7)
    for i, day_num in enumerate(week):
        with cols[i]:
            if day_num == 0:
                st.write(" ")
                continue
            d_str = f"{year:04d}-{month:02d}-{day_num:02d}"
            is_today   = d_str == str(date.today())
            is_selected = d_str == selected_date
            day_todos  = day_map.get(d_str, [])
            
            # 日期按钮
            label = f"**{day_num}**" if is_today else str(day_num)
            btn_type = "primary" if is_selected else "secondary"
            if st.button(label, key=f"cal_{d_str}", type=btn_type,
                         use_container_width=True):
                st.session_state["planning_cal_date"] = d_str
                st.rerun()
            
            # 优先级色标（最多显示 3 个）
            if day_todos:
                badges = "".join(PRIORITY_BADGE.get(t["priority"], "·")
                                 for t in day_todos[:3])
                if len(day_todos) > 3:
                    badges += f"+{len(day_todos)-3}"
                st.caption(badges)
```

### 4. 待办列表（选中日期）

```python
selected_date = st.session_state.get("planning_cal_date")
st.divider()

if selected_date:
    st.markdown(f"#### 📌 {selected_date} 的待办")
else:
    st.markdown(f"#### 📋 {year} 年 {month} 月 全部待办")

# 过滤显示
display_todos = [t for t in todos if t["target_date"] == selected_date] \
                if selected_date else todos

if st.button("➕ 新增待办", key="add_todo_btn", type="primary"):
    st.session_state["planning_todo_adding"] = True
    st.rerun()

_render_todo_form(selected_date, year, month)   # 见下一节

for t in display_todos:
    _render_todo_row(t)
```

### 5. `_render_todo_row(t)` — 单条待办（含复盘钩子）

```python
def _render_todo_row(t: dict) -> None:
    tid      = t["id"]
    is_done  = t["status"] == "已完成"
    badge    = PRIORITY_BADGE.get(t["priority"], "")
    content_md = f"~~{t['content']}~~" if is_done else t["content"]
    color_style = "color:gray;" if is_done else ""

    reflection_open = st.session_state.get("_reflection_open", {}).get(tid, False)

    with st.container(border=True):
        rc1, rc2, rc3 = st.columns([0.5, 6, 1])
        with rc1:
            checked = st.checkbox("", value=is_done, key=f"chk_{tid}",
                                  label_visibility="collapsed")
            if checked and not is_done:
                # 拦截：开启复盘弹窗
                ro = st.session_state.get("_reflection_open", {})
                ro[tid] = True
                st.session_state["_reflection_open"] = ro
                st.rerun()
            elif not checked and is_done:
                update_calendar_todo(tid, status="待办", reflection="")
                st.rerun()
        with rc2:
            st.markdown(
                f"<span style='{color_style}'>{badge} {content_md}</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"{t['category']}　{t['recurrence']}"
                       + (f"　🔗 关联目标" if t.get("linked_goal_id") else ""))
        with rc3:
            if st.button("🗑️", key=f"td_{tid}", help="删除"):
                delete_calendar_todo(tid)
                st.rerun()

        # 复盘弹窗
        if reflection_open:
            with st.container(border=True):
                st.caption("🎉 完成了！记录一下心得吧（选填）")
                reflection = st.text_area("完成心得", key=f"ref_{tid}",
                                          placeholder="这件事给我带来了……",
                                          label_visibility="collapsed")
                ca, cb = st.columns(2)
                with ca:
                    if st.button("✅ 确认完成", key=f"ref_ok_{tid}", type="primary"):
                        complete_todo(tid, reflection)
                        ro = st.session_state.get("_reflection_open", {})
                        ro.pop(tid, None)
                        st.session_state["_reflection_open"] = ro
                        st.rerun()
                with cb:
                    if st.button("跳过", key=f"ref_skip_{tid}"):
                        complete_todo(tid, "")
                        ro = st.session_state.get("_reflection_open", {})
                        ro.pop(tid, None)
                        st.session_state["_reflection_open"] = ro
                        st.rerun()

        # 已完成心得展示
        if is_done and t.get("reflection"):
            st.caption(f"💬 {t['reflection']}")
```

### 6. `_render_todo_form(selected_date, year, month)` — 新增待办表单

仅在 `st.session_state["planning_todo_adding"] == True` 时渲染：

```python
def _render_todo_form(selected_date, year, month):
    if not st.session_state.get("planning_todo_adding"):
        return

    # 获取可关联的目标（仅"未开始"/"进行中"）
    linkable_goals = get_annual_goals(status_filter=["未开始", "进行中"])

    with st.container(border=True):
        st.markdown("#### ➕ 新增待办")
        content   = st.text_area("待办内容 *", key="tf_content")
        category  = st.selectbox("分类 *", TODO_CATEGORIES, key="tf_cat")
        priority  = st.selectbox("优先级 *", TODO_PRIORITIES, key="tf_pri")
        
        default_date = date.fromisoformat(selected_date) \
                       if selected_date else date(year, month, 1)
        target_date  = st.date_input("执行日期 *", value=default_date, key="tf_date")
        recurrence   = st.selectbox("重复规则", TODO_RECURRENCES, key="tf_rec")

        goal_options  = {None: "（不关联）"} | {g["id"]: g["content"][:40]
                                                for g in linkable_goals}
        linked_goal   = st.selectbox("关联年度目标（选填）",
                                     options=list(goal_options.keys()),
                                     format_func=lambda k: goal_options[k],
                                     key="tf_goal")

        ta, tb = st.columns(2)
        with ta:
            if st.button("💾 保存", key="tf_save", type="primary"):
                if content.strip():
                    create_calendar_todo(
                        content.strip(), category, priority,
                        str(target_date), recurrence,
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
```

## 不要做

- 不要实现重复任务自动生成（recurrence 只存储展示）
- 不要修改 `app.py`（Tab 已由 task-17 添加）
- `_reflection_open` 使用 dict 而非多个独立 key，避免 session_state 膨胀

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 月份导航（◀/▶）正确切换年月，日历网格正确渲染
- [ ] 有待办的日期显示 🔴/🟡/🟢 色标，今日高亮
- [ ] 点击日期 → 下方列表仅显示该日任务
- [ ] 新增待办（含关联目标）→ 出现在对应日期格与列表中
- [ ] 勾选 Checkbox → 弹出复盘输入框 → 确认后状态变"已完成"，显示删除线
- [ ] 跳过复盘 → 直接完成，不填心得
- [ ] 已完成心得在任务下方展示
- [ ] 高优先级任务 🔴 标记醒目，已完成任务灰色+删除线
- [ ] 关联年度目标下拉框仅显示"未开始"/"进行中"的目标
- [ ] `docs/api/components.md` 的 `tab_planning.py` 节已补全日历功能说明
- [ ] commit 符合规范（建议 `feat(tab_planning): 月度日历待办 Tab · 关联 #18`）
- [ ] 在 worktree 分支提交，未 push main

## 架构师备注

- 日历网格用 `calendar.monthcalendar()` 标准库，0 代表空白格
- 复盘弹窗用 `_reflection_open: dict` 存在 session_state，key 为 todo_id，避免多条并发展开
- 重复任务本期只在 `target_date` 当天显示，`get_calendar_todos` 的 recurrence 过滤逻辑由 task-16 实现的 SQL 处理，UI 层不需要额外计算
- 日历格子点击用 `st.button` 而非自定义组件，在 Streamlit 标准能力范围内实现
