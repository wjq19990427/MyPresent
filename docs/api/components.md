# components/ — UI 层

> Streamlit 渲染。只消费 `skills/` 和 `core/`，不实现业务逻辑。

## 边界规则

- 业务逻辑禁止写在 Tab 里——下沉到 `skills/` 或 `core/`
- 组件之间最小耦合：通过 `session_state` 或显式回调通信
- 不直接操作 SQLite——所有 DB 访问走 `core/db_manager`

## 组件清单

| 文件 | 职责 | 契约状态 |
|------|------|----------|
| `cards.py` | 共用卡片 / 详情 / 评论 / 结构化标签&分组管理 | ✅ |
| `forms.py` | 表单字段（基于 `FIELD_SCHEMA` 动态渲染） | ✅ |
| `tab_upload.py` | 「记录台」上传子页 | ✅ |
| `tab_gallery.py` | 「待处理」子页 | ✅ |
| `tab_archived.py` | 「已归档」Tab | ✅ |
| `tab_insight.py` | 「洞见」Tab（检索 / 情绪趋势 / 洞察报告） | ✅ |
| `tab_search.py` | 「洞见」检索子组件（日期 + 语义 + 问答） | ✅ |
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
- **功能**：渲染标题区、项目介绍文案，以及「记录台 / 洞见 / 规划台 / 回收站 / 系统」5 个模块卡片
- **入参**：`on_navigate` 可选导航回调；用户点击模块入口时传入目标 key（`record/insight/planning/recycle/system`）
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
- **展示内容**：标题、`content_time`（为空不显示）、记录类型角标、结构化标签 badge、文件数/评论数/相似度
- **标题规则**：优先 `session["title"]`；为空时截取 `description` 前 30 字；仍为空显示「（未命名）」
- **记录类型**：`_infer_record_type(session)` 根据 `source_type` 与文件扩展名推断 `text/image/video/mixed/file`；无文件时回落到 `source_type`
- **结构化标签**：卡片只展示 `domains/attributes/topics`，最多 6 个，超出显示 `+N`；不展示 `emotion_tags`
- **旧字段限制**：卡片不再展示 `upload_time`、完整度 badge、旧 `tags/session_tags`
- **副作用**：渲染缩略图 + 元信息 + 切换按钮；点击按钮写 `st.session_state[state_key]` + `st.rerun()`

### `_render_batch_row(session, selected_key="batch_selected_ids") -> None`
- **入参**：
  - `session`：完整 session dict
  - `selected_key`：保存已选 session_id 集合的 `session_state` 键
- **副作用**：渲染批量管理行（checkbox + 缩略图 + 摘要 + 标签/分组摘要）；勾选变化时写 `st.session_state[selected_key]` 并 `st.rerun()`

### `_render_detail(session, mode, state_key=None) -> None`
- **入参**：`mode = "pending" | "final"`；`state_key` 默认按 mode 推导（搜索 Tab 显式传 `search_selected`）
- **副作用**：
  - 表单保存 → `update_session_fields(sid, ...)`
  - 归档（仅 pending）→ `move_to_final(sid)`
  - 删除按钮 → `soft_delete_session(sid)`，清空选中态并关闭详情面板
  - 纯文字 session 直接重写源 .txt 文件
  - AI 内容生成只写入当前详情页建议缓存；字段建议逐条采纳后才写入对应 widget；保存/归档时清空建议缓存
  - AI 标签建议只写入话题多选框与新标签缓存；保存/归档前才将用户实际选中的新标签通过 `add_label` 入库
