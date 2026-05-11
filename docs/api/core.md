# core/ — 基础设施

> 项目最底层。零业务逻辑，仅提供 DB / LLM / 向量 / 文件 / 媒体 / 状态 / 常量。

## 边界规则

- core/ **不得** import `skills/` 或 `components/`
- core/ 内部禁止循环依赖

## 子模块清单

| 文件 | 职责 | 契约状态 |
|------|------|----------|
| `db_manager.py` | SQLite 连接 + CRUD 封装 | ✅ |
| `llm_client.py` | LLM 统一调用层（JSON 重试 + llm_logs 写库） | ✅ |
| `vector_db.py` | ChromaDB + BGE embedding | ✅ |
| `prompts.py` | System Prompts 集中存放 | ✅ |
| `file_io.py` | 文件写入 / 移动 / Markdown 导出 | ✅ |
| `media.py` | 视频缩略图 / 图像格式转换 | ✅ |
| `state.py` | Streamlit `session_state` 初始化 | ✅ |
| `constants.py` | `FIELD_SCHEMA` + 全部常量 | ✅ |

> ⬜ 未填 · 🟡 部分 · ✅ 完整。模板见 [`_TEMPLATE.md`](_TEMPLATE.md)

---

## db_manager.py

> SQLite 主库的唯一访问层。Schema 详见 [`database.md`](database.md)。
> 上层禁止直接 `sqlite3.connect`——一律通过此模块。

### 初始化

#### `init_db() -> None`
- **用途**：创建库 + 全部表（如不存在）+ 灌入 `DEFAULT_TAGS` / `label_registry` 系统种子
- **副作用**：写 `data/database.db`；幂等
- **调用时机**：`app.py` 启动 / `migrate.py`
- **迁移行为**：幂等补齐 `sessions.domains/attributes/topics/emotion_tags/emotion_note/title/summary` 七列；对空 `title` 用 `description[:20]` 回填（不重算历史 `is_complete`），并自动调用 `migrate_tags_to_topics()`

#### `migrate_tags_to_topics() -> int`
- **用途**：一次性把旧 `session_tags` 平移到 `sessions.topics`
- **行为**：仅处理 `topics IS NULL` / 空字符串 / `'[]'` 的 session；将旧标签按名称排序后 JSON 序列化写入 `topics`；当 `domains` 为空或 `'[]'` 时写入 `["未分类"]`
- **副作用**：批量更新 `sessions`；不删除 `session_tags` / `tags_registry`
- **返回**：实际更新的 session 行数；重复调用幂等

### Session CRUD

#### `load_db() -> list[dict]`
- **返回**：所有未软删除 session（按 `upload_time DESC`），每条含 `files / tags / group_ids / edit_history / comments`，业务字段 `title / summary`，以及结构化标签字段 `domains / attributes / topics / emotion_tags / emotion_note`
- **副作用**：无

#### `get_session(session_id: str) -> dict | None`
- **返回**：单条 session 完整 dict，未找到返回 `None`
- **结构化标签**：`domains / attributes / topics / emotion_tags` 返回 list；坏 JSON / 空值降级为 `[]`；`emotion_note` 空值降级为 `''`
- **业务字段**：`title / summary` 空值降级为 `''`

#### `create_session(session_id, file_entries, source_type, field_values, tags=None, status='pending', archive_time='', domains=None, attributes=None, topics=None, emotion_tags=None, emotion_note='', title='', summary='') -> dict`
- **副作用**：插入 `sessions` + `session_files` + `session_tags`；自动计算 `is_complete`
- **结构化标签**：新增可选参数均保持旧调用兼容；列表字段写库前 JSON 序列化，`None` 等同 `[]`
- **标题/摘要**：`title` 可作为可选参数写入，也可由 `field_values["title"]` 写入；`title` 参与 `is_complete`，`summary` 仅存库、不参与完整度
- **返回**：完整 session dict
- **异常**：违反 NOT NULL 约束时抛 `sqlite3.IntegrityError`

#### `update_session_fields(session_id, new_values: dict) -> None`
- **入参**：`new_values` 可含 `FIELD_SCHEMA` 字段（含 `title`）+ 可选 `summary` / `tags` / `group_ids` / `domains` / `attributes` / `topics` / `emotion_tags` / `emotion_note`
- **副作用**：
  - Final 记录额外写 `edit_history`（仅业务字段，标签/分组不计）
  - Final 记录会**重写 `.md`** 并**重新 embed**（隐式调 `file_io._write_md` + `vector_db.embed_session`）
