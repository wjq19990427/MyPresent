# Task #38 — 规划台优化 + 记录台文字修正

## 目标

规划台：日历视图调为默认入口；待办支持编辑；事务记录支持时间段；过期待办在切换月份时自动迁移至当月。记录台：修正导引文字与当前 Tab 名称一致。

## 必读契约

- `docs/api/components.md` # tab_planning.py 节
- `docs/api/core.md` # db_manager.py::Calendar Todos + Daily Activities 节

## 改动范围

- **修改**：`components/tab_planning.py`
- **修改**：`core/db_manager.py`
- **修改**：`components/tab_upload.py`（文字修正）
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/components.md`
- **不许碰**：年度规划相关逻辑、`annual_goals` 表

## 接口约定

### 一、规划台 sub-tab 顺序调整

将现有两个 sub-tab 顺序互换：`📅 日历 & 日志` 排第一，`🎯 年度规划` 排第二。`planning_sub_tab` 默认值改为日历 sub-tab 的名称。

### 二、待办编辑

`update_calendar_todo(todo_id, **fields) -> None` 已存在，直接复用。

UI 层在每条待办行新增「编辑」按钮，展开与新建相同字段的内联表单（内容 / 分类 / 优先级 / 日期 / 重复 / 关联目标），确认后调 `update_calendar_todo`，取消关闭表单。使用 `session_state` key `_todo_editing_{todo_id}` 控制展开状态；同一时间只能有一条待办处于编辑状态。

### 三、事务时间段

#### DB 变更（幂等，ALTER TABLE IF NOT EXISTS 模式）

`daily_activities` 新增两列：
- `start_time TEXT DEFAULT ''`：开始时间，`HH:MM` 24 小时制，空表示未填
- `end_time TEXT DEFAULT ''`：结束时间，同上

#### `create_daily_activity` 签名扩展

`create_daily_activity(date, description, category, duration=0, start_time='', end_time='') -> dict`
- `start_time` / `end_time` 可选，写库时存原始字符串
- `duration`：若 `start_time` 和 `end_time` 均非空，由调用方传入计算好的分钟数；DB 层不自动计算

#### `get_daily_activities` 返回值

新增 `start_time` / `end_time` 字段（空字符串降级）。

#### UI 表单

时间段输入区域，显示两个时间控件（开始 / 结束）：
- 默认选项：下拉列表，00:00 ～ 23:30，每 30 分钟一格，共 48 项，加一个「自定义…」选项
- 选「自定义…」后显示文本输入框，格式提示 `HH:MM`，输入后做简单格式校验（`\d{1,2}:\d{2}`，小时 0-23，分钟 0-59）
- 若两端时间均已选，自动计算并填入 `duration`（分钟数），用户仍可手动覆盖
- 时间段选填，不填不影响保存

### 四、过期待办跨月自动迁移

#### DB 变更

`calendar_todos` 新增一列：
- `postponed_months INTEGER NOT NULL DEFAULT 0`：记录累计自动跨月次数

#### 迁移逻辑

新增函数 `migrate_overdue_todos(target_year: int, target_month: int) -> int`：
- 查询所有 `status != '已完成'`、`target_date < {target_year}-{target_month}-01`、`recurrence == '仅一次'` 的待办
- 对每条：将 `target_date` 更新为 `target_year-target_month-{原日，超出当月末则取末日}`，`postponed_months += 1`
- 返回迁移条数；幂等（同月多次调用结果相同）

#### 触发时机

在 `_render_calendar_tab`（日历视图渲染入口）中，当 `planning_cal_year` / `planning_cal_month` 与上一次渲染的值不同时，调用 `migrate_overdue_todos(当前年, 当前月)`。若返回值 > 0，在日历顶部渲染一条 `st.info("已自动迁移 N 条过期待办至本月")`，渲染一次后清除（不持久化）。

重复任务（`recurrence != '仅一次'`）不迁移，保持现有重复展示逻辑。

### 五、记录台文字修正

在 `tab_upload.py` 中，将面向用户的导引文字中的「灵感墙」统一替换为「待处理」；将「记录舱」替换为「记录台」；检查并修正其他与当前 Tab 名称不符的提示语（如暂存成功提示、错误提示等）。

## 不要做

- 不要给重复任务做跨月迁移
- 不要自动计算 duration（调用方负责计算后传入）
- 不要改 `postpone_todo`（按天延期）的逻辑
- 不要在日历以外的地方触发迁移逻辑

## 验收清单

- [ ] 规划台默认展示日历 & 日志，年度规划在第二位
- [ ] 待办行有「编辑」按钮，点击展开表单，修改后保存生效
- [ ] 事务新增表单有开始/结束时间下拉，选「自定义…」出现文本框
- [ ] 填写时间段后 duration 自动计算，事务详情显示时间段
- [ ] 切换到当月，过期未完成的单次待办自动迁移，顶部有提示
- [ ] 重复任务不被迁移
- [ ] `get_daily_activities` 返回含 `start_time / end_time`
- [ ] 上传页导引文字无「灵感墙」/「记录舱」字样
- [ ] 已同步更新 `docs/api/core.md` + `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

跨月日期处理：若原 `target_date` 为 `2026-01-31`，迁移至 2 月时应取 2 月末（`2026-02-28`）。用 Python `calendar.monthrange` 或直接 `min(原日, 当月天数)` 处理即可。`migrate_overdue_todos` 建议在 `_conn()` 事务内批量 UPDATE，避免逐条提交。