- **依赖组件**：`forms.render_field_inputs` / `ai_tagging.render_ai_tag_picker` / `_render_comments`
- **已知陷阱**：widget key 用 `safe_sid = "".join(c if c.isalnum() else "_" for c in sid)` 净化，避免 streamlit 对特殊字符报错
- **AI 功能位置**：详情页字段编辑区上方提供「✨ AI 生成内容」，仅生成 `title/summary/feeling/reason/emotion_note` 的内联建议；「🤖 AI 建议标签」只填入话题多选框；详情页不再渲染旧的整体 AI 分析面板，也不再提供 StorySkill 摘要入口
- **保存控件**：详情页使用普通 `st.button` 即时按钮，不再用 `st.form`，避免 AI 组件写入 widget state 后前端不刷新

### `_render_comments(session) -> None`
- **必须**在 `st.form` 外调用（依赖 `st.button` 即时回写）

### `_render_label_manager() -> None` / `_render_group_manager() -> None`
- 标签库：使用四维 `label_registry`，sub-tab 为领域 / 视角 / 话题 / 情绪
- 标签新增：调用 `add_label(name, type)`；空名称由 UI 拦截
- 标签删除：仅用户自定义标签显示删除按钮；点击后统计对应结构化字段引用数并展示确认区，确认后调用 `remove_label_cascade(name, type)` 从标签库和已有记录引用中同步移除；系统标签只显示 `🔒 系统`
- 分组：删分组同步清 `archived_group_filter`

### 内部辅助

- `_session_thumb(session)`：图片返回路径；视频取首帧 PNG bytes
- `_completion_badge(session)`：调 `validate_session`，返回带 emoji 的状态字符串

---

## forms.py

> `FIELD_SCHEMA` 驱动的表单字段渲染。新增字段类型只需在此增加分支。

### `render_field_inputs(prefix, defaults=None, skip_keys=None, suggestions=None, suggestions_key="") -> dict`
- **入参**：
  - `prefix: str`：widget key 前缀（同页面多次渲染必须不同前缀）
  - `defaults: dict | None`：字段默认值（通常传 session 或 `{}`）
  - `skip_keys: set | None`：跳过的字段；返回值仍包含这些 key 的 `defaults` 原值
  - `suggestions: dict[str, str] | None`：字段级 AI 文本建议；仅对 `textarea` / `text` 字段渲染内联建议块
  - `suggestions_key: str`：建议 dict 在 `st.session_state` 中的键；采纳后从该 dict 删除对应字段
- **返回**：`{key: 用户输入值}`，覆盖 `FIELD_SCHEMA` 全部字段
- **副作用**：在当前 streamlit 容器渲染输入框；写 widget state（`{prefix}_{key}` 或带 `_date`/`_text` 后缀）
- **建议块**：若 `suggestions[key]` 非空，在输入框下方显示 `🤖 AI 建议` 与「✓ 采纳」按钮；采纳会覆盖该 widget 当前值、删除对应建议并 `st.rerun()`；`date_or_text` 不显示建议块

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

> 「记录台」上传子页。三种上传模式：上传文件 / 粘贴文字 / 文件夹批量导入。

### `render_upload_tab() -> None`
- **副作用**：归档调 `save_session_final`；暂存调 `save_session_pending`；文件夹模式调 `import_folder_to_pending`
- **依赖 session_state**：`upload_key`（计数器，提交后 +1，触发 `file_uploader` 重置）/ `upload_prefill`（规划台跳转预填数据，消费后清空）
- **预填行为**：若 `upload_prefill` 存在，上传页切换到「📝 粘贴文字」，显示 `st.info("✍️ 已从今日规划预填内容，可继续扩充")`，将 `description` 写入粘贴文本框，将 `topics` 补入结构化话题标签并默认选中，然后立即清空 `upload_prefill`
- **AI 分析保存**：上传页的统一 AI 分析结果会写入上传表单与结构化标签控件；保存/归档时透传 `domains/attributes/topics/emotion_tags/emotion_note/summary`，并以 `topics` 作为 `tags` 参数桥接旧 `session_tags`
- **新标签入库时机**：AI 采纳和规划台预填只写入 `st.session_state`；`_structured_options()` 会把当前已选值合并进 options。仅在「完成并归档」或「暂存到待处理」提交前，对用户实际选中的结构化标签与 `label_registry` 比对后调用 `add_label()` 入库。

