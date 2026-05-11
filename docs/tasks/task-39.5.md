# Task #39.5 — 规划台时长统计（今日 + 月度）

## 目标

在规划台日历视图中，动态展示两个维度的事务时长统计：① 当日各分类的时长汇总，随事务列表增删实时更新；② 当月各分类的累计时长，随月份切换自动刷新。时长格式统一为「X小时Y分钟」。

**可与 task-38 并行，但两者都改 `tab_planning.py`，合并时注意冲突。**

## 必读契约

- `docs/api/components.md` # tab_planning.py 节
- `docs/api/core.md` # db_manager.py::Daily Activities 节

## 改动范围

- **修改**：`core/db_manager.py`（新增月度统计查询函数）
- **修改**：`components/tab_planning.py`（新增两处统计展示）
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/components.md`
- **不许碰**：`daily_activities` 表结构、现有 CRUD 函数

## 接口约定

### db_manager.py 新增函数

`get_monthly_activity_stats(year: int, month: int) -> dict[str, int]`
- 返回：`{category: total_minutes}`，仅含有记录的分类，无记录返回空 dict
- 查询 `daily_activities` 中 `date` 在指定年月内的所有行，按 `category` 分组求 `SUM(duration)`
- 副作用：无

### tab_planning.py 新增展示逻辑

#### 今日时长统计

**位置**：在当日事务列表渲染完毕之后、「记录此刻想法」提示之前。

**触发条件**：仅在 `selected_date` 已选且当日 `activities` 列表非空时渲染。

**展示内容**：一行紧凑的统计摘要，格式：
```
⏱ 今日：工作 1小时30分钟 · 学习 45分钟 · 生活 20分钟
```
- 按分类列出，跳过 `duration == 0` 的条目
- 末尾显示合计：`共 X小时Y分钟`

#### 月度时长统计

**位置**：日历格子下方，以 `st.expander("📊 本月时长统计", expanded=False)` 包裹。

**触发条件**：始终渲染（即使当月无事务，展示空态）。

**展示内容**：调 `get_monthly_activity_stats(planning_cal_year, planning_cal_month)` 获取数据，渲染表格或分行展示：
```
工作     8小时30分钟
学习     3小时
生活     2小时15分钟
──────────────────
合计    13小时45分钟
```
无记录时显示「本月暂无事务记录」。

### format_duration 辅助函数

在 `tab_planning.py` 内部定义（不作为公开 API）：
- `format_duration(minutes: int) -> str`
- 输出规则：`0` → `"0分钟"`；`< 60` → `"X分钟"`；`整小时` → `"X小时"`；其他 → `"X小时Y分钟"`

## 不要做

- 不要新增 DB 表或修改 `daily_activities` 表结构
- 不要把 `format_duration` 暴露为公开函数放到 `core/` 层
- 不要在统计展示处加任何编辑交互

## 验收清单

- [ ] 新增事务后，今日统计行立即更新（Streamlit rerun 驱动，无需额外状态）
- [ ] 删除事务后，统计行同步减少，归零后统计行隐藏
- [ ] 月度统计 expander 内容随 `planning_cal_month` 切换自动刷新
- [ ] 格式：`1小时30分钟` / `45分钟` / `2小时` / `0分钟` 均正确
- [ ] 无事务时月度统计显示空态提示，不报错
- [ ] 已同步更新 `docs/api/core.md` + `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`get_monthly_activity_stats` 使用 SQLite 的 `strftime('%Y-%m', date)` 过滤，比 LIKE 更健壮。今日统计不需要新 DB 函数，直接对 `_render_daily_activities` 已有的 `activities` 列表做 Python 层聚合即可，无额外查询。
