# Task #24 — UI：日历视图重命名 + 今日事务记录 + 优先级标签重设计

## 目标

扩展月度日历视图为「日历 & 日志」：选中具体日期时同时展示待办事宜与今日事务记录，并支持动态增删今日事务。同时将全局优先级展示从纯色圆块升级为带文字的小标签，提升可读性。

## 依赖

**必须在 task-23 合并后执行。**

## 必读契约

- `docs/api/core.md` # `daily_activities` 相关函数（task-23 新增）
- `docs/api/components.md` # `tab_planning.py` 节（现有日历结构）

## 改动范围

- **修改**：`components/tab_planning.py`
- **修改**：`core/state.py`（新增今日事务相关 session_state 键）
- **更新**：`docs/api/components.md`
- **不许碰**：`core/db_manager.py` / `app.py`

## 接口约定

本任务改动顺序如下，Codex 按序实现：

### 步骤 1：重命名子 Tab

将 `render_planning_tab()` 中的子 Tab 名从「📅 月度日历待办」改为能体现「待办 + 日志」双重含义的名称，由 Codex 自行选定。

---

### 步骤 2：优先级标签重设计

将 `PRIORITY_BADGE` 从纯色 emoji 改为带文字的小标签格式：同时包含颜色指示与优先级文字（如「🔴 高」「🟡 中」「🟢 低」）。

涉及所有引用 `PRIORITY_BADGE` 的位置：`_render_goal_row`、`_render_todo_row`、`_render_calendar_cell`（`_calendar_todo_summary`）、`_render_goal_todo_readonly`。

---

### 步骤 3：`core/state.py` 新增键

新增今日事务相关 session_state 键，用于控制新增表单的显示状态（参照 `planning_todo_adding` 的模式）。

---

### 步骤 4：选中日期视图扩展

`_render_calendar_todos` 中，选中具体日期后的视图从单一待办列表扩展为两个区块：

**区块一：待办事宜**（现有逻辑保留）  
显示该日期下的 `calendar_todos`，逻辑不变。

**区块二：今日事务**  
- 标题区域含「📝 记录今日事务」按钮，点击展开新增表单
- 列出该日已记录的事务（描述、分类、时长）及删除入口
- 新增表单字段：事务描述（必填）、分类（`TODO_CATEGORIES`）、时长（分钟，选填，0 表示未填）
- 保存调 `create_daily_activity`；删除调 `delete_daily_activity`

---

### 步骤 5：日历网格格子更新

`_calendar_cell_label` 中，有效日期格同时聚合当日 `calendar_todos` 摘要与 `daily_activities` 数量提示（若有）。

`_render_calendar_todos` 在构建 `day_map` 时，同步查询当月所有 `daily_activities` 并按日期分组，传入格子渲染函数。

## 不要做

- 不要修改 `app.py`
- 不要修改年度规划相关函数（`_render_annual_goals` / `_render_goal_form` / `_render_category_manager` 等）
- 不要为今日事务实现编辑功能（本期只支持增删）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 规划控制台第二子 Tab 名称已更新
- [ ] 优先级标签在目标列表、待办列表、日历格子、展开区均显示为带文字小标签
- [ ] 选中日期后视图包含「待办事宜」与「今日事务」两个区块
- [ ] 「记录今日事务」按钮展开表单，填写后保存出现在列表中
- [ ] 删除今日事务条目生效
- [ ] 日历格子有今日事务时有对应提示
- [ ] `docs/api/components.md` 已更新
- [ ] commit 符合规范（建议 `feat(tab_planning): 日历日志 + 今日事务 + 优先级标签 · 关联 #24`）
- [ ] worktree 分支提交，未 push main

## 架构师备注

- 步骤 5 需要在渲染月历前额外查询当月 daily_activities，查询函数 `get_daily_activities` 按单日查询，月视图需对每一天调用或扩展为按月查询——实现方式由 Codex 自行决定
- `daily_activities` 与 `calendar_todos` 语义不同：前者是「已做」实录，后者是「计划做」清单；在 UI 上保持视觉区分