- **不变量**：纯文字 session 跳过 `description` 的 diff（避免误记历史）
- **结构化标签**：列表字段写库前 JSON 序列化；未传入的结构化标签字段保持原值
- **标题/摘要**：`title` 随 `FIELD_SCHEMA` 参与 `is_complete` 和业务字段历史；`summary` 写库但不计入完整度

#### `update_session_tags(session_id, tags: list[str]) -> None`
- **副作用**：替换 `session_tags`；Final 记录会重新 embed（**不**写 `.md`，**不**记历史）

#### `update_session_groups(session_id, group_ids: list[str]) -> None`
- **副作用**：替换 `session_groups`；不触发 embed/md/历史

#### `update_session_files(session_id, file_entries: list[dict]) -> None`
- **副作用**：整体替换 `session_files`（用于 `move_to_final` 路径迁移）

#### `set_session_status(session_id, status, archive_time='', is_complete=1) -> None`
- **副作用**：更新 `sessions` 三个字段；不触发任何 hook

#### `log_operation(session_id: str, operation: str) -> None`
- **副作用**：插入 `operation_logs`；`operation` 约定为 `create/update/archive/delete/restore/purge`

#### `get_operation_logs(limit: int = 100) -> list[dict]`
- **返回**：按 `operated_at DESC` 排序的操作日志 dict 列表

#### `soft_delete_session(session_id: str) -> None`
- **副作用**：将 session 标记为 `status='deleted'`，写入 `deleted_at` / `pre_delete_status`，best-effort 删除向量索引，记录 `delete` 操作日志；不删除磁盘文件

#### `restore_session(session_id: str) -> None`
- **副作用**：将软删除 session 恢复到 `pre_delete_status`；若恢复为 final，best-effort 重建向量索引；记录 `restore` 操作日志

#### `get_deleted_sessions() -> list[dict]`
- **返回**：所有 `status='deleted'` 的 session，按 `deleted_at DESC` 排序

#### `purge_expired_deleted(days: int = 30) -> int`
- **副作用**：永久删除超过 `days` 天的软删除 session 及其磁盘文件，保留 `operation_logs` 审计记录；返回删除数量

### 校验

#### `validate_session(session: dict) -> list[str]`
- **返回**：未填写的必填项 **label** 列表（不是 key）；空 = 全部完整
- **副作用**：无

### Comments

#### `add_comment(session_id, text: str) -> None`
- **副作用**：插入 `comments`；Final 记录重写 `.md`；空文本静默忽略

#### `delete_comment(session_id, comment_id: str) -> None`
- **副作用**：删行；Final 记录重写 `.md`

### Tags Registry

- `get_tags_registry() -> list[str]` ：按 name 升序
- `add_tag(name: str) -> None` ：`INSERT OR IGNORE`，空字符串忽略
- `remove_tag(name: str) -> None` ：默认标签也能删（保护逻辑在 UI 层）

### Label Registry

- `get_label_registry(type: str) -> list[dict]`：返回指定类型标签，每条含 `name/is_system`，按 `is_system DESC, name ASC` 排序
- `add_label(name: str, type: str) -> None`：`INSERT OR IGNORE` 写入用户自定义标签（`is_system=0`）；空名称静默忽略
- `remove_label(name: str, type: str) -> None`：删除指定 `(name,type)`；不存在静默 no-op；系统标签保护在 UI 层处理
- `remove_label_cascade(name: str, type: str) -> int`：在一个事务内删除 `(name,type)`，并从所有 session 对应结构化 JSON 字段移除此标签；`type='topic'` 时同步删除 `session_tags.tag=name`；返回实际更新的 session 行数；标签不存在或 type 非法时静默 no-op

### Groups

- `get_groups() -> list[dict]` ：按 created_at 升序
- `create_group(name: str) -> str` ：返回 `grp_*` ID；空名返回 `''`
- `delete_group(group_id: str) -> None` ：级联删 `session_groups`

### LLM Providers / Models

