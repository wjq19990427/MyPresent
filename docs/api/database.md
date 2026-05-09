# database.md — SQLite 主库

> `data/database.db` · WAL 模式 · `PRAGMA foreign_keys=ON`
> Schema 单一信息源：`core/db_manager.py::_SCHEMA`

## 表清单（实际 14 张）

| # | 表 | 主键 | 职责 | 契约状态 |
|---|----|------|------|----------|
| 1 | `sessions` | `id` (TEXT) | 主记录 | ✅ |
| 2 | `session_files` | autoinc | session 的文件清单 | ✅ |
| 3 | `session_tags` | (session_id, tag) | session ↔ 标签 多对多 | ✅ |
| 4 | `tags_registry` | `name` | 标签注册表 | ✅ |
| 5 | `groups` | `id` (TEXT) | 分组 | ✅ |
| 6 | `session_groups` | (session_id, group_id) | session ↔ 分组 多对多 | ✅ |
| 7 | `edit_history` | autoinc | Final 字段编辑历史 | ✅ |
| 8 | `comments` | `id` (TEXT) | 评论列表 | ✅ |
| 9 | `llm_providers` | `id` (TEXT) | LLM 提供方 | ✅ |
| 10 | `llm_models` | `id` (TEXT) | 模型（→ provider） | ✅ |
| 11 | `llm_logs` | autoinc | LLM 调用日志 | ✅ |
| 12 | `operation_logs` | autoinc | session 操作审计日志 | ✅ |
| 13 | `annual_goals` | `id` (TEXT) | 年度规划目标 | ✅ |
| 14 | `calendar_todos` | `id` (TEXT) | 日历待办 | ✅ |

---

## 各表 schema

### 1. sessions

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | TEXT | **PK** | session_id（外部生成，时间戳前缀） |
| `status` | TEXT | NOT NULL, default `'pending'` | `'pending'` / `'final'` / `'deleted'` |
| `source_type` | TEXT | NOT NULL, default `'file'` | `'file'` / `'text'` / `'folder'` |
| `content_time` | TEXT | default `''` | 用户填写的内容时间（自由格式） |
| `description` | TEXT | default `''` | 描述（纯文字记录时为正文） |
| `feeling` | TEXT | default `''` | 必填字段（见 `FIELD_SCHEMA`） |
| `reason` | TEXT | default `''` | 选填 |
| `is_complete` | INTEGER | NOT NULL, default `0` | 必填项是否齐全（0/1） |
| `upload_time` | TEXT | NOT NULL | `YYYY-MM-DD HH:MM:SS` |
| `archive_time` | TEXT | default `''` | 归档时刻；pending 为空 |
| `deleted_at` | TEXT | 可空 | 软删除时刻 |
| `pre_delete_status` | TEXT | 可空 | 软删除前状态，用于恢复 |

### 2. session_files

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | INTEGER | PK autoinc |
| `session_id` | TEXT | NOT NULL, **FK → sessions(id) ON DELETE CASCADE** |
| `filename` | TEXT | NOT NULL |
| `original_name` | TEXT | NOT NULL |
| `path` | TEXT | NOT NULL（相对或绝对路径） |

### 3. session_tags

| 字段 | 类型 | 约束 |
|------|------|------|
| `session_id` | TEXT | NOT NULL, **FK → sessions(id) ON DELETE CASCADE** |
| `tag` | TEXT | NOT NULL |
| **PK** | — | (session_id, tag) |

### 4. tags_registry

| 字段 | 类型 | 约束 |
|------|------|------|
| `name` | TEXT | **PK** |

`init_db()` 启动时把 `DEFAULT_TAGS` 用 `INSERT OR IGNORE` 灌入。

### 5. groups

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | TEXT | **PK**（`grp_YYYYMMDD_HHMMSS`） |
| `name` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |

### 6. session_groups

| 字段 | 类型 | 约束 |
|------|------|------|
| `session_id` | TEXT | NOT NULL, **FK → sessions(id) ON DELETE CASCADE** |
| `group_id` | TEXT | NOT NULL, **FK → groups(id) ON DELETE CASCADE** |
| **PK** | — | (session_id, group_id) |

### 7. edit_history

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | INTEGER | PK autoinc |
| `session_id` | TEXT | NOT NULL, **FK → sessions(id) ON DELETE CASCADE** |
| `edited_at` | TEXT | NOT NULL |
| `changes` | TEXT | NOT NULL（JSON 字符串：`{key: {"from", "to"}}`） |

仅当 session.status = `'final'` 时插入；标签/分组变更**不**记录。

