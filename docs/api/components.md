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
| `eval_dashboard.py` | 「运行看板」Tab | ✅ |
| `ai_tagging.py` | AI 打标 UI 组件 | ✅ |

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

### `_render_detail(session, mode, state_key=None) -> None`
- **入参**：`mode = "pending" | "final"`；`state_key` 默认按 mode 推导（搜索 Tab 显式传 `search_selected`）
- **副作用**：
  - 表单保存 → `update_session_fields(sid, ...)`
  - 归档（仅 pending）→ `move_to_final(sid)`
  - 纯文字 session 直接重写源 .txt 文件
  - AI 推荐的新标签在保存时通过 `add_tag` 自动入库
- **依赖组件**：`forms.render_field_inputs` / `ai_tagging.render_ai_tag_picker` / `_render_ai_summary` / `_render_comments`
- **已知陷阱**：widget key 用 `safe_sid = "".join(c if c.isalnum() else "_" for c in sid)` 净化，避免 streamlit 对特殊字符报错

### `_render_comments(session) -> None`
- **必须**在 `st.form` 外调用（依赖 `st.button` 即时回写）

### `_render_ai_summary(session) -> None`
- 仅 final 详情页用；缓存 key = `_story_{session_id}`，依赖全局 `llm_selected_model`

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
- **依赖 session_state**：`upload_key`（计数器，提交后 +1，触发 `file_uploader` 重置）

### 内部子组件

- `_pasted_filename(text) -> str`：粘贴模式自动生成文件名（首行前 20 字符 + `.txt`）
- `_render_folder_import()`：扫描 → multiselect → 模式选择（独立 / 合并） → 导入

### 强制约束

- **标签必填**：归档 / 暂存前校验 `upload_tags` 非空
- 归档前必校验 `validate_session`，缺必填字段拒绝放行（暂存时仅警告不阻断）
- 文件夹模式 `field_values={}`——直接以空字段暂存到 pending

### 已知陷阱

- `upload_key` 自增是 streamlit 重置 file_uploader 的标准技巧——勿删
- 上传时「✨ AI」打标只用 `description`，`feeling` 留空（此时用户还没填）

---

## tab_gallery.py

> 「灵感墙」Tab。展示所有 pending 记录，按上传时间倒序。

### `render_gallery_tab() -> None`
- **过滤条件**：`status == "pending"` **且**至少一个文件实际存在
- **网格**：`COLS=3` 列
- **依赖**：`cards._render_card` / `cards._render_detail`
- **依赖 session_state**：`pending_selected`

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

> 「📊 运行看板」Tab。LLM 配置管理 + 全局模型选择器 + 调用统计。

### `render_eval_dashboard() -> None`
- 三段：API 配置（折叠）→ 模型选择器 → 调用统计（指标 + 按 Skill 分组 + 最近 N 条）
- 数据来源：`get_llm_logs(limit=500)`

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
  - 应用按钮 → 写 `_ai_applied_tags_{state_key}` + `del st.session_state[apply_key]`

### session_state 键空间约定

| 模板 | 含义 |
|------|------|
| `_ai_tag_result_{state_key}` | LLM 返回的三字段 dict |
| `_ai_tag_checked_{state_key}` | 用户当前勾选 |
| `_ai_applied_tags_{state_key}` | 应用按钮按下时的快照——`cards._render_detail` 读此值合并到表单默认 |

### 已知陷阱

- 与 `cards._render_detail` 是**紧耦合**：`apply_key` 必须等于详情表单内 multiselect 的 widget key，否则应用无效
- AI 新生成的标签**不**在此组件入库；用户在详情表单点保存时由 `cards._render_detail` 触发 `add_tag`