| 函数 | 副作用 / 异常 |
|------|--------------|
| `get_llm_providers() -> list[dict]` | 按 name 升序 |
| `add_llm_provider(name, base_url, api_key, framework='openai') -> str` | 三项必填，否则 `ValueError`；`base_url` 自动去尾 `/` |
| `remove_llm_provider(provider_id) -> None` | 级联删 `llm_models` |
| `update_llm_provider(provider_id, **kwargs) -> None` | 仅接受 `name/base_url/api_key/framework`，其余忽略 |
| `get_llm_models() -> list[dict]` | 按 name 升序 |
| `add_llm_model(model_name, provider_id, display_name='') -> str` | 校验 provider 存在，否则 `ValueError` |
| `remove_llm_model(model_id) -> None` | 不影响 `llm_logs`（无 FK） |
| `update_llm_model(model_id, **kwargs) -> None` | 仅接受 `name/display_name` |

### LLM Logs

#### `log_llm_call(model_id='', skill_name='', session_id='', prompt_tokens=0, completion_tokens=0, latency_ms=0, success=True, error_message='') -> None`
- **副作用**：插入 `llm_logs`；空字符串自动转 `NULL`
- **调用方**：通常由 `llm_client.call()` 自动调用，业务代码勿手动调

#### `get_llm_logs(limit: int = 200) -> list[dict]`
- **返回**：按 id 倒序，最新在前

### Planning Constants

| 常量 | 值 |
|------|----|
| `_SYSTEM_GOAL_CATEGORIES` | `["身心健康", "亲密关系", "事业发展", "个人成长"]` |
| `GOAL_CATEGORIES` | 兼容导出，指向 `_SYSTEM_GOAL_CATEGORIES`；已过时，UI 分类来源应改用 `get_goal_categories()` |
| `GOAL_STATUSES` | `["未开始", "进行中", "已完成", "已搁置"]` |
| `GOAL_PRIORITIES` | `["高", "中", "低"]` |
| `TODO_CATEGORIES` | `["工作", "学习", "生活", "社交", "娱乐"]` |
| `TODO_RECURRENCES` | `["仅一次", "每天", "每周", "每月", "每年"]` |
| `TODO_PRIORITIES` | `["高", "中", "低"]` |

### Annual Goals

#### `create_annual_goal(content: str, category: str, priority: str, deadline: str, status: str = "未开始") -> dict`
- **副作用**：插入 `annual_goals`；ID 使用 `datetime.now().strftime("%Y%m%d_%H%M%S_%f")`
- **返回**：新建目标 dict

#### `get_annual_goals(status_filter: list[str] | None = None) -> list[dict]`
- **返回**：年度目标列表，按 `deadline ASC` 排序；传 `status_filter` 时只返回指定状态

#### `get_annual_goal(goal_id: str) -> dict | None`
- **返回**：单条年度目标，未找到返回 `None`

#### `update_annual_goal(goal_id: str, **fields) -> None`
- **副作用**：更新 `content/category/priority/deadline/status`；其他字段静默忽略；空更新直接返回

#### `delete_annual_goal(goal_id: str) -> None`
- **副作用**：删除年度目标；关联的 `calendar_todos.linked_goal_id` 自动置空

### Session ↔ Annual Goal Links

#### `link_session_to_goal(session_id: str, goal_id: str, reasoning: str = '') -> None`
- **副作用**：向 `session_linked_goals` 插入关联；已存在时静默 no-op（`INSERT OR IGNORE`）
- **不变量**：不触发 embedding，不重写 `.md`

#### `unlink_session_from_goal(session_id: str, goal_id: str) -> None`
- **副作用**：删除指定关联；不存在时静默 no-op

#### `get_linked_goals_for_session(session_id: str) -> list[dict]`
- **返回**：该 session 关联的年度目标完整 dict（JOIN `annual_goals`），额外含 `ai_reasoning`，按 `deadline ASC` 排序
- **副作用**：无

#### `get_linked_sessions_for_goal(goal_id: str) -> list[dict]`
- **返回**：`[{"session_id": ..., "ai_reasoning": ...}]`
- **副作用**：无

### Calendar Todos

#### `create_calendar_todo(content: str, category: str, priority: str, target_date: str, recurrence: str = "仅一次", linked_goal_id: str | None = None) -> dict`
- **副作用**：插入 `calendar_todos`；ID 使用 `datetime.now().strftime("%Y%m%d_%H%M%S_%f")`
- **返回**：新建待办 dict

#### `get_calendar_todos(year: int | None = None, month: int | None = None, status_filter: list[str] | None = None) -> list[dict]`
- **返回**：待办列表，按 `target_date ASC` 排序；传 `year/month` 时返回目标月份记录以及 `recurrence != "仅一次"` 的记录；传 `status_filter` 时再按状态过滤
- **注意**：重复任务本期只存储/展示，不自动生成新实例