### 内部子组件

- `_pasted_filename(text) -> str`：粘贴模式自动生成文件名（首行前 20 字符 + `.txt`）
- `_pick_folder_dialog() -> str`：调用 Windows 文件夹选择器，取消时返回空字符串
- `_get_uploaded_filenames() -> set[str]`：从 `data/pending|final` 递归提取已落盘文件的原始文件名，用于扫描结果去重
- `_render_folder_import()`：选择文件夹 → 递归扫描 → multiselect → 模式选择（独立 / 合并） → 导入；文件夹导入不要求预选标签，导入后进入待处理再统一处理

### 强制约束

- 不再渲染旧 `upload_tags` multiselect，也不再要求旧标签必填；归档仍校验 `validate_session`，暂存只警告缺失必填字段
- 归档前必校验 `validate_session`，缺必填字段拒绝放行（暂存时仅警告不阻断）
- 文件夹模式 `field_values={}` 且不传默认标签——直接以空字段暂存到 pending

### 已知陷阱

- `upload_key` 自增是 streamlit 重置 file_uploader 的标准技巧——勿删
- 上传页布局顺序为 AI 分析面板、必填信息、结构化标签、摘要、操作按钮；应用结果通过返回值交给 `tab_upload.py` 写入上传表单 state
- 上传文件 / 粘贴文字模式渲染统一 AI 分析组件；组件返回采纳结果后，由本 Tab 写入 `upload_title` / `upload_summary` / `upload_feeling` / `upload_reason` 等表单 widget state
- 文件夹导入路径保存在 `folder_selected_path`；切换路径时清空 `folder_scan_results`
- 文件夹扫描会按原始文件名排除已上传文件，并把跳过数量写入 `folder_scan_skipped_n`

---

## ai_analysis.py

> 上传草稿统一 AI 分析面板。详情页当前不再渲染整体 AI 分析面板，改由 `cards._render_detail()` 内的内容建议与标签建议分别处理。

### `render_ai_analysis(draft: dict, model_id: str, *, state_key="upload") -> dict | None`
- **入参**：
  - `draft`：上传表单当前字段值，至少含 `description`
  - `model_id`：当前选中的 LLM 模型 ID
  - `state_key`：调用方提供的状态命名空间，默认 `"upload"`
- **行为**：
  - 初始显示「✨ AI 分析」按钮；点击后通过 `_analysis_panel_open_{state_key}` 就地展开内联分析面板，再次点击「▲ 收起 AI 分析」收起
  - 内联面板内的「✨ AI 分析」按钮调用 `AnalysisSkill().execute_draft(draft, model_id, fields="all")`；分析完成后自动保持展开
  - 结果面板按字段展示标题、摘要、领域、视角、话题、情绪、情绪描述、感受、原因；领域/视角/话题/情绪使用 badge 展示
  - 每个字段支持「↺ 重生成」展开三级 hint：无 hint 再试一次、字段预设快捷 hint、自定义 hint
  - 局部重生成只调用对应字段并合并回缓存，不清空其他字段
  - 支持「全部采纳」与逐项勾选后「采纳勾选项」；`new_topics` 合并到话题行内显示，并标注为新标签
- **返回**：用户采纳后返回已选字段 dict；未操作时返回 `None`
- **副作用**：读写 `st.session_state` 的 `_analysis_result_{state_key}` / `_analysis_field_states_{state_key}` / `_analysis_apply_payload_{state_key}`；不直接写 DB，不直接写上传表单 widget
- **约束**：不得替代 `tab_upload.py` 做入库；调用方负责把返回值写入表单或标签控件

