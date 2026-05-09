# components/ — UI 层

> Streamlit 渲染。只消费 `skills/` 和 `core/`，不实现业务逻辑。

## 边界规则

- 业务逻辑禁止写在 Tab 里——下沉到 `skills/` 或 `core/`
- 组件之间最小耦合：通过 `session_state` 或显式回调通信
- 不直接操作 SQLite——所有 DB 访问走 `core/db_manager`

## 组件清单

| 文件 | 职责 | 契约状态 |
|------|------|----------|
| `cards.py` | 共用卡片 / 详情 / 评论 / 标签&分组管理 / AI 摘要 | ✅ |
| `forms.py` | 表单字段（基于 `FIELD_SCHEMA` 动态渲染） | ✅ |
| `tab_upload.py` | 「记录舱」Tab | ✅ |
| `tab_gallery.py` | 「灵感墙」Tab | ✅ |
| `tab_archived.py` | 「已归档」Tab | ✅ |
| `tab_search.py` | 「搜索」Tab（日期 + 语义 + 问答） | ✅ |
| `tab_home.py` | 「主页」Tab（项目介绍 + 功能模块概览） | ✅ |
| `eval_dashboard.py` | 「运行看板」Tab | ✅ |
| `ai_analysis.py` | 上传草稿统一 AI 分析面板 | ✅ |
| `ai_tagging.py` | AI 打标 UI 组件 | ✅ |
| `ai_fill.py` | AI 感受/原因补全 UI 组件 | ✅ |
| `tab_recycle.py` | 「回收站」Tab | ✅ |
| `tab_planning.py` | 「规划控制台」Tab | ✅ |

---

## tab_home.py

> 「主页」Tab。展示项目介绍与 5 个功能模块卡片。

### `render_home(on_navigate: Callable[[str], None] | None = None) -> None`
- **功能**：渲染标题区、项目介绍文案，以及「记录台 / 探索 / 规划台 / 回收站 / 系统」5 个模块卡片
- **入参**：`on_navigate` 可选导航回调；用户点击模块入口时传入目标 key（`record/search/planning/recycle/system`）
- **布局**：模块卡片使用 `st.columns` 分两行展示；每张卡片使用 `st.container(border=True)` 渲染边框
- **副作用**：无写库；提供 `on_navigate` 时点击模块入口会调用该回调
- **约束**：顶层直接调用，不嵌套在任何 `st.form` 内

---

## cards.py

> 共用 UI 工具。所有函数都是 `_前缀`——跨 components 内部共享，业务/外部不应直接调。

### `_render_card(col, session, state_key, score=None) -> None`
- **入参**：
  - `col`：streamlit column 容器
  - `session`：完整 session dict
  - `state_key`：选中态键名（`pending_selected` / `archived_selected` / `search_selected`）
  - `score: float | None`：显示「🎯 相似度 XX%」徽章
- **副作用**：渲染缩略图 + 元信息 + 切换按钮；点击按钮写 `st.session_state[state_key]` + `st.rerun()`

### `_render_batch_row(session, selected_key="batch_selected_ids") -> None`
- **入参**：
  - `session`：完整 session dict
  - `selected_key`：保存已选 session_id 集合的 `session_state` 键
- **副作用**：渲染批量管理行（checkbox + 缩略图 + 摘要 + 标签）；勾选变化时写 `st.session_state[selected_key]` 并 `st.rerun()`

### `_render_detail(session, mode, state_key=None) -> None`
- **入参**：`mode = "pending" | "final"`；`state_key` 默认按 mode 推导（搜索 Tab 显式传 `search_selected`）
- **副作用**：
  - 表单保存 → `update_session_fields(sid, ...)`
  - 归档（仅 pending）→ `move_to_final(sid)`
  - 删除按钮 → `soft_delete_session(sid)`，清空选中态并关闭详情面板
  - 纯文字 session 直接重写源 .txt 文件
  - AI 推荐的新标签在保存时通过 `add_tag` 自动入库
- **依赖组件**：`forms.render_field_inputs` / `ai_fill.render_ai_fill_picker` / `ai_tagging.render_ai_tag_picker` / `_render_ai_summary` / `_render_comments`
- **已知陷阱**：widget key 用 `safe_sid = "".join(c if c.isalnum() else "_" for c in sid)` 净化，避免 streamlit 对特殊字符报错
- **AI 功能位置**：AI 补全在字段编辑区上方；AI 摘要在字段区下方，pending/final 均可用；AI 标签在标签 multiselect 上方
- **保存控件**：详情页使用普通 `st.button` 即时按钮，不再用 `st.form`，避免 AI 组件写入 widget state 后前端不刷新