#### `get_calendar_todo(todo_id: str) -> dict | None`
- **返回**：单条待办，未找到返回 `None`

#### `get_todos_by_goal(goal_id: str) -> list[dict]`
- **返回**：所有 `linked_goal_id == goal_id` 的待办，全字段 dict（含 `postpone_count` / `postponed_days` / `postponed_months`），按 `target_date ASC` 排序
- **约束**：不过滤状态，已完成与未完成均返回
- **副作用**：无

#### `complete_todo(todo_id: str, reflection: str = "") -> None`
- **副作用**：将待办状态改为 `已完成`，并写入复盘心得
- **不变量**：不修改延期字段

#### `update_calendar_todo(todo_id: str, **fields) -> None`
- **副作用**：更新 `content/category/priority/target_date/status/recurrence/linked_goal_id/reflection`；其他字段静默忽略；空更新直接返回

#### `delete_calendar_todo(todo_id: str) -> None`
- **副作用**：删除待办

#### `postpone_todo(todo_id: str, days: int) -> None`
- **副作用**：将 `target_date` 推迟 `days` 天，`postpone_count += 1`，`postponed_days += days`
- **约束**：`days <= 0` 时静默 no-op；未找到待办时静默 no-op；不修改 `status` / `reflection`

#### `migrate_overdue_todos(target_year: int, target_month: int) -> int`
- **用途**：将目标月份之前的过期、未完成、单次待办自动迁移到目标月份
- **行为**：仅处理 `status != "已完成"`、`target_date < YYYY-MM-01`、`recurrence == "仅一次"` 的待办；迁移后 `postponed_months += 1`
- **日期规则**：保留原日号，若超过目标月份天数则取目标月最后一天
- **返回**：实际迁移条数；同一月份重复调用幂等
- **约束**：不迁移重复任务，不修改 `postpone_todo()` 的按天延期字段

### Daily Activities

#### `create_daily_activity(date: str, description: str, category: str, duration: int = 0, start_time: str = "", end_time: str = "") -> dict`
- **副作用**：插入 `daily_activities`；ID 使用 `datetime.now().strftime("%Y%m%d_%H%M%S_%f")`
- **返回**：新建事务实录 dict，字段含 `id/date/description/category/duration/start_time/end_time/created_at`
- **时间段**：`start_time` / `end_time` 可选，按调用方传入的原始字符串落库；DB 层不自动计算 `duration`
- **约束**：`category` 取值应与 `TODO_CATEGORIES` 一致；DB 层不做 FK 约束

#### `get_daily_activities(date: str) -> list[dict]`
- **返回**：指定日期的事务实录列表，按 `created_at ASC` 排序；每条包含 `start_time` / `end_time`，历史空值降级为 `""`
- **副作用**：无

#### `get_monthly_activity_stats(year: int, month: int) -> dict[str, int]`
- **返回**：指定月份的事务时长统计，形如 `{category: total_minutes}`；仅返回当月有事务记录的分类
- **过滤规则**：按 `daily_activities.date` 的 `YYYY-MM` 匹配指定年月，按 `category` 分组累加 `duration`
- **副作用**：无

#### `delete_daily_activity(activity_id: str) -> None`
- **副作用**：删除指定事务实录

### Goal Categories

#### `get_goal_categories() -> list[dict]`
- **返回**：所有年度规划分类，每条含 `name` 与 `is_system`，按 `is_system DESC, name ASC` 排序
- **用途**：UI 层获取年度规划分类的唯一推荐来源

#### `add_goal_category(name: str) -> None`
- **副作用**：插入用户自定义分类（`is_system=0`）
- **约束**：`name.strip()` 为空或已存在时静默 no-op

#### `delete_goal_category(name: str) -> None`
- **副作用**：删除用户自定义分类
- **约束**：系统分类（`is_system=1`）静默 no-op；不修改已有 `annual_goals.category` 历史值

### 不变量

- 所有公开函数自管事务（`_conn()` 上下文）；异常自动 rollback
- Final 记录的字段更新会**自动**触发 `.md` 重写 + embedding 重建——上层无需手动同步
- `_conn()` / `_load_aux()` / `_row_to_dict()` / `_missing_fields()` / `_is_text_session()` 为内部函数，禁止外部 import

---

## llm_client.py

> 所有 LLM 调用的唯一入口。Skill 层禁止直接起 SDK 客户端。

