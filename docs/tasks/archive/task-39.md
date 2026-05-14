# Task #39 — 标签体系三项优化

## 目标

① 已归档页标签筛选改为折叠式，默认全选摘要态，避免大量渲染；② 新增标签延迟入库，只有用户保存记录时才真正写入 `label_registry`；③ 删除标签时询问并级联移除已有记录中对该标签的引用。

## 必读契约

- `docs/api/components.md` # tab_archived.py + cards.py + ai_analysis.py 节
- `docs/api/core.md` # db_manager.py::Label Registry 节

## 改动范围

- **修改**：`components/tab_archived.py`
- **修改**：`components/cards.py`（`_render_label_manager`）
- **修改**：`components/tab_upload.py`（保存路径）
- **修改**：`core/db_manager.py`（新增级联函数）
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/components.md`
- **不许碰**：`skills/analysis_skill.py`、`components/ai_analysis.py`（分析逻辑不变）

## 接口约定

### 一、筛选折叠 UX

**替换 `_render_structured_filter` 的渲染行为**（tab_archived.py）：

默认状态（未展开）：渲染一行紧凑摘要文字，格式：
```
📍 筛选：全部领域 · 全部话题 · 全部情绪    [自定义 ▾]
```
若某维度有自定义选择（非全选），摘要改为：`领域：3/6 项`。

点击「自定义 ▾」切换展开状态（session_state key `_archived_filter_expanded`），展开后渲染原有的三行 multiselect，顶部有「收起 ▴」按钮。

筛选逻辑不变，只改渲染方式。

### 二、新增标签延迟入库

**核心原则**：在用户点「归档」或「保存」之前，`add_label()` 不被调用。

#### 上传页（tab_upload.py）

`_apply_analysis_to_upload_form(result)`：移除其中对 `add_label()` / `_register_structured_labels()` 的调用；仅写入 `st.session_state`（含 AI 建议的新标签值）。

`_structured_options(field)`：options = label_registry + session_state 当前已选值（包含 AI 建议的新值）；新值（不在 registry 中）可以出现在选项里，用户可选取或移除。

保存路径（`do_archive` / `do_pending`）：在调用 `save_session_final` / `save_session_pending` 之前，对每个结构化字段的 selected 值，与 `get_label_registry(type)` 对比，将不在 registry 中的新值调 `add_label(value, type)` 写库——只写用户实际选中的。

#### 详情页（cards.py）

`_apply_analysis_to_detail_form`：移除 `_register_structured_labels()` 调用；仅写 session_state。

`_structured_options`：同上，options 含 AI 建议值（不在 registry 中的均可选）。

保存路径（两处 `update_session_fields` 调用前）：同样对比 registry，只 `add_label()` 用户实际选中的新值。

### 三、删除标签级联移除

#### db_manager.py 新增函数

`remove_label_cascade(name: str, type: str) -> int`
- 行为：
  1. 从 `label_registry` 删除 `(name, type)`
  2. 读取所有 `sessions`，对应字段（`type` → JSON 列映射：`domain→domains, attribute→attributes, topic→topics, emotion→emotion_tags`）做 `json.loads → filter out name → json.dumps`，批量 UPDATE 有变化的行
  3. 若 `type == 'topic'`：同时从 `session_tags` 删除 `tag = name` 的所有行
- 返回：实际更新的 session 行数
- 约束：在一个事务内完成；若 `(name, type)` 不在 registry 静默 no-op

#### UI 层（cards.py `_render_label_manager`）

删除按钮点击后不立即删除，而是先查询引用数量：
- 读取所有 sessions，统计对应 JSON 字段中含该值的条数
- 展示确认提示：`「{name}」在 N 条记录中被引用，删除后将从所有记录中移除引用，是否确认？`（N=0 时提示「暂无记录引用，直接删除」）
- 点「确认删除」→ 调 `remove_label_cascade(name, type)` → `st.rerun()`
- 点「取消」→ 关闭确认区域

使用 session_state key `_label_delete_confirm_{type}_{name}` 控制确认区域显示。

## 不要做

- 不要改 `remove_label`（保留原函数供其他调用），新增 `remove_label_cascade` 作为带级联的版本
- 不要在 AI 分析面板内部做任何入库操作（`ai_analysis.py` 不动）
- 不要改变 label_registry 的结构或 `add_label` 的签名

## 验收清单

- [ ] 已归档页默认显示筛选摘要行，点「自定义」才展开 multiselect
- [ ] 摘要行准确反映当前筛选状态（全选 vs 部分选）
- [ ] AI 分析采纳后，新标签出现在 multiselect options 中可供选取，但此时 label_registry 中无该条目
- [ ] 点「归档」/「保存」后，只有用户实际选中的新标签写入 label_registry
- [ ] 未被选中的 AI 建议新标签不出现在 label_registry 中
- [ ] 删除库中一个标签，弹出确认框并显示引用数量
- [ ] 确认后该标签从 label_registry 和所有 session 的对应 JSON 字段中移除
- [ ] `type == 'topic'` 时同步清理 `session_tags`
- [ ] 已同步更新 `docs/api/core.md` + `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`remove_label_cascade` 的 session 批量扫描不走 `load_db()`（会触发 vector 索引等副作用），直接用 `_conn()` 执行 `SELECT id, {col} FROM sessions WHERE {col} LIKE '%?%'` 做粗筛后再精确过滤，减少不必要的行更新。新标签出现在 multiselect options 中但不在 registry 的实现方式：`_structured_options` 把当前 session_state 已选值合并进 options 列表即可（现有代码已有类似逻辑，核查后复用）。