### `_render_comments(session) -> None`
- **必须**在 `st.form` 外调用（依赖 `st.button` 即时回写）

### `_render_ai_summary(session) -> None`
- pending/final 详情页均可用；缓存 key = `_story_{session_id}`，依赖全局 `llm_selected_model`

### `_render_tag_manager() -> None` / `_render_group_manager() -> None`
- 标签：禁删 `DEFAULT_TAGS`
- 分组：删分组同步清 `archived_group_filter`

### 内部辅助

- `_session_thumb(session)`：图片返回路径；视频取首帧 PNG bytes
- `_completion_badge(session)`：调 `validate_session`，返回带 emoji 的状态字符串

---

## forms.py

> `FIELD_SCHEMA` 驱动的表单字段渲染。新增字段类型只需在此增加分支。

### `render_field_inputs(prefix, defaults=None, skip_keys=None) -> dict`
- **入参**：
  - `prefix: str`：widget key 前缀（同页面多次渲染必须不同前缀）
  - `defaults: dict | None`：字段默认值（通常传 session 或 `{}`）
  - `skip_keys: set | None`：跳过的字段；返回值仍包含这些 key 的 `defaults` 原值
- **返回**：`{key: 用户输入值}`，覆盖 `FIELD_SCHEMA` 全部字段
- **副作用**：在当前 streamlit 容器渲染输入框；写 widget state（`{prefix}_{key}` 或带 `_date`/`_text` 后缀）

### 字段类型分支

| `FIELD_SCHEMA[].type` | 渲染控件 |
|----------------------|----------|
| `date_or_text` | 日历 + 自由文本双控件，自由文本优先 |
| `textarea` | `st.text_area`（高 100） |
| `text` | `st.text_input` |

### 已知陷阱

- 同 `prefix` 多次渲染会冲突——跨表单务必用不同前缀
- `skip_keys` 中字段不渲染但**仍**返回原值，避免上层 dict 缺 key

---

## tab_upload.py

> 「记录舱」Tab。三种上传模式：上传文件 / 粘贴文字 / 文件夹批量导入。

### `render_upload_tab() -> None`
- **副作用**：归档调 `save_session_final`；暂存调 `save_session_pending`；文件夹模式调 `import_folder_to_pending`
- **依赖 session_state**：`upload_key`（计数器，提交后 +1，触发 `file_uploader` 重置）/ `upload_prefill`（规划台跳转预填数据，消费后清空）
- **预填行为**：若 `upload_prefill` 存在，上传页切换到「📝 粘贴文字」，显示 `st.info("✍️ 已从今日规划预填内容，可继续扩充")`，将 `description` 写入粘贴文本框，将 `topics` 补入标签注册表并默认选中，然后立即清空 `upload_prefill`

### 内部子组件

- `_pasted_filename(text) -> str`：粘贴模式自动生成文件名（首行前 20 字符 + `.txt`）
- `_pick_folder_dialog() -> str`：调用 Windows 文件夹选择器，取消时返回空字符串
- `_get_uploaded_filenames() -> set[str]`：从 `data/pending|final` 递归提取已落盘文件的原始文件名，用于扫描结果去重
- `_render_folder_import()`：选择文件夹 → 递归扫描 → multiselect → 模式选择（独立 / 合并） → 导入

### 强制约束

- **标签必填**：归档 / 暂存前校验 `upload_tags` 非空
- 归档前必校验 `validate_session`，缺必填字段拒绝放行（暂存时仅警告不阻断）
- 文件夹模式 `field_values={}`——直接以空字段暂存到 pending

### 已知陷阱

- `upload_key` 自增是 streamlit 重置 file_uploader 的标准技巧——勿删
- 上传时统一 AI 分析面板在标签 multiselect 前渲染；应用结果通过返回值交给 `tab_upload.py` 写入上传表单 state
- 上传文件 / 粘贴文字模式渲染统一 AI 分析组件；组件返回采纳结果后，由本 Tab 写入 `upload_title` / `upload_summary` / `upload_feeling` / `upload_reason` 等表单 widget state
- 文件夹导入路径保存在 `folder_selected_path`；切换路径时清空 `folder_scan_results`
- 文件夹扫描会按原始文件名排除已上传文件，并把跳过数量写入 `folder_scan_skipped_n`