### 公开 API

#### `call_llm(system_prompt, user_prompt, *, model_id, expect_json=True, skill_name='', session_id='') -> str | dict`
- **用途**：Skill 层首选接口。把 system + user 拼成 messages 后转发给 `call()`
- **返回**：
  - `expect_json=False` → `str`
  - `expect_json=True`  → `dict`（解析后的 JSON）
- **异常**：
  - JSON 解析失败 → `LLMJsonParseError`（`ValueError` 子类）
  - 模型/Provider 未找到 → `ValueError`
  - 底层 SDK 异常（网络/认证）→ 原样冒泡
- **副作用**：自动写 `llm_logs`（成功/失败均写）

#### `call(messages: list[dict], model_id: str, *, expect_json=False, skill_name='', session_id='', max_retries=2) -> str | dict`
- **用途**：底层调用入口。给需要自定义 multi-turn messages 的场景使用
- **JSON 重试机制**：`expect_json=True` 时若解析失败，把原始输出 + 重试提示追加到 messages 重发，最多 `max_retries` 次
- **副作用**：写 `llm_logs`；成功只写一次（最终成功时刻）；失败写一次（最后一次失败）
- **不变量**：`max_retries=2` 表示最多调 LLM **3 次**（首次 + 2 次重试）

#### `call_with_config(messages: list[dict], model: dict, provider: dict) -> str`
- **用途**：新增配置前的连通性测试。绕过 DB 查找，直接用临时 dict 调用
- **副作用**：**不写 `llm_logs`**（测试不污染日志）
- **返回**：纯文本 raw 输出
- **异常**：`NotImplementedError` 当 framework 不是 `'openai'`

### 异常类型

#### `LLMJsonParseError(ValueError)`
- LLM 返回内容无法解析为 JSON 时抛出
- 调用方用 `try/except LLMJsonParseError` 单独捕获以区分「调用失败」vs「输出格式错」

### 不变量

- 所有公开调用都依赖 `db_manager.get_llm_models()` / `get_llm_providers()`——必须先在 SQLite 里有配置
- 仅 `framework='openai'` 框架已实现；扩展点保留在 `_do_call()` 内
- `_do_call()` / `_parse_json()` 为内部函数，禁止外部 import
- `_parse_json()` 容忍 markdown 代码块包裹（` ```json ... ``` `自动剥离）

### 已知陷阱

- `call_with_config` 不写日志 ≠ 永远不出现在看板。某些早期代码可能残留直接走 `call()` 做测试，会污染日志——新代码一律用 `call_with_config`
- `expect_json=True` 时，重试会让 messages 越来越长（追加 assistant 输出 + user 提示），可能撞上 context window；2 次重试是经验上限，不要轻易调高

---

## vector_db.py

> ChromaDB（cosine）+ BGE 中文 embedding。所有公开 API **静默吞异常**——搜索功能可降级，主流程不阻断。

### 公开 API

#### `embed_session(session: dict) -> None`
- **用途**：把 session 的可索引字段（`content_time / description / feeling / reason / tags`）upsert 进向量库
- **副作用**：写 `vector_db/`；任何异常静默吞掉（不抛、不日志）
- **不变量**：embedding 文本为空时静默跳过；`session["session_id"]` 必须存在
- **被谁调用**：`db_manager.update_session_fields` / `update_session_tags` / `file_io.save_session_final` / `file_io.move_to_final`

#### `delete_embedding(session_id: str) -> None`
- **副作用**：从向量库删条目；异常静默吞

#### `index_existing_finals() -> int`
- **用途**：批量补全所有 Final 记录的索引（启动检查 / 手动重建）
- **返回**：本次新增索引的条数（已存在不重复）

### 半公开（仅 `app.py` / `core/state` 链上调用）

#### `_ensure_indexed() -> None`
- 启动时调一次：metadata 缺 `content_time_num` 字段（旧 schema）则全库重建，否则只补未索引
- 用 `st.session_state["_vector_db_ready"]` 单次哨兵保护，多页面切换不会重复执行
- 失败时 `st.warning`，不抛异常

### embedding metadata 字段

每条 embedding 的元数据（用于 `tab_search` 过滤）：

- `session_id` / `content_time_raw` / `content_time_iso` / `content_time_num` / `has_exact_date` / `upload_time` / `archive_time` / `source_type`
- `_parse_date_iso(raw)` 支持的格式：`YYYY-MM-DD` / `YYYY/MM/DD` / `YYYY.MM.DD` / `YYYY-MM` / `YYYY/MM` / `YYYY`