### `render_session_ai_analysis(session: dict, model_id: str, *, state_key: str) -> dict | None`
- **入参**：
  - `session`：已有记录 dict，必须含 `session_id`
  - `model_id`：当前选中的 LLM 模型 ID
  - `state_key`：调用方提供的状态命名空间，避免上传页与多个详情面板互相污染
- **行为/返回**：与 `render_ai_analysis()` 相同；底层调用 `AnalysisSkill.execute_draft(session, ...)`，使用调用方传入的当前 UI 草稿，避免待处理记录 DB 字段为空时二次查库导致「内容为空」
- **约束**：保留给未来复用；当前详情页不再调用此整体分析面板；不直接写 DB，调用方负责把采纳结果写回 UI widget 和 `update_session_fields()`

---

## tab_gallery.py

> 「待处理」子页。展示所有 pending 记录，按上传时间倒序。

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

> 「已归档」Tab。全部筛选视图 + 分组相册视图 + 编辑入口 + 结构化标签库&分组管理。

### `render_archived_tab() -> None`
- **依赖 session_state**：
  - 视图态：`archived_view_mode`（`"all"` / `"groups"`）/ `archived_group_selected`
  - 过滤态：`archived_type_filter` / `archived_group_filter` / `archived_domain_filter` / `archived_topic_filter` / `archived_emotion_filter`
  - 选中态：`archived_selected`
- **依赖**：`cards._render_card` / `_render_detail` / `_render_label_manager` / `_render_group_manager`
- **顶部切换**：「📋 全部」保留现有筛选 + 网格 + 批量操作；「📁 分组」进入相册格浏览
- **全部模式批量**：`batch_mode_archived=True` 时改用 `_render_batch_row`，支持批量软删除 / 加入分组 / 取消选择；加入分组通过 `update_session_groups()` 逐条合并目标 group id
- **分组模式**：
  - 分组列表支持通过内联按钮展开/收起新建分组表单；每格展示封面缩略图（第一条 final 记录首个图片/视频缩略图）或首字占位、分组名、记录数、改名、删除
  - 删除分组调用 `delete_group()`，仅删除分组与记录关联，不删除 session
  - 改名不新增 DB API：创建新分组、迁移原分组关联到新 id、删除旧分组
  - 点击分组进入详情，仅按 `load_db()` 返回的 `group_ids` 过滤该组全部 final 记录，不渲染维度筛选
  - 分组详情批量模式支持软删除 / 移出分组 / 取消选择；移出分组调用 `update_session_groups()`
- **结构化筛选**：仅全部模式渲染；默认折叠为 `📍 筛选：全部领域 · 全部话题 · 全部情绪` 摘要行，点击「自定义 ▾」后展开领域、话题、情绪三行 multiselect；摘要在部分选择时显示 `领域：N/M 项`。筛选逻辑不变：同一维度内 OR，跨维度 AND，全部勾选等同于不筛选

### 过滤优先级（AND 链）

```
status==final → 分组(AND) → 文件类型(AND) → 领域OR → 话题OR → 情绪OR
```

### 已知陷阱

- 选中条目若被新过滤条件排除，自动清 `archived_selected`，防止显示已不可见的详情

---

## tab_insight.py

> 「🪞 洞见」Tab。提供洞见内部子页框架、情绪趋势热力矩阵与洞察报告 UI。

### `render_insight_tab() -> None`
- **功能**：通过 `insight_sub_tab` 渲染三个内部子页：「🔍 检索」/「🌈 情绪趋势」/「📋 洞察报告」
- **检索子页**：直接调用 `tab_search.render_search_tab()`，保持原日期过滤 / 语义检索 / 智能问答行为不变
- **情绪趋势子页**：调用本模块内部情绪趋势渲染流程，展示筛选区、热力矩阵与下钻记录列表
- **洞察报告子页**：渲染时间范围、评分模式、模型选择、「一键生成全部」与五个报告段落 expander
- **依赖 session_state**：`insight_sub_tab` / `insight_date_start` / `insight_date_end` / `_insight_report_{section}` / `_insight_report_signature`
- **约束**：本模块不直接操作 `emotion_scores` 表；报告内容仅缓存在 `session_state`，不写 DB；业务生成委托 `InsightReportSkill`