---

## ai_analysis.py

> 上传草稿的统一 AI 分析面板。基于 `AnalysisSkill.execute_draft()`，替代上传流程中的旧 AI 打标 + AI 补全组合；旧组件仍供详情/归档流程使用。

### `render_ai_analysis(draft: dict, model_id: str) -> dict | None`
- **入参**：
  - `draft`：上传表单当前字段值，至少含 `description`
  - `model_id`：当前选中的 LLM 模型 ID
- **行为**：
  - 初始显示「✨ AI 分析」按钮；点击后调用 `AnalysisSkill().execute_draft(draft, model_id, fields="all")`
  - 结果面板按字段展示标题、摘要、领域、视角、话题、情绪、情绪描述、感受、原因
  - 每个字段支持「↺ 重生成」展开三级 hint：无 hint 再试一次、字段预设快捷 hint、自定义 hint
  - 局部重生成只调用对应字段并合并回缓存，不清空其他字段
  - 支持「全部采纳」与逐项勾选后「采纳勾选项」
- **返回**：用户采纳后返回已选字段 dict；未操作时返回 `None`
- **副作用**：读写 `st.session_state` 的 `_analysis_result` / `_analysis_field_states` / `_analysis_apply_payload`；不直接写 DB，不直接写上传表单 widget
- **约束**：不得替代 `tab_upload.py` 做入库；调用方负责把返回值写入表单或标签控件

---

## tab_gallery.py

> 「灵感墙」Tab。展示所有 pending 记录，按上传时间倒序。

### `render_gallery_tab() -> None`
- **过滤条件**：`status == "pending"` **且**至少一个文件实际存在
- **网格**：`COLS=3` 列
- **批量模式**：`batch_mode_gallery=True` 时改用 `_render_batch_row`，支持批量软删除 / 批量归档 / 取消选择
- **依赖**：`cards._render_card` / `cards._render_batch_row` / `cards._render_detail`
- **依赖 session_state**：`pending_selected` / `batch_mode_gallery` / `batch_selected_ids`

### 已知陷阱

- 文件不存在的 pending 记录会**被过滤掉但不删 DB**——可能产生孤儿行（目前无清理脚本，是未来债务）

---

## tab_archived.py

> 「已归档」Tab。分组导航 + 类型 / 标签 / 无标签过滤 + 编辑入口 + 标签&分组管理。

### `render_archived_tab() -> None`
- **依赖 session_state**：
  - 过滤态：`archived_type_filter` / `archived_tag_filter` / `archived_group_filter` / `_show_no_tag_only`
  - 选中态：`archived_selected`
- **依赖**：`cards._render_card` / `_render_detail` / `_render_tag_manager` / `_render_group_manager`
- **批量模式**：`batch_mode_archived=True` 时改用 `_render_batch_row`，支持批量软删除 / 批量加标签 / 取消选择

### 过滤优先级（AND 链）

```
status==final → 分组(AND) → 文件类型(AND) → 标签 OR → [可选]无标签独占
```

### 已知陷阱

- `_show_no_tag_only` 与 `archived_tag_filter` 互斥：开启前者会显式清空后者
- 选中条目若被新过滤条件排除，自动清 `archived_selected`，防止显示已不可见的详情

---

## tab_search.py

> 「搜索」Tab。三种模式：日期过滤 / 语义检索 / 智能问答。

### `render_search_tab() -> None`
- **模式切换**：`_search_mode_prev` 不等于当前模式时清空所有结果与选中态
- **依赖 session_state**（按模式）：
  - 通用：`search_selected` / `search_mode` / `_search_mode_prev`
  - 日期：`date_filter_exact` / `date_filter_fuzzy` / `date_filter_range` / `_period_story_*`
  - 语义：`semantic_results` / `semantic_query_used` / `semantic_query` / `semantic_topk`
  - 问答：`llm_chat_history`

### 内部子组件

- `_render_date_filter()`：用 ChromaDB metadata filter（`has_exact_date` + `content_time_num` 范围）；模糊时间记录单独折叠展示；下方支持「✨ 生成阶段回忆录」（调 `StorySkill.run_period`）
- `_render_semantic_search()`：BGE 非对称查询前缀「为这个句子生成表示以用于检索相关文章：」+ Top-K
- `_render_qa()`：multi-turn chat，调 `llm_client.call(history, model_id)`；失败时弹错误并 `pop` 最后一条 user 消息保持历史一致性