### 已知陷阱

- `embed_session` 异常静默吞——搜索结果不全时，先 `index_existing_finals()` 重建一次再排查
- BGE 模型 `BAAI/bge-small-zh-v1.5` 通过 `@st.cache_resource` 缓存，首次启动会下载（>200 MB）
- 检索时给 query 加非对称前缀的逻辑在 `tab_search.py`，**不**在本模块
- `VECTOR_DB_DIR` 在 `<repo>/vector_db`，**不**在 `data/` 下（与 v4.0.0 媒体目录迁移**不一致**，未来可考虑统一）

## prompts.py

> 所有 LLM System Prompt 与 User 模板的单一信息源。Skill **不得**内嵌字符串，全部从此处导入。

### 常量清单

| 名称 | 用途 | 模板变量 |
|------|------|----------|
| `TAGGING_SYSTEM` | 打标 system | — |
| `TAGGING_USER_TMPL` | 打标 user | `{content}` |
| `STORY_SINGLE_SYSTEM` | 单条摘要 system | — |
| `STORY_SINGLE_USER_TMPL` | 单条摘要 user | `{content_time}` `{description}` `{feeling}` `{reason_section}` |
| `STORY_PERIOD_SYSTEM` | 时间段叙事 system | — |
| `STORY_PERIOD_USER_TMPL` | 时间段叙事 user | `{period}` `{memories}` |
| `ANALYSIS_SYSTEM` | 结构化分析 system | — |
| `ANALYSIS_USER_TMPL` | 结构化分析 user | `{content}` `{fields}` `{registry_section}` `{hint_section}` |
| `PLANNING_RECORD_MOMENT_SYSTEM` | 规划台「记录此刻」草稿生成 system | — |
| `PLANNING_RECORD_MOMENT_USER_TMPL` | 规划台「记录此刻」草稿生成 user | `{date}` `{activities}` `{todos}` |
| `QA_SYSTEM` | 智能问答 system | — |

### 修改原则

- 改 prompt **必须**同步检查 Skill 的解析逻辑（字段名、JSON schema）
- 改完跑一次 `python -m skills.tagging_skill` 本地测试（需设 `TEST_MODEL_ID` 环境变量）
- 新增 Skill 必须在此追加常量；禁止把字符串塞回 Skill 文件

## file_io.py

> 文件落盘 + Markdown 导出。一律按文件类型路由到 `images/` / `videos/` / `text/` 子目录。

### 公开 API

#### `ensure_dirs() -> None`
- **副作用**：创建 `data/{final,pending}/{images,videos,text}` + `vector_db/`
- **幂等**；启动入口 `app.py` 调用

#### `save_session_pending(file_data_list, source_type, field_values, tags=None, domains=None, attributes=None, topics=None, emotion_tags=None, emotion_note='', summary='') -> None`
- **入参**：
  - `file_data_list`：`list[tuple[bytes | file-like, original_name: str]]`
  - `source_type`：`'file'` / `'text'` / `'folder'`
- **副作用**：写 `data/pending/{sub}/`；插 `sessions` 行（status=pending），透传结构化标签与摘要字段
- **不写 .md，不 embed**

#### `save_session_final(file_data_list, source_type, field_values, tags=None, domains=None, attributes=None, topics=None, emotion_tags=None, emotion_note='', summary='') -> None`
- 同上 + 写 `.md` + 写 `vector_db`；`session_id` 由 `datetime.now()` 生成
- **结构化字段**：透传到 `create_session()`，用于上传页 AI 分析结果直接保存

#### `move_to_final(session_id: str) -> None`
- **用途**：物理搬移 pending → final + 更新 DB + 写 .md + embed
- **副作用**：`shutil.move` 文件；改 `session_files.path` 与 `sessions.status/archive_time/is_complete`
- **失败容忍**：源文件不存在则跳过 move，但 DB 仍按 final 标记（与历史行为一致）

#### `import_folder_to_pending(file_paths: list[Path], as_one_session: bool, tags=None) -> int`
- **返回**：创建的 session 条数
- **`as_one_session=True`**：所有文件合并为一条 pending；流式打开避免内存峰值
- **`as_one_session=False`**：每文件一条 pending

### 半公开（被 `db_manager` 调用，不直接暴露给业务/UI）

