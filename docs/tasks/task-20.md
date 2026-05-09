# Task #20 — 日历 UI 重设计：方格 + 对齐 + 月份跳转 + 延期流程

## 目标

重设计月度日历待办的视觉与交互：修复星期标题对齐问题；将日期格升级为可展示待办内容的方形块；月份导航支持直接跳转（不再只能逐月翻页）；待办行增加延期流程，记录延期次数与天数。

## 依赖

**必须在 task-19 合并后执行。**

## 必读契约

- `docs/api/core.md` # `calendar_todos` 相关函数（含 task-19 新增的 `postpone_todo`、`postpone_count` / `postponed_days` 字段）
- `docs/api/components.md` # `tab_planning.py` 节（现有日历实现结构）

## 改动范围

- **修改**：`components/tab_planning.py`（`_render_calendar_todos` 及相关私有函数）
- **修改**：`core/state.py`（新增延期表单开关键）
- **更新**：`docs/api/components.md`（更新 `tab_planning.py` 节）
- **不许碰**：`core/db_manager.py` / `app.py` / 年度规划相关函数

## 接口约定

### 月份导航

`_render_month_nav(year: int, month: int) -> None`
- 行为：渲染一行导航控件，同时支持逐月翻页（◀▶按钮）和直接跳转（年份与月份可直接输入/选择）；任意控件变更后立即更新 session_state 并 rerun
- 约束：年份范围合理即可

---

### 日期格

- 行为：每格为独立内容块，同时展示日期数字与当日待办摘要文字；今日日期有视觉高亮；点击日期格可选中该日
- 约束：星期标题行（一～日）与日期格列**必须使用同一组列定义**，保证水平对齐；超出展示上限的待办以"+N 更多"提示

---

### 延期流程

`core/state.py` 新增延期表单开关键（参照 `_reflection_open` 的 dict 结构）。

- 行为：未完成的待办行新增「延期」入口；触发后展开内联表单，用户输入延期天数并确认；确认后调 `postpone_todo`，关闭表单，rerun
- 副作用：`target_date` 变更，延期后该待办可能从当前月消失（正确行为）
- 展示：`postpone_count > 0` 的待办在信息行显示延期次数标记

## 不要做

- 不要修改年度规划相关函数
- 不要修改 `app.py`
- 不要实现重复任务自动生成

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 星期标题（一～日）与日期格列精确对齐
- [ ] 日期格同时显示日期数字与待办摘要文字（不只是数字按钮）
- [ ] 今日日期有视觉高亮；已完成待办显示删除线
- [ ] 月份导航：◀▶翻页正常；年份与月份可直接跳转
- [ ] 延期入口仅对未完成待办显示；确认后 target_date 更新，日期格位置变化
- [ ] `postpone_count > 0` 的待办显示延期次数标记
- [ ] `docs/api/components.md` 已更新
- [ ] commit 符合规范（建议 `feat(tab_planning): 日历 UI 重设计 + 延期流程 · 关联 #20`）
- [ ] worktree 分支提交，未 push main

## 架构师备注

- 星期标题与日期格对齐的根本原因：两者必须共用同一组列声明，不能分两次调用 `st.columns`
- 延期后 `target_date` 改变，若新日期不在当前查看月，该待办从网格消失——这是正确行为，无需额外提示
- 延期开关 key 的命名和结构与 `_reflection_open` 保持一致