### 已知陷阱

- `_render_qa` / `_render_semantic_search` 直接 import `vector_db._get_collection / _get_embedder` —— 跨层下划线 API 调用，是技术债
- 模式切换会丢弃所有已有结果（包括语义检索的耗时计算）——故意为之，避免界面状态混乱

---

## eval_dashboard.py

> 「📊 运行看板」Tab。LLM 配置管理 + 全局模型选择器 + 调用统计 + 数据操作记录。

### `render_eval_dashboard() -> None`
- 四段：API 配置（折叠）→ 模型选择器 → 调用统计（指标 + 按 Skill 分组 + 最近 N 条）→ 数据操作记录
- 数据来源：`get_llm_logs(limit=500)` / `get_operation_logs(limit=50)`

### `render_model_selector(widget_key="llm_model_select_dash") -> str | None`
- **跨 Tab 共用**：搜索 Tab 的智能问答也调用此函数
- **副作用**：写 `st.session_state["llm_selected_model"]`（全局生效）
- **格式**：下拉项显示 `Provider · 模型名`
- **入参**：`widget_key` 必须在同页面唯一（看板用 `..._dash`，问答用 `..._qa`）

### 配置「确认+重测」流程（关键 UX）

| 阶段 | session_state 键 | 含义 |
|------|------------------|------|
| 用户点编辑 | `_confirm_edit_pvd` / `_confirm_edit_mdl` | 弹「需重测」二次确认 |
| 进入编辑表单 | `_editing_pvd` / `_editing_mdl` | 显示输入框 |
| 进入测试草稿 | `_draft_provider` / `_draft_model` | 临时配置（可能含 `_id` / `_readonly`） |
| 测试完成 | `_test_result` / `_draft_test_passed` | 收集 API 回复 |
| 用户确认 | — | 调 `add/update_llm_provider/model` 落库 |

### 已知陷阱

- `_TEST_MESSAGE` 是固定测试字段（非随机 prompt），便于人工验证回复合理性
- 测试调用走 `call_with_config`，**不**写 `llm_logs`（避免污染统计）
- 删当前选中模型会自动清 `llm_selected_model`，但**不**强制刷新依赖此模型的页面

---

## tab_recycle.py

> 「回收站」Tab。展示软删除记录，支持恢复与永久删除。

### `render_recycle_tab() -> None`
- **副作用**：
  - Tab 加载时调用 `purge_expired_deleted(30)` 自动清理超期软删除记录
  - 点击恢复 → `restore_session(sid)` + `st.rerun()`
  - 点击永久删除 → 二次确认后删除磁盘文件、删除 `sessions` 行、写 `purge` 操作日志
  - 每条记录提供「查看内容」折叠块，展示描述 / 感受 / 原因 / 标签 / 文件名
- **依赖**：`get_deleted_sessions` / `restore_session` / `purge_expired_deleted` / `log_operation`
- **保留期**：`_KEEP_DAYS = 30`

### 内部辅助

- `_days_remaining(deleted_at)`：按 `deleted_at` 计算剩余保留天数，解析失败返回 30
- `_purge_now(session_id)`：用户主动永久删除路径；删除文件和 DB 行，并保留操作日志

### 已知陷阱

- 永久删除不可恢复，必须保留二次确认
- 自动清理走 `purge_expired_deleted`；用户主动永久删除在 UI 内补充处理

---

## tab_planning.py

> 「📋 规划控制台」Tab。包含「🎯 年度规划」与「📅 日历 & 日志」两个子页。

### `render_planning_tab() -> None`
- **副作用**：渲染规划控制台两个子 Tab；年度规划调 `_render_annual_goals()`，日历待办调 `_render_calendar_todos()`
- **依赖**：所有数据读写均通过 `core.db_manager` 的 `annual_goals` / `calendar_todos` CRUD 与枚举常量

### 年度规划子页

#### `_render_annual_goals() -> None`
- **功能**：状态/分类筛选、分类管理、新增目标、目标列表展示、状态即时更新、编辑、删除
- **分类来源**：运行时调用 `get_goal_categories()`，筛选器与表单下拉框均使用 DB 中实际分类
- **依赖 session_state**：`planning_goal_filter_status` / `planning_goal_filter_cat` / `planning_goal_editing` / `planning_cat_manager_open`
- **视觉约定**：优先级以小号边框标签展示，文案为 `优先级：高/中/低`；`已完成` / `已搁置` 目标使用删除线