### 情绪趋势子页

- **数据范围**：仅读取 `load_db()` 返回的 `status == "final"` 记录；优先按可解析的 `content_time` 过滤，无法解析时回退到 `upload_time`
- **筛选控件**：开始日期 / 结束日期默认最近 90 天；时间粒度支持 `week / month / year`，默认月；评分模式支持 `quick / precise`，默认快速
- **情绪集合**：行集合来自筛选结果中 `emotion_tags` 的并集，按 `get_label_registry("emotion")` 顺序优先，其余新增情绪按名称排序补齐；无情绪标签时显示空态提示
- **热力矩阵**：使用 plotly `go.Heatmap`；每个情绪单独一条单行 trace，颜色为白色到该情绪固定基础色，单元格值为该情绪在该周期内所有记录的平均 score，空值按 0 显示
- **颜色约定**：默认情绪使用组件内部固定 hex；用户新增情绪从备用色池循环分配，不写 DB
- **精准模式**：切换到精准模式显示 LLM 消耗提示与「开始精准分析」按钮；未选择模型时按钮禁用
- **下钻**：plotly 点选单元格后，或使用下钻选择器后，在矩阵下方用 `cards._render_card()` 展示对应记录
- **降级**：若运行环境缺少 plotly，组件显示依赖缺失提示，不影响其它子页

### 洞察报告子页

- **数据来源**：UI 调 `load_db()` 读取 final sessions，根据 `content_time` 过滤时间范围
- **统计预计算**：调用 Skill 前组装 `emotion_scores / emotion_freq / topic_freq / domain_freq / record_dates / linked_goal_ids / weekday_freq / time_bucket_freq / linked_goal_summary`
- **报告段落**：`🌈 情绪画像` / `🗺️ 话题聚焦` / `🔄 行为规律` / `🎯 目标追踪` / `💬 代表语录`
- **交互**：一键生成顺序请求全部段；每个 expander 内的生成/重新生成只请求对应 section，不清空其他缓存
- **缓存失效**：时间范围、评分模式或过滤后的 session id 集合变化时清空 `_insight_report_*`
- **目标段**：当前时段无关联目标时显示提示，不触发 LLM
- **代表语录**：按引用块展示 `quotes` 数组

---

## tab_search.py

> 「洞见 / 检索」子组件。三种模式：日期过滤 / 语义检索 / 智能问答。

### `render_search_tab() -> None`
- **模式切换**：`_search_mode_prev` 不等于当前模式时清空所有结果与选中态
- **依赖 session_state**（按模式）：
  - 通用：`search_selected` / `search_mode` / `_search_mode_prev`
  - 日期：`date_filter_exact` / `date_filter_fuzzy` / `date_filter_range` / `_period_story_*`
  - 语义：`semantic_results` / `semantic_query_used` / `semantic_query` / `semantic_topk`
  - 问答：`llm_chat_history`

### 内部子组件

- `_render_date_filter()`：`EMBEDDING_ENABLED=true` 时用 ChromaDB metadata filter（`has_exact_date` + `content_time_num` 范围）；禁用 embedding 时回退到 `load_db()` 的普通日期筛选，不加载向量库；模糊时间记录单独折叠展示；下方支持「✨ 生成阶段回忆录」（调 `StorySkill.run_period`）
- `_render_semantic_search()`：`EMBEDDING_ENABLED=false` 时仅显示 `向量搜索功能当前未启用（EMBEDDING_ENABLED=false）。`；启用时使用 BGE 非对称查询前缀「为这个句子生成表示以用于检索相关文章：」+ Top-K
- `_render_qa()`：`EMBEDDING_ENABLED=false` 时仅显示 `向量搜索功能当前未启用（EMBEDDING_ENABLED=false）。`；启用时 multi-turn chat，调 `llm_client.call(history, model_id)`；失败时弹错误并 `pop` 最后一条 user 消息保持历史一致性