#### `_write_md(session: dict) -> None`
- **用途**：生成/覆盖 `data/final/{session_id}.md`
- **被谁调用**：`db_manager.update_session_fields / add_comment / delete_comment` / 本模块自身
- **下划线含义**：业务代码与 UI 层禁止直接调，统一通过 `db_manager` 高层函数间接触发
- **不变量**：仅 Final 记录有 .md；pending 不生成

### 内部辅助（私有）

- `_file_subdir(filename) -> 'images' | 'videos' | 'text'`
- `_session_file_type(session) -> str`
- `_write_files(file_data_list, dest_dir, session_id) -> list[dict]`

### 已知陷阱

- 文件名格式固定 `{session_id}_{idx:03d}_{original_name}`——更名规则改动会破坏历史路径索引
- `_write_md` 的 .md 仅供人读 / 导出；**不**参与 embedding 索引（embedding 走 `vector_db._build_embed_text`）

## media.py

> 视频缩略图 + 图像格式转换。两个纯函数，无持久副作用。

### 公开 API

#### `video_thumbnail(video_path: Path) -> PIL.Image.Image | None`
- **用途**：抽视频第一帧 + 叠加「▶ [视频]」黑底白字标签
- **返回**：PIL Image；cv2 读取失败返回 `None`
- **副作用**：cv2 短暂打开文件；自动 `cap.release()`

#### `pil_to_png_bytes(img: PIL.Image.Image) -> bytes`
- **用途**：PIL Image → PNG bytes（喂给 `st.image` 或落盘）

### 已知陷阱

- 损坏 / 不支持编码的视频返回 `None`，调用方自行降级（通常显示文件信息 + 下载按钮）
- 标签像素位置硬编码（`[0,0,90,26]` 黑框 + 字符 `(6,5)`），与缩略图分辨率耦合较紧

## state.py

> Streamlit `session_state` 全部键的初始化清单。新增 UI 状态键**必须**在此登记。

### 公开 API

#### `init_state() -> None`
- **副作用**：将约 25 个键以默认值写入 `st.session_state`（已存在跳过）
- **调用时机**：`app.py` 启动；多次调用幂等

### 当前管理的键（按域分组）

- **导航**：`active_tab` / `active_sub_tab` / `_nav_target`
- **选择状态**：`pending_selected` / `archived_selected` / `search_selected`
- **搜索**：`semantic_results` / `semantic_query_used` / `date_filter_exact` / `_fuzzy` / `_range` / `_search_mode_prev`
- **已归档视图/过滤**：`archived_view_mode`（默认 `"all"`）/ `archived_group_selected`（默认 `None`）/ `archived_type_filter` / `archived_tag_filter` / `archived_group_filter` / `_show_no_tag_only`
- **文件夹批量导入**：`folder_selected_path` / `folder_scan_results` / `folder_scan_skipped_n` / `folder_import_done`
- **上传预填**：`upload_prefill`
- **智能问答**：`llm_selected_model` / `llm_chat_history`
- **LLM 配置编辑**：`_editing_pvd` / `_editing_mdl` / `_draft_provider` / `_draft_model` / `_test_result` / `_draft_test_passed` / `_confirm_edit_pvd` / `_confirm_edit_mdl`
- **杂项**：`upload_key`
- **规划控制台**：`planning_sub_tab`（默认 `"calendar"`） / `planning_goal_editing` / `planning_cat_manager_open` / `planning_goal_filter_status` / `planning_goal_filter_cat` / `planning_cal_year` / `planning_cal_month` / `planning_cal_date` / `planning_todo_adding` / `planning_activity_adding` / `planning_record_moment_date` / `_reflection_open` / `_postpone_open`

### 未在此登记的运行期键（隐式）

- `_vector_db_ready`：由 `vector_db._ensure_indexed()` 首次写入
- 任何由 `setdefault` 散落到组件内的 key 都属于**应在此登记但未登记**的债务

### 命名约定

- `_xxx`（下划线开头）= 内部状态，不在 UI 直接展示
- 业务相关键不要前缀下划线
- 添加新键时同步在 `init_state()` 登记，避免散落

### 导航协议

- `active_tab`：当前激活外层 Tab，默认 `"🏠 主页"`
- `active_sub_tab`：各外层 Tab 的内层激活 sub-tab 字典，默认 `{}`
- `_nav_target`：编程跳转指令，格式为 `(外层Tab名, 子Tab名或 None)`；`app.py` 在渲染导航前消费并置 `None`
- 组件可通过 `st.session_state["_nav_target"] = ("📝 记录台", "⬆️ 上传"); st.rerun()` 跳转到指定页面

