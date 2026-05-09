# Task #22 — 年度规划：展开查看关联待办进度

## 目标

为年度规划的每一项目标增加展开/折叠能力：当该目标有关联的日历待办时，可展开查看所有拆解出的小目标列表及其完成情况，并显示整体进度。年度规划因此兼具"目标分组"视角，用户无需跳转日历即可评估执行进展。

## 依赖

**必须在 task-19 和 task-21 均合并后执行。**

## 必读契约

- `docs/api/core.md` # `calendar_todos` 相关函数（含 `postpone_count` 字段）
- `docs/api/components.md` # `tab_planning.py` 节（task-21 更新后的 `_render_goal_row` 结构）

## 改动范围

- **修改**：`core/db_manager.py`（新增 `get_todos_by_goal`）
- **修改**：`components/tab_planning.py`（`_render_goal_row` 增加展开区）
- **更新**：`docs/api/core.md`（追加 `get_todos_by_goal` 契约节）
- **更新**：`docs/api/components.md`（更新 `tab_planning.py` 节）
- **不许碰**：`app.py` / `core/state.py` / 日历待办相关函数

## 接口约定

### `get_todos_by_goal(goal_id: str) -> list[dict]`
- 行为：返回所有关联至该目标的待办，按执行日期升序排列
- 返回：字段同 `calendar_todos` 全字段（含 `postpone_count` / `postponed_days`）
- 副作用：无
- 约束：不过滤 status，返回全量（已完成与未完成均包含）

---

### `_render_goal_row` 展开区

- 行为：有关联待办的目标行显示整体进度（已完成数 / 总数 + 进度条）；可展开查看每条待办的日期、内容摘要、完成状态、延期次数标记
- 展开区**只读**，不提供任何写操作
- 无关联待办的目标行：展开区不渲染，与现有样式完全一致

## 不要做

- 不要在展开区内加任何写操作（checkbox、删除、延期按钮均不加）
- 不要修改日历待办相关函数
- 不要修改 `app.py` / `core/state.py`

## 验收清单

- [ ] `python -c "from core.db_manager import get_todos_by_goal; print('OK')"` 通过
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 无关联待办的目标行：样式与现有完全一致
- [ ] 有关联待办的目标行：显示进度（已完成数 / 总数 + 进度条）
- [ ] 展开后列表按执行日期排序；完成状态、延期次数标记正确显示
- [ ] 展开区内无任何可操作按钮
- [ ] `docs/api/core.md` 追加 `get_todos_by_goal` 契约
- [ ] `docs/api/components.md` 已更新
- [ ] commit 符合规范（建议 `feat(tab_planning): 年度规划展开关联待办进度 · 关联 #22`）
- [ ] worktree 分支提交，未 push main

## 架构师备注

- `get_todos_by_goal` 每次 rerun 调用，轻量查询，无需缓存
- 目标被删除时关联待办的 `linked_goal_id` 自动置空（ON DELETE SET NULL），`get_todos_by_goal` 按 FK 查，已置空的自然不返回，无需额外处理