#### `_render_goal_row(goal: dict) -> None`
- **功能**：渲染单条年度目标；有关联待办时额外显示整体进度（已完成数 / 总数 + 进度条），并提供只读展开区查看关联待办
- **数据来源**：调用 `get_todos_by_goal(goal["id"])`
- **展开区约束**：只展示待办日期、内容摘要、完成状态、延期次数标记；不提供 checkbox、删除、延期等任何写操作
- **无关联待办**：不渲染进度与展开区，保持普通目标行样式

#### `_render_goal_form(editing: str, category_names: list[str]) -> None`
- **入参**：`"NEW"` 表示新增；否则为 `annual_goals.id`
- **功能**：编辑 `content/category/priority/deadline/status`；分类下拉使用 `category_names`
- **副作用**：保存时调用 `create_annual_goal()` 或 `update_annual_goal()`；取消/保存后清空 `planning_goal_editing`

#### `_render_category_manager(categories: list[dict]) -> None`
- **功能**：渲染可展开/折叠的分类管理面板；展示系统内置与用户自定义分类；支持新增分类与删除自定义分类
- **保护规则**：系统内置分类根据 `is_system` 判断，只显示受保护标记，不提供删除入口；UI 层不硬编码系统分类名称
- **副作用**：新增调用 `add_goal_category()`；删除调用 `delete_goal_category()`；增删后 `st.rerun()`，筛选器和表单下拉即时刷新
- **约束**：空名称、已存在名称会提示并不写库；删除自定义分类不修改已有目标的 `category` 历史值

### 日历 & 日志子页

#### `_render_calendar_todos() -> None`
- **功能**：月份导航、周一到周日的方格月历、日期选择、日期内待办摘要、事务数量提示、选中日期的待办事宜与今日事务、整月待办列表、新增待办入口
- **依赖 session_state**：`planning_cal_year` / `planning_cal_month` / `planning_cal_date` / `planning_todo_adding` / `planning_activity_adding`
- **视觉约定**：星期标题与日期格共用同一列规格；日期格使用 HTML 信息块展示日期数字、最多 3 条待办摘要和今日事务数量提示；待办摘要前置小号彩色边框优先级标签；待办与事务之间用分隔线区分，超出显示 `+N 更多`；今日和选中日期有不同高亮
- **交互约定**：选中具体日期后新增待办默认填入该日期；日期视图提供返回月份视图入口，清空 `planning_cal_date`
- **注意**：重复规则只存储和展示，不在 UI 层自动生成实例

#### `_render_month_nav(year: int, month: int) -> None`
- **功能**：渲染月份导航，支持 `◀` / `▶` 逐月翻页，也支持年份与月份直接跳转
- **副作用**：任意月份变更写 `planning_cal_year` / `planning_cal_month`，清空 `planning_cal_date` / `planning_activity_adding` 后 `st.rerun()`

#### `_render_calendar_cell(year, month, day_num, selected_date, day_map, activity_map) -> None`
- **功能**：渲染单个方格日期块；空白日期渲染等高占位；有效日期提供选择按钮
- **视觉约定**：已完成待办摘要使用删除线；有今日事务时显示 `📝 事务｜N 条`；信息块下方使用 `查看` / `已选中` 按钮选择日期；日期格与星期标题保持列对齐

#### `_render_todo_form(selected_date: str | None, year: int, month: int) -> None`
- **渲染条件**：仅当 `planning_todo_adding=True` 时显示
- **功能**：创建待办，字段包括 `content/category/priority/target_date/recurrence/linked_goal_id`
- **关联目标**：下拉框只展示状态为 `未开始` / `进行中` 的年度目标
- **副作用**：保存时调用 `create_calendar_todo()`；取消/保存后关闭表单

#### `_render_todo_row(todo: dict) -> None`
- **功能**：单条待办展示、完成 checkbox、延期、删除、完成复盘、已完成心得展示
- **完成流程**：勾选未完成待办时打开复盘输入；确认或跳过后调用 `complete_todo()`；取消勾选已完成待办时调用 `update_calendar_todo(status="待办", reflection="")`
- **延期流程**：仅未完成待办显示「延期」入口；展开内联表单后确认调用 `postpone_todo()`；`postpone_count > 0` 时信息行显示延期次数
- **依赖 session_state**：`_reflection_open` / `_postpone_open`，结构均为 `{todo_id: True}`

