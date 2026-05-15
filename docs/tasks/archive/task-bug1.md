# Task #bug1 — 修复规划台待办迁移错误触发（UI 浏览月份触发了迁移）

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：Bug修复

修复规划台日历的一个逻辑错误：用户在日历界面切换到未来月份时，系统会把当前未完成的待办事项错误地迁移到那个未来月份。正确行为应该是：只有当真实系统日期跨入新的自然月时，才自动将上月未完成待办迁移到当前真实月份。

---

## 目标

用户在规划台翻看日历（浏览6月、7月等未来月份）时，不再触发任何待办迁移。迁移只由「真实时钟跨月」驱动，与用户当前浏览的日历页无关。

## 必读契约

- `docs/api/components.md` — `tab_planning` 节（重点：`_render_calendar_todos` 与 `_maybe_migrate_overdue_todos` 的调用关系）
- `docs/api/core.md` — `migrate_overdue_todos` 节（幂等性保证）

## 改动范围

- **修改**：`components/tab_planning.py`（仅 `_maybe_migrate_overdue_todos` 函数及其调用点）
- **不许碰**：`core/db_manager.py`（`migrate_overdue_todos` 签名和逻辑不动）
- **不许碰**：其他规划台组件和数据库层

## 接口约定

**现象**：`_render_calendar_todos`（tab_planning.py:301）调用 `_maybe_migrate_overdue_todos(year, month)` 时传入的是 UI 日历视图的年月，而非系统当前时间。用户翻到未来月份就等价于触发了迁移。

**预期行为**：`_maybe_migrate_overdue_todos` 内部始终取 `datetime.now()` 的年月作为迁移目标，与外部传入参数或 session_state 中的日历视图月份无关。

**约束**：
- `migrate_overdue_todos(year, month)` 本身已具备幂等性（已在当月的 todo 不会被重复迁移），修复后无需持久化迁移记录到数据库
- 修复后，session_state 的防重复 key 仍用真实当月（`YYYY-MM`），而非视图月份

## 不要做

- 不修改 `migrate_overdue_todos` 的函数签名
- 不引入新的数据库表或字段来持久化迁移状态
- 不改动日历 UI 导航逻辑（用户仍可自由翻看任意月份）

## 验收清单

- [ ] 将日历切换到7月、8月等未来月份，控制台无迁移触发，页面无「已自动迁移 X 条」提示
- [ ] 将系统时间模拟为下月初，首次打开规划台时，弹出「已自动迁移 X 条」提示（或手动确认 DB 数据变更）
- [ ] 当月待办在日历中显示正常，大头针（今日标注）仍指向正确的系统当日
- [ ] `python -m pytest` 或启动应用无报错
- [ ] commit 信息：`fix(tab_planning): 迁移触发改为真实时钟驱动，禁止 UI 浏览触发 · 关联 #bug1`
- [ ] 在 worktree 分支提交，未 push main

## 架构师备注

**根因定位**：`tab_planning.py:301` 调用 `_maybe_migrate_overdue_todos(year, month)`，其中 `year/month` 来自 `session_state["planning_cal_year/month"]`，即用户正在浏览的日历月份，而非 `datetime.now()`。用户翻到未来月份 → session_state 更新 → 函数被以未来月份调用 → 触发迁移。

**已知数据损伤**：上述 bug 已将 plus7 用户的以下待办错误迁移：
- `postponed_months=2` 的5条（原5月 → 错误迁移至7月）
- `postponed_months=1` 的1条（原6月 → 错误迁移至7月）

数据还原脚本需在本 task 代码修复前单独执行（见架构师另行操作），本 task 仅修复代码逻辑。

**幂等性说明**：`migrate_overdue_todos(year, month)` 查询条件为 `target_date < month_start`，已在当月的 todo 不满足条件，因此修复后每次 app 启动都调用一次也不会重复迁移——无需额外的持久化开关。