### 已知陷阱

- `_render_qa` / `_render_semantic_search` 直接 import `vector_db._get_collection / _get_embedder` —— 跨层下划线 API 调用，是技术债
- 禁用 embedding 时，模块级 import `_get_collection / _get_embedder` 仍安全；只要渲染路径不调用它们，就不会加载模型或 ChromaDB
- 模式切换会丢弃所有已有结果（包括语义检索的耗时计算）——故意为之，避免界面状态混乱

---

## eval_dashboard.py

> 「📊 运行看板」Tab。LLM 配置管理 + 全局模型选择器 + 调用统计 + 数据操作记录。

### `render_eval_dashboard() -> None`
- 五段：API 配置（折叠）→ 模型选择器 → 修改密码（cloud 已登录用户）→ 调用统计（指标 + 按 Skill 分组 + 最近 N 条）→ 数据操作记录
- 数据来源：`get_llm_logs(limit=500)` / `get_operation_logs(limit=50)`
- **修改密码面板**：仅 `DEPLOY_MODE=="cloud"` 且 `st.session_state["_current_user"]` 存在时渲染；校验原密码、新密码、确认密码均非空且两次新密码一致后调用 `update_user_password()`；成功显示 `密码已修改`，`ValueError` 直接提示给用户
- **用户管理面板**：仅 cloud 管理员可见；支持新增普通用户；用户列表显示总数，并以带边框行展示 `username` 和管理员/普通用户标识

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

> 「规划控制台」Tab。包含「📅 日历 & 日志」与「🎯 年度规划」两个子页。

### `render_planning_tab() -> None`
- **副作用**：渲染规划控制台两个子 Tab；默认入口为「📅 日历 & 日志」，第二个子页为「🎯 年度规划」
- **依赖**：所有数据读写均通过 `core.db_manager` 的 `annual_goals` / `calendar_todos` / `daily_activities` CRUD 与枚举常量

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
- **功能**：月份导航、周一到周日的方格月历、日期选择、日期内待办摘要、事务数量提示、本月事务时长统计、选中日期的待办事宜与今日事务、整月待办列表、新增待办入口
- **依赖 session_state**：`planning_cal_year` / `planning_cal_month` / `planning_cal_date` / `planning_todo_adding` / `planning_todo_parent` / `planning_tree_expanded` / `planning_activity_adding` / `planning_activity_editing` / `planning_activity_prefill`
- **过期迁移**：当当前渲染月份与上次迁移月份不同时，调用 `migrate_overdue_todos(year, month)`；迁移数大于 0 时在顶部显示一次性提示
- **视觉约定**：星期标题与日期格共用同一列规格；日期格使用 HTML 信息块展示日期数字、最多 3 条待办摘要和今日事务数量提示；待办摘要前置小号彩色边框优先级标签；待办与事务之间用分隔线区分，超出显示 `+N 更多`；今日和选中日期有不同高亮
- **交互约定**：选中具体日期后新增待办默认填入该日期；日期视图提供返回月份视图入口，清空 `planning_cal_date`
- **过滤约定**：月历格只统计根级未完成待办；月份模式展示根级未完成待办以及已 moved 的根分支；选中具体日期后的待办列表展示当日根级待办并递归展示其子树
- **统计约定**：月历下方固定渲染 `📊 本月时长统计` 折叠面板，数据来自 `get_monthly_activity_stats(year, month)`；无事务记录时显示 `本月暂无事务记录`
- **注意**：重复规则只存储和展示，不在 UI 层自动生成实例；重复任务不参与跨月自动迁移

