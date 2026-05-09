# Task #17 — UI：年度规划 Tab

## 目标

实现「规划控制台」的年度规划子页，支持目标的新增、查看、状态更新、删除，并提供优先级颜色标识与分类/状态筛选。

## 依赖

**必须在 task-16 合并后执行。**

## 必读契约

- `docs/api/core.md` # `db_manager.py` 节中 `annual_goals` 相关函数（task-16 新增）
- `docs/api/components.md` # `tab_recycle.py` 节（参照类似的列表+操作布局风格）

## 改动范围

- **新建**：`components/tab_planning.py`（包含年度规划与日历待办的容器函数，task-18 在此文件追加）
- **修改**：`app.py`（新增第 7 个 Tab「📋 规划控制台」）
- **修改**：`core/state.py`（新增 planning 相关 session_state 键）
- **更新**：`docs/api/components.md`（追加 `tab_planning.py` 节）
- **不许碰**：`core/db_manager.py` / `skills/` / 其他组件

## 实现要点

### 1. `core/state.py` 新增键

```python
"planning_sub_tab":       "annual",      # "annual" | "calendar"
"planning_goal_editing":  None,          # 当前编辑中的 goal_id
"planning_goal_filter_status": [],       # 状态筛选
"planning_goal_filter_cat":    [],       # 分类筛选
```

### 2. `components/tab_planning.py` 骨架

```python
"""规划控制台 Tab — 年度规划 + 月度日历待办。"""
from __future__ import annotations
import streamlit as st

def render_planning_tab() -> None:
    sub1, sub2 = st.tabs(["🎯 年度规划", "📅 月度日历待办"])
    with sub1:
        _render_annual_goals()
    with sub2:
        st.info("📅 日历待办功能即将上线（task-18）")
```

### 3. `_render_annual_goals()` 实现

#### 优先级颜色映射

```python
from core.db_manager import (
    get_annual_goals, create_annual_goal, update_annual_goal, delete_annual_goal,
    GOAL_CATEGORIES, GOAL_STATUSES, GOAL_PRIORITIES,
)

PRIORITY_BADGE = {"高": "🔴", "中": "🟡", "低": "🟢"}
STATUS_COLOR   = {
    "未开始": "",
    "进行中": "**",      # 加粗
    "已完成": "~~",      # 删除线（markdown）
    "已搁置": "~~",
}
```

#### 筛选栏（页面顶部）

```python
fc1, fc2, fc3 = st.columns([3, 3, 2])
with fc1:
    f_status = st.multiselect("状态筛选", GOAL_STATUSES, key="planning_goal_filter_status")
with fc2:
    f_cat = st.multiselect("分类筛选", GOAL_CATEGORIES, key="planning_goal_filter_cat")
with fc3:
    if st.button("➕ 新增目标", key="add_goal_btn", type="primary"):
        st.session_state["planning_goal_editing"] = "NEW"
        st.rerun()
```

#### 新增 / 编辑表单（内联展示）

当 `planning_goal_editing == "NEW"` 或某个 `goal_id` 时：

```python
with st.container(border=True):
    st.markdown("#### ✏️ " + ("新增目标" if is_new else "编辑目标"))
    content  = st.text_area("目标内容 *", value=g.get("content",""), key="ge_content")
    cat_sel  = st.selectbox("规划维度 *", GOAL_CATEGORIES, key="ge_cat",
                            index=GOAL_CATEGORIES.index(g.get("category", GOAL_CATEGORIES[0])))
    # 自定义分类
    if cat_sel == "自定义":
        cat_custom = st.text_input("自定义维度名称", key="ge_cat_custom",
                                   value="" if is_new else g.get("category",""))
        category = cat_custom.strip() or "自定义"
    else:
        category = cat_sel
    priority = st.selectbox("优先级 *", GOAL_PRIORITIES, key="ge_priority",
                            index=GOAL_PRIORITIES.index(g.get("priority", "中")))
    deadline = st.date_input("截止日期 *", key="ge_deadline")
    status   = st.selectbox("状态", GOAL_STATUSES, key="ge_status",
                            index=GOAL_STATUSES.index(g.get("status","未开始")))
    ca, cb = st.columns(2)
    with ca:
        if st.button("💾 保存", key="ge_save", type="primary"):
            if content.strip() and deadline:
                if is_new:
                    create_annual_goal(content.strip(), category, priority,
                                       str(deadline))
                else:
                    update_annual_goal(g["id"], content=content.strip(),
                                       category=category, priority=priority,
                                       deadline=str(deadline), status=status)
                st.session_state["planning_goal_editing"] = None
                st.rerun()
            else:
                st.warning("目标内容和截止日期为必填项")
    with cb:
        if st.button("取消", key="ge_cancel"):
            st.session_state["planning_goal_editing"] = None
            st.rerun()
```

#### 目标列表

```python
goals = get_annual_goals(status_filter=f_status or None)
if f_cat:
    goals = [g for g in goals if g["category"] in f_cat]

if not goals:
    st.info("暂无目标，点击「➕ 新增目标」开始规划。")
    return

for g in goals:
    badge   = PRIORITY_BADGE.get(g["priority"], "")
    is_done = g["status"] in ("已完成", "已搁置")
    title   = f"~~{g['content'][:60]}~~" if is_done else g["content"][:60]

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([5, 2, 1, 1])
        with c1:
            st.markdown(f"{badge} {title}")
            st.caption(f"{g['category']}　·　截止 {g['deadline']}　·　{g['status']}")
        with c2:
            new_status = st.selectbox("", GOAL_STATUSES, key=f"gs_{g['id']}",
                                      index=GOAL_STATUSES.index(g["status"]),
                                      label_visibility="collapsed")
            if new_status != g["status"]:
                update_annual_goal(g["id"], status=new_status)
                st.rerun()
        with c3:
            if st.button("✏️", key=f"ge_{g['id']}", help="编辑"):
                st.session_state["planning_goal_editing"] = g["id"]
                st.rerun()
        with c4:
            if st.button("🗑️", key=f"gd_{g['id']}", help="删除"):
                delete_annual_goal(g["id"])
                st.rerun()
```

### 4. `app.py` 新增 Tab

```python
from components.tab_planning import render_planning_tab

tab1, ..., tab7 = st.tabs([
    "🗂️ 记录舱（上传）",
    "🖼️ 灵感墙（待处理）",
    "📚 已归档",
    "🔍 搜索",
    "📊 运行看板",
    "🗑️ 回收站",
    "📋 规划控制台",
])
# ...
with tab7:
    render_planning_tab()
```

## 不要做

- 不要在此任务中实现日历待办（task-18 负责）
- 不要直接在 app.py 内写 planning 逻辑
- 不要硬编码分类/优先级字符串——从 `db_manager` 导入枚举常量

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动，顶部出现第 7 个「📋 规划控制台」Tab
- [ ] 新增目标（含自定义分类） → 出现在列表中，优先级颜色正确
- [ ] 下拉直接改状态 → 已完成/已搁置状态目标显示删除线灰色
- [ ] 🔴/🟡/🟢 优先级标记正确显示
- [ ] 筛选状态/分类 → 列表正确过滤
- [ ] 编辑目标 → 字段回填，保存后更新
- [ ] 删除目标 → 从列表消失
- [ ] `docs/api/components.md` 追加 `tab_planning.py` 节
- [ ] commit 符合规范（建议 `feat(tab_planning): 年度规划 Tab · 关联 #17`）
- [ ] 在 worktree 分支提交，未 push main
