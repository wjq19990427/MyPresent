# Task #44 — 待办完成→事务自动预填 + 记录此刻入口收拢

## 目标

① 勾选待办完成后，自动展开事务记录表单并预填描述，提示用户补全时长或时间段；② 「记录此刻想法」入口仅保留在今日事务列表底部，移除其他触发点。

## 必读契约

- `docs/api/components.md` # tab_planning.py 节

## 改动范围

- **修改**：`components/tab_planning.py`
- **修改**：`core/state.py`（新增 `planning_activity_prefill` 键）
- **修改**：`docs/api/components.md`
- **修改**：`docs/api/core.md`
- **不许碰**：`core/db_manager.py`、`complete_todo` 函数签名

## 接口约定

### 一、待办完成→事务自动预填

#### session_state 新增键

| key | 默认值 | 说明 |
|---|---|---|
| `planning_activity_prefill` | `None` | `{"description": str, "category": str}` 或 `None` |

#### 触发时机

完成待办的确认流程（用户点「确认完成」或跳过复盘后）调用 `complete_todo()` 之后：
- 若 `planning_activity_adding` 为 False，将其置为 True
- 将 `{"description": todo["content"], "category": todo["category"]}` 写入 `planning_activity_prefill`
- 不额外触发 `planning_record_moment_date`（避免两层提示叠加）

#### 事务表单消费预填

`_render_activity_form` 在展开时检查 `planning_activity_prefill`：
- 若非 None，将 `description` 和 `category` 写入对应 widget 的 session_state key 作为默认值
- 同时渲染提示文字：`💡 也可以只填时长（分钟）来快速记录，时间段为选填`
- 消费后立即清空 `planning_activity_prefill = None`（防止再次展开时残留）

### 二、「记录此刻」入口收拢

**保留**：`_render_record_moment_prompt` 在 `_render_daily_activities` 末尾的唯一调用点，由 `planning_record_moment_date` 控制显示。

**移除**：所有其他可能触发「记录此刻」提示的代码路径——检查 `tab_planning.py` 全文，确保 `planning_record_moment_date` 只在 `_render_activity_form` 保存成功时被写入，其他任何地方若有写入该键的逻辑一律删除。

## 不要做

- 不要在待办完成流程里再单独渲染一个「记录此刻」提示
- 不要强制要求预填字段（用户可以清空后自行填写）
- 不要改变待办完成的复盘（reflection）逻辑

## 验收清单

- [ ] 勾选待办并确认完成后，今日事务表单自动展开，描述已预填为待办内容
- [ ] 事务表单内有时长填写提示文字
- [ ] 切换日期或重新打开后，预填不残留（`planning_activity_prefill` 已清空）
- [ ] 「记录此刻想法」提示只出现在事务列表底部，完成待办后不再额外出现该提示
- [ ] `planning_activity_prefill` 已在 `state.py` 登记
- [ ] 已同步更新 `docs/api/components.md` + `docs/api/core.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

预填消费的时机：在 `_render_activity_form` **渲染 widget 之前**读取并写入 session_state，写完立即清空，确保 Streamlit 下次渲染时 widget 已拿到默认值，且不会二次触发。`planning_activity_adding = True` 和 `planning_activity_prefill` 的写入应在同一次 `st.rerun()` 前完成。