#### `_render_month_nav(year: int, month: int) -> None`
- **功能**：渲染月份导航，支持 `◀` / `▶` 逐月翻页，也支持年份与月份直接跳转
- **副作用**：任意月份变更写 `planning_cal_year` / `planning_cal_month`，清空 `planning_cal_date` / `planning_activity_adding` 后 `st.rerun()`

#### `_render_calendar_cell(year, month, day_num, selected_date, day_map, activity_map) -> None`
- **功能**：渲染单个方格日期块；空白日期渲染等高占位；有效日期提供选择按钮
- **视觉约定**：已完成待办摘要使用删除线；有今日事务时显示 `📝 事务｜N 条`；信息块下方使用 `查看` / `已选中` 按钮选择日期；日期格与星期标题保持列对齐

#### `_render_todo_form(selected_date: str | None, year: int, month: int) -> None`
- **渲染条件**：仅当 `planning_todo_adding=True` 时显示
- **功能**：创建根待办或子级待办，字段包括 `content/category/priority/target_date/recurrence/linked_goal_id`；`planning_todo_parent` 有值时创建该父节点下的子级，默认继承父节点分类、优先级、日期、重复规则与关联目标
- **关联目标**：下拉框只展示状态为 `未开始` / `进行中` 的年度目标
- **副作用**：保存时调用 `create_calendar_todo()`；取消/保存后关闭表单

#### `_render_todo_row(todo: dict) -> None`
- **功能**：单条树节点展示、完成 checkbox、展开/折叠、添加子级、编辑、延期、删除、完成复盘、已完成心得展示
- **树形渲染**：待办列表按 `parent_id` 递归渲染；每个非 moved 节点均提供「添加子级」，子级同样递归支持；展开状态保存在 `planning_tree_expanded`；非根节点由 `_render_todo_node()` 在整行外层产生横向缩进，并在左侧 gutter 显示树线/L 形连接线
- **编辑流程**：点击「编辑」打开内联表单，字段与新增一致（内容 / 分类 / 优先级 / 日期 / 重复 / 关联年度目标）；保存调用 `update_calendar_todo()`，同一时间只保留一个 `_todo_editing_{todo_id}` 为打开状态
- **完成流程**：勾选未完成节点时调用 `update_todo_subtree_state(todo_id, "done")`，该节点及全部未 moved 后代立即显示删除线与变暗；随后显示“是否将此项及其子任务移入已完成事务？”确认区。确认移入后进入含开始/终止时间的完成表单；保存后调用 `mark_todo_subtree_moved()`，分支永久置灰且禁止交互。选择仅标记完成则保留 done 状态，不写事务。
- **父节点完成判定**：渲染时若父节点全部直接/间接叶子节点均为 done/moved，父节点自动同步为 done；部分完成时 caption 显示 `完成 X/Y`
- **已移入节点**：`todo_state="moved"` 的节点保留在树中，使用现有已完成删除线与置灰样式；checkbox 禁用，添加子级/编辑/延期隐藏，删除禁用；后续批量完成会跳过 moved 节点
- **延期流程**：仅未完成待办显示「延期」入口；展开内联表单后确认调用 `postpone_todo()`；`postpone_count > 0` 时信息行显示延期次数
- **依赖 session_state**：`planning_tree_expanded` / `_todo_move_confirm` / `_todo_pending_move` / `_reflection_open` / `_postpone_open` / `_todo_editing_{todo_id}` / `_compl_start_{todo_id}_hour` / `_compl_start_{todo_id}_minute` / `_compl_end_{todo_id}_hour` / `_compl_end_{todo_id}_minute`

