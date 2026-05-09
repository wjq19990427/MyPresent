# Task #31 — ai_analysis.py 统一分析 UI 组件

## 目标

新建 `components/ai_analysis.py`，在上传流程中替换原有 `ai_tagging.py` + `ai_fill.py` 的位置，提供统一的 AI 分析面板：一次调用填入所有字段，支持逐字段重生成（含三级 hint 选择）。

**依赖**：task-30 先合并（需 AnalysisSkill 可用）。

## 必读契约

- `docs/api/components.md`
- `docs/api/skills.md` # AnalysisSkill 节

## 改动范围

- **新增**：`components/ai_analysis.py`
- **修改**：`components/tab_upload.py`（替换原 `render_ai_tag_picker` + `render_ai_fill_picker` 调用，改为调用新组件）
- **修改**：`docs/api/components.md`
- **不许碰**：`components/ai_tagging.py` / `components/ai_fill.py`（保留，归档流程仍在用）

## 接口约定

### `render_ai_analysis(model_id: str) -> dict | None`

- **行为**：渲染完整 AI 分析面板
- **返回**：用户点击「全部采纳」或逐项确认完毕后，返回含已选字段的 dict（结构与 `AnalysisSkill.execute` 的 `data` 一致）；用户未操作或关闭时返回 `None`
- **副作用**：读写 `session_state`（缓存 AI 建议，避免切换页面后重置）；不直接写库

### 面板交互行为

**初始状态**：「✨ AI 分析」按钮，点击后调用 `AnalysisSkill(fields="all")`，展开结果面板。

**结果面板**（每行一个字段）：
- 标题 / 摘要 / 领域 / 视角 / 话题 / 情绪 / 情绪描述 / 感受 / 原因
- 每行右侧有「↺ 重生成」按钮

**重生成交互（三级）**：
1. 「再试一次」— 无 hint，直接重调 `AnalysisSkill(fields=[该字段])`
2. 预设快捷标签（按字段类型显示，如标题类：「太长」「太正式」「换个角度」）— 选中后自动触发重调
3. 「自定义…」— 显示文本输入框，提交后触发重调；以上均不合适时使用

**确认区**：「全部采纳」一键应用 + 「逐项确认」模式（每行独立勾选）

### 预设 hint 标签参考

| 字段 | 预设选项 |
|---|---|
| title | 太长、太正式、太模糊、换个角度 |
| domains / attributes / emotion_tags | 分类不对、太宽泛、换个方向 |
| topics | 太技术性、太笼统、更具体一些 |
| summary / feeling / reason | 太简短、换个表达、更口语化 |

## 不要做

- 不要在本组件内直接调用 `db_manager` 写库
- 不要把 AI 建议直接写入表单 widget，而是通过返回值让调用方写入
- 不要删除 `ai_tagging.py` / `ai_fill.py`（其他地方还在用）

## 验收清单

- [ ] 上传页面「✨ AI 分析」按钮可见，点击后展示全部字段建议
- [ ] 点击任意字段的「↺ 重生成」→ 出现三级 hint 选项 → 选择后仅该字段刷新，其他字段不变
- [ ] 「全部采纳」后表单各字段被正确填入
- [ ] 刷新/切换 sub-tab 后重回上传页，AI 建议结果仍在（session_state 缓存）
- [ ] `ai_tagging.py` / `ai_fill.py` 在归档流程中仍正常工作
- [ ] 已同步更新 `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`session_state` key 命名建议用 `_analysis_result` + `_analysis_field_states`，与现有 `_ai_tag_*` 等 key 区分。重生成时只更新对应字段的 state，其他字段不重置——这是核心 UX 约束，Codex 实现时需注意局部更新而非整体替换。