### 8. comments

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | TEXT | **PK**（`YYYYMMDD_HHMMSS_ffffff`） |
| `session_id` | TEXT | NOT NULL, **FK → sessions(id) ON DELETE CASCADE** |
| `body` | TEXT | NOT NULL |
| `created_at` | TEXT | NOT NULL |

### 9. llm_providers

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | TEXT | **PK**（`pvd_YYYYMMDD_HHMMSS_ffffff`） |
| `name` | TEXT | NOT NULL |
| `base_url` | TEXT | NOT NULL（保存时去尾 `/`） |
| `api_key` | TEXT | NOT NULL |
| `framework` | TEXT | NOT NULL, default `'openai'` |

`framework` 是新框架扩展点；目前 `_do_call` 仅实现 `'openai'`，其他抛 `NotImplementedError`。

### 10. llm_models

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | TEXT | **PK**（`mdl_YYYYMMDD_HHMMSS_ffffff`） |
| `name` | TEXT | NOT NULL（实际调用时传给 SDK 的 model name） |
| `display_name` | TEXT | NOT NULL, default `''`（UI 展示） |
| `provider_id` | TEXT | NOT NULL, **FK → llm_providers(id) ON DELETE CASCADE** |

### 11. llm_logs

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | INTEGER | PK autoinc |
| `model_id` | TEXT | 可空（**无 FK**，model 删除后日志保留） |
| `skill_name` | TEXT | 可空 |
| `session_id` | TEXT | 可空 |
| `prompt_tokens` | INTEGER | 默认 0 |
| `completion_tokens` | INTEGER | 默认 0 |
| `latency_ms` | INTEGER | 默认 0 |
| `success` | INTEGER | NOT NULL, default `1` |
| `error_message` | TEXT | 失败时填 |
| `created_at` | TEXT | NOT NULL, default `strftime('%Y-%m-%d %H:%M:%S','now','localtime')` |

⚠️ **故意不加 FK**：保留历史调用记录，模型/Provider 删除不影响审计。

### 12. operation_logs

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | INTEGER | PK autoinc |
| `session_id` | TEXT | NOT NULL（**无 FK**，session 永久删除后日志保留） |
| `operation` | TEXT | NOT NULL，枚举：`create` / `update` / `archive` / `delete` / `restore` / `purge` |
| `operated_at` | TEXT | NOT NULL, default `strftime('%Y-%m-%d %H:%M:%S','now','localtime')` |

⚠️ **故意不加 FK**：保留审计历史，session 永久删除不影响操作日志。

### 13. annual_goals

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | TEXT | **PK**（`YYYYMMDD_HHMMSS_ffffff`） |
| `content` | TEXT | NOT NULL |
| `category` | TEXT | NOT NULL |
| `priority` | TEXT | NOT NULL, default `'中'` |
| `deadline` | TEXT | NOT NULL（`YYYY-MM-DD`） |
| `status` | TEXT | NOT NULL, default `'未开始'` |
| `created_at` | TEXT | NOT NULL, default `strftime('%Y-%m-%d %H:%M:%S','now','localtime')` |

### 14. calendar_todos

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | TEXT | **PK**（`YYYYMMDD_HHMMSS_ffffff`） |
| `content` | TEXT | NOT NULL |
| `category` | TEXT | NOT NULL |
| `priority` | TEXT | NOT NULL, default `'中'` |
| `target_date` | TEXT | NOT NULL（`YYYY-MM-DD`） |
| `status` | TEXT | NOT NULL, default `'待办'` |
| `recurrence` | TEXT | NOT NULL, default `'仅一次'` |
| `linked_goal_id` | TEXT | **FK → annual_goals(id) ON DELETE SET NULL**，可空 |
| `reflection` | TEXT | NOT NULL, default `''` |
| `created_at` | TEXT | NOT NULL, default `strftime('%Y-%m-%d %H:%M:%S','now','localtime')` |

---

## 跨表不变量

- 删除 `sessions` 行 → 级联删除 `session_files` / `session_tags` / `session_groups` / `edit_history` / `comments`
- 删除 `groups` 行 → 级联删除 `session_groups`（`update_session_fields` 调用方仍需自行清理 UI 选择状态）
- 删除 `llm_providers` 行 → 级联删除 `llm_models`，但 `llm_logs` 保留
- 删除 `annual_goals` 行 → `calendar_todos.linked_goal_id` 置空，待办本身保留
- 软删除 session 只改 `sessions.status/deleted_at/pre_delete_status`，不触发级联删除；永久删除才触发级联
- 所有事务通过 `_conn()` 上下文管理器，异常自动 rollback