#### `_render_daily_activities(selected_date: str, activities: list[dict], todos: list[dict]) -> None`
- **渲染条件**：仅在选中具体日期时显示
- **功能**：展示该日今日事务列表；提供「记录今日事务」入口；每条事务支持编辑与删除；新增/编辑表单字段为 `description/category/start_time/end_time/duration`
- **编辑流程**：点击事务行「编辑」打开内联表单并预填当前值；保存调用 `update_daily_activity()`；取消关闭表单且不写入；`planning_activity_editing` 保存当前打开的事务 ID
- **时间段**：开始/结束时间为可选下拉，提供 00:00 到 23:30 的 30 分钟刻度与「自定义…」；自定义校验 `HH:MM`，两端均填写时自动计算分钟数并写入 duration，用户仍可手动覆盖；结束时间早于开始时间时提交被阻止并提示
- **预填行为**：事务表单渲染 widget 前消费 `planning_activity_prefill`；若存在则写入 `af_description` / `af_category` 默认值，显示时长填写提示，并立即清空该预填状态
- **统计约定**：事务列表下方、记录此刻提示上方显示当日分类时长汇总；跳过 `duration=0` 的事务，所有事务均无有效时长时隐藏汇总
- **副作用**：新增保存时调用 `create_daily_activity()`；编辑保存时调用 `update_daily_activity()`；删除时调用 `delete_daily_activity()`；保存/取消后关闭对应表单；新增保存成功后写 `planning_record_moment_date` 以显示「记录此刻」入口
- **记录此刻**：保存事务后在当日事务列表下方内联显示「📝 记录此刻的想法？」；点「不了」清空提示状态；点「去记录」调用 `core.llm_client.call_llm(expect_json=False)` 生成草稿，写入 `upload_prefill={"description": ..., "topics": ..., "source": "planning"}`，再设置 `_nav_target=("📝 记录台", "⬆️ 上传")` 跳转到上传页

#### `format_duration(minutes: int) -> str`
- **用途**：规划页内部时长展示格式化工具
- **返回**：`0 -> "0分钟"`；小于 60 分钟返回 `X分钟`；整小时返回 `X小时`；其他返回 `X小时Y分钟`

---

## ai_tagging.py

> 「让 AI 帮我选标签」交互组件。基于 `tagging_skill.auto_tag_session`。

### `render_ai_tag_picker(session_data, model_id, state_key, apply_key="", new_tags_key="") -> None`
- **必须**在 `st.form` 外调用（依赖 `st.button` 即时回写）
- **入参**：
  - `session_data: dict`：含 `description` / `feeling`（至少一项有值）
  - `model_id: str`：当前选中模型；空字符串时显示提示并 return
  - `state_key: str`：本组件独占的 session_state 命名空间（保证唯一）
  - `apply_key: str`：目标标签/话题 multiselect 的 widget key；点击按钮后直接合并写入该 key
  - `new_tags_key: str`：未入库新标签的 session_state key；调用方保存时负责写入正式标签库
- **副作用**：
  - 点击「🤖 AI 建议标签」后调用 `auto_tag_session`
  - 将 `suggested_tags + new_tags` 去重合并写入 `st.session_state[apply_key]`
  - 将 `new_tags` 合并写入 `st.session_state[new_tags_key]`，不写 DB
  - 触发 `st.toast("AI 建议标签已更新，确认后保存生效")` 后 `st.rerun()`

### session_state 键空间约定

| 模板 | 含义 |
|------|------|
| `_ai_tag_result_{state_key}` | LLM 返回的三字段 dict，用于保留 reasoning |
| `{new_tags_key}` | AI 新生成且尚未入库的标签列表 |

### 已知陷阱

- 与 `cards._render_detail` 是**紧耦合**：当前详情页传入 `apply_key=f"{safe_sid}_topics"`，AI 标签直接填入「话题」多选框
- 组件不再调用 `add_tag`；新标签保存前只存在于 session_state，详情页保存/归档时通过结构化标签持久化逻辑写入 `label_registry(type="topic")`
- Streamlit multiselect 不能给单个选项染色；AI 新标签由 `cards.py` 在话题多选框下方以橙色提示块展示

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