#### `_render_daily_activities(selected_date: str, activities: list[dict], todos: list[dict]) -> None`
- **渲染条件**：仅在选中具体日期时显示
- **功能**：展示该日今日事务列表；提供「记录今日事务」入口；新增表单字段为 `description/category/duration`
- **副作用**：保存时调用 `create_daily_activity()`；删除时调用 `delete_daily_activity()`；保存/取消后关闭表单；保存成功后写 `planning_record_moment_date` 以显示「记录此刻」入口
- **记录此刻**：保存事务后在当日事务列表下方内联显示「📝 记录此刻的想法？」；点「不了」清空提示状态；点「去记录」调用 `core.llm_client.call_llm(expect_json=False)` 生成草稿，写入 `upload_prefill={"description": ..., "topics": ..., "source": "planning"}`，再设置 `_nav_target=("📝 记录台", "⬆️ 上传")` 跳转到上传页

---

## ai_tagging.py

> 「让 AI 帮我选标签」交互组件。基于 `tagging_skill.auto_tag_session`。

### `render_ai_tag_picker(session_data, model_id, state_key, apply_key="") -> None`
- **必须**在 `st.form` 外调用（依赖 `st.button` 即时回写）
- **入参**：
  - `session_data: dict`：含 `description` / `feeling`（至少一项有值）
  - `model_id: str`：当前选中模型；空字符串时显示提示并 return
  - `state_key: str`：本组件独占的 session_state 命名空间（保证唯一）
  - `apply_key: str`：表单内标签 multiselect 的 widget key；点击「应用」时 `del` 此 key 强制 multiselect 重新渲染
- **副作用**：
  - 调 `auto_tag_session` → 写 `_ai_tag_result_{state_key}`
  - 用户勾选 → 写 `_ai_tag_checked_{state_key}`
  - 应用按钮 → 调 `add_tag()` 把 `updated` 中不在 registry 的标签写入 `tags_registry`，写 `_ai_applied_tags_{state_key}`，并把选中标签合并写入 `st.session_state[apply_key]`

### session_state 键空间约定

| 模板 | 含义 |
|------|------|
| `_ai_tag_result_{state_key}` | LLM 返回的三字段 dict |
| `_ai_tag_checked_{state_key}` | 用户当前勾选 |
| `_ai_applied_tags_{state_key}` | 应用按钮按下时的快照——`cards._render_detail` 读此值合并到表单默认 |

### 已知陷阱

- 与 `cards._render_detail` 是**紧耦合**：`apply_key` 必须等于目标标签 multiselect 的 widget key，否则前端无法自动勾选
- 应用按钮按下时即调 `add_tag` 入库；`cards._render_detail` 的入库循环作为 belt-and-suspenders 兼职捕获 session 历史孤儿标签

## ai_fill.py

> 「AI 补全感受与原因」交互组件。基于 `CompletionSkill().execute()`。

### `render_ai_fill_picker(session_data, model_id, state_key, form_prefix) -> None`
- **必须**在 `st.form` 外调用（依赖 `st.button` 即时回写）
- **入参**：
  - `session_data: dict`：至少含 `description`
  - `model_id: str`：当前选中模型；空字符串时显示提示并 return
  - `state_key: str`：本组件独占的 session_state 命名空间（保证唯一）
  - `form_prefix: str`：关联表单的 `render_field_inputs()` prefix；点击「应用」时写入 `{form_prefix}_feeling` / `{form_prefix}_reason`
- **副作用**：
  - 调 `CompletionSkill().execute()` → 写 `_ai_fill_result_{state_key}`
  - 用户应用 → 直接写 `{form_prefix}_feeling` / `{form_prefix}_reason` widget state，清除建议后 `st.rerun()`
  - 用户重新生成 → 清除 `_ai_fill_result_{state_key}` 后 `st.rerun()`

### session_state 键空间约定

| 模板 | 含义 |
|------|------|
| `_ai_fill_result_{state_key}` | LLM 返回的 `{feeling, reason}` 建议 |

### 已知陷阱

- 与 `render_field_inputs` 的 prefix 紧耦合：上传表单传 `upload`；详情表单传 `edit_{safe_sid}`
- 文件夹导入模式不渲染此组件，因为没有可用描述
