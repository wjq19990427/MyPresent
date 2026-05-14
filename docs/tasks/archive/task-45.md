# Task #45 — 待办完成时填写时间并自动生成事务；月历隐藏已完成待办

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：优化

在具体日期视图中勾选完成一条待办时，弹出时间选择表单（小时 + 分钟各一个下拉），填写后自动在当日生成一条对应事务记录，无需再手动填表。月历格和月份待办列表不再显示已完成的待办，仅在点开具体日期后的窗口中保留（维持原有灰色删除线样式）。

---

## 目标

简化"完成待办 → 记录事务"的操作路径，同时让月历视图更简洁，只展示未完成项。

## 必读契约

- `docs/api/components.md` # tab_planning.py 节（`_render_todo_row` / `_render_reflection_box` / `_render_calendar_todos`）
- `docs/api/core.md` # Daily Activities 节（`create_daily_activity`）

## 改动范围

- **修改**：`components/tab_planning.py`
- **修改**：`docs/api/components.md`
- **不许碰**：`core/db_manager.py`、`complete_todo`、`create_daily_activity` 签名

## 接口约定

### 一、完成待办的新交互流程（仅限具体日期视图）

**触发条件**：当前有选中日期（`planning_cal_date` 非空）时，勾选未完成待办。

**新表单内容**（替换现有 `_render_reflection_box`）：
- 小时下拉：`00`–`23`，共 24 项，默认空（未选）
- 分钟下拉：`00`–`59`，共 60 项，默认空（未选）
- 反思文本框（选填，与现有相同）
- 「✅ 确认完成」按钮 / 「跳过」按钮

**确认完成**：
- 调用 `complete_todo(todo_id, reflection)`
- 若小时与分钟均已选择，调用 `create_daily_activity(selected_date, todo["content"], todo["category"], start_time="HH:MM")`，`duration=0`，`end_time=""`
- 若时间未填，不创建事务（不再触发原有的活动表单预填行为）
- 关闭表单，`st.rerun()`

**跳过**：仅调用 `complete_todo(todo_id, "")`, 不创建事务，关闭表单，`st.rerun()`

**非日期视图中完成待办**（月份模式，`planning_cal_date` 为空）：保持现有逻辑不变（原有反思表单 + 活动表单预填行为）。

### 二、月历视图过滤已完成待办

`_render_calendar_todos` 中构建 `day_map` 时，跳过 `status == "已完成"` 的待办，已完成项不出现在日历格子中。

月份模式下的待办列表（无选中日期时渲染的 `display_todos` 循环）同样只渲染未完成项。

`_render_selected_day_todos`（具体日期视图）：行为**不变**，全部渲染，包括已完成（保留灰色删除线样式）。

## 不要做

- 不要改 `complete_todo` 或 `create_daily_activity` 的签名
- 不要在月份模式的待办完成流程上应用时间表单（两个路径分开处理）
- 不要给时间输入添加「自定义…」或文本框，只用下拉
- 不要改已完成待办在日期视图中的显示样式

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 无报错
- [ ] `streamlit run app.py` 启动无报错
- [ ] 手工：选中某日期 → 勾选一条未完成待办 → 出现小时+分钟下拉 + 反思框
- [ ] 手工：填写时间后确认 → 待办变灰 → 今日事务列表出现对应条目，`start_time` 正确
- [ ] 手工：不填时间直接确认 → 待办变灰 → 今日事务列表不生成新条目
- [ ] 手工：点跳过 → 待办变灰 → 不生成事务
- [ ] 手工：月历格中已完成待办不再显示
- [ ] 手工：月份待办列表（无日期选中时）不显示已完成项
- [ ] 手工：点开具体日期 → 已完成待办仍显示（灰色删除线）
- [ ] `docs/api/components.md` 已同步更新
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`_render_reflection_box` 目前不接收 `todo` 对象，只有 `todo_id`；需要 `todo["content"]`、`todo["category"]`、`selected_date` 来创建事务。可读 session_state 的 `planning_cal_date` 取 selected_date，`todo` 对象通过 `_find_todo_in_render_state(todo_id)` 获取（现有函数，可复用）。

时间下拉的 session_state key 建议用 `_compl_hour_{todo_id}` / `_compl_min_{todo_id}`，避免与 `af_start_time` 等已有 key 冲突。