### 上传预填协议

- `upload_prefill`：上传页一次性预填数据，默认 `None`
- 结构：`{"description": str, "topics": list[str], "source": "planning"}`
- 消费方：`components/tab_upload.py` 在首次渲染上传页时读取，写入粘贴文本与标签区后立即置 `None`

## constants.py

> 路径、文件格式、UI 列数、默认标签、`FIELD_SCHEMA` 扩展接口。零内部依赖。

### 路径

| 常量 | 值 |
|------|-----|
| `DATA_DIR` | `Path("data")` |
| `FINAL_DIR` | `data/final` |
| `PENDING_DIR` | `data/pending` |
| `DB_PATH` | `data/database.db` |
| `VECTOR_DB_DIR` | `<repo>/vector_db`（**不**在 `data/` 下） |

### 文件格式集合

| 常量 | 内容 |
|------|------|
| `TEXT_EXTS` | `.txt` `.md` |
| `IMAGE_EXTS` | `.jpg` `.jpeg` `.png` `.gif` `.webp` `.bmp` |
| `VIDEO_EXTS` | 13 种（`.mp4` `.mov` `.avi` `.mkv` `.wmv` `.webm` `.flv` `.m4v` `.3gp` `.ts` `.mts` `.mpg` `.mpeg`） |
| `VIDEO_EXTS_PLAYABLE` | `.mp4` `.webm` `.mov` `.m4v` `.ogg`（浏览器原生可播） |
| `SUPPORTED_IMPORT_EXTS` | `IMAGE_EXTS ∪ VIDEO_EXTS ∪ TEXT_EXTS` |

### UI

- `COLS = 3`（卡片网格列数）

### 标签默认值

- `DEFAULT_TAGS = ["个人规划", "生活感悟", "重要记忆", "工作总结", "随笔"]`
- `init_db()` 启动时灌入 `tags_registry`

### L-A-T / 情绪标签种子

| 常量 | 内容 |
|------|------|
| `DOMAINS` | `["个人成长", "情绪感受", "工作经验", "人际关系", "兴趣爱好", "财务理财"]` |
| `ATTRIBUTES` | `["反思避坑", "灵光一现", "阶段里程碑", "干货总结", "疑问困惑", "日常流水"]` |
| `EMOTIONS` | `["喜悦", "平静", "充实", "期待", "疲惫", "焦虑", "愤怒", "失落", "迷茫"]` |
| `TOPICS` | `[]`（无默认值，纯动态） |

`init_db()` 启动时将四组常量灌入 `label_registry`，类型分别为 `domain/attribute/topic/emotion`，系统种子 `is_system=1`。

### `FIELD_SCHEMA` — 字段扩展接口

每个字段的 dict 字段约定：

| 键 | 类型 | 说明 |
|----|------|------|
| `key` | str | 标识；同时是 SQL 列名（业务字段 `content_time / description / feeling / reason / title`） |
| `label` | str | 表单与 .md 中的显示名 |
| `required` | bool | 影响 `is_complete` 与归档放行 |
| `type` | str | `textarea` / `text` / `date_or_text` |
| `placeholder` | str | UI 占位 |
| `help` | str | UI 帮助文字 |

**当前 5 字段**：`content_time`(必) → `description`(必) → `feeling`(必) → `reason`(选) → `title`(必)
**派生**：`REQUIRED_KEYS = [k for f in FIELD_SCHEMA if f["required"]]`

### 扩展规则（重要 · 当前最大紧耦合点）

增字段不止改 `FIELD_SCHEMA`：
1. 在 `FIELD_SCHEMA` 末尾追加（UI / 校验 / .md 自动跟随）✅
2. 在 `db_manager._SCHEMA` 的 `sessions` 表加列 ⚠️
3. 在 `db_manager._row_to_dict` 加字段映射 ⚠️
4. 在 `db_manager.create_session` / `update_session_fields` 字段抽取里加 key ⚠️
5. 在 `init_db()` 的幂等迁移里补 `ALTER TABLE sessions ADD COLUMN ...`，必要时回填历史数据 ⚠️

> 这是当前架构遗留的最大紧耦合点，值得在未来重构里优先打破（候选方案：`sessions` 改为 K/V `session_fields` 表，业务字段全部走 EAV）。
