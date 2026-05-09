# Task #28 — CRUD 接口更新 + 标签注册表方法 + 目标关联方法

## 目标

更新 `db_manager.py` 的 session 读写逻辑，使新结构化标签字段正确序列化/反序列化；新增 `label_registry` 的 CRUD 方法；新增 session ↔ annual_goal 关联的 CRUD 方法。

**依赖**：task-27 必须先合并（新列、`label_registry`、`session_linked_goals` 表须已存在）。

## 必读契约

- `docs/api/core.md` # `db_manager.py::Session CRUD` 节 + `Goal Categories` 节（参考 label_registry 的实现模式）
- `docs/api/database.md` # 1. sessions + label_registry + session_linked_goals

## 改动范围

- **修改**：`core/db_manager.py`
- **修改**：`docs/api/core.md`
- **不许碰**：`core/constants.py`、任何 `components/` 文件、`skills/`

## 接口约定

### 现有函数更新（签名变更，需兼容旧调用方）

`_row_to_dict(row, cursor)`
- 新增反序列化：`domains` / `attributes` / `topics` / `emotion_tags` 字段读出时 `json.loads`，失败时降级为 `[]`；`emotion_note` 降级为 `''`

`load_db() -> list[dict]` / `get_session(session_id) -> dict | None`
- 返回的每条 session dict 新增字段：`domains` (list) / `attributes` (list) / `topics` (list) / `emotion_tags` (list) / `emotion_note` (str)

`create_session(..., domains=None, attributes=None, topics=None, emotion_tags=None, emotion_note='') -> dict`
- 新增可选参数（默认 `None` 等同 `[]`，保持旧调用方兼容）
- 写库时对列表字段 `json.dumps`

`update_session_fields(session_id, new_values: dict) -> None`
- `new_values` 新增接受 `domains / attributes / topics / emotion_tags / emotion_note` 键
- 列表字段写库前 `json.dumps`

### 新增：label_registry CRUD

`get_label_registry(type: str) -> list[dict]`
- 返回指定 type 的所有标签，每条含 `name` / `is_system`；按 `is_system DESC, name ASC` 排序

`add_label(name: str, type: str) -> None`
- 副作用：`INSERT OR IGNORE` 插入 `(name, type, is_system=0)`；`name.strip()` 为空时静默 no-op

`remove_label(name: str, type: str) -> None`
- 副作用：删除指定行；不存在时静默 no-op（DB 层不检查 `is_system`，保护逻辑在 UI 层）

### 新增：session ↔ goal 关联

`link_session_to_goal(session_id: str, goal_id: str, reasoning: str = '') -> None`
- 副作用：`INSERT OR IGNORE` 插入 `session_linked_goals`；已存在时静默 no-op

`unlink_session_from_goal(session_id: str, goal_id: str) -> None`
- 副作用：删除指定关联行；不存在时静默 no-op

`get_linked_goals_for_session(session_id: str) -> list[dict]`
- 返回：JOIN `annual_goals` 的完整 goal dict，额外含 `ai_reasoning` 字段；按 `deadline ASC` 排序

`get_linked_sessions_for_goal(goal_id: str) -> list[dict]`
- 返回：`[{"session_id": ..., "ai_reasoning": ...}]`

## 不要做

- 不要改 `update_session_tags` / `get_tags_registry` 等旧标签方法（保留兼容）
- 不要在新方法里调用 `embed_session` 或触发 `.md` 重写
- 不要改任何 `components/` 文件

## 验收清单

- [ ] `python -c "import core.db_manager as d; s=d.load_db(); print(type(s[0].get('domains')))"` 输出 `<class 'list'>`
- [ ] `create_session(... topics=['深度学习'])` 后 `get_session()` 返回的 `topics` 为 `['深度学习']`
- [ ] `get_label_registry('domain')` 返回 6 条，`get_label_registry('emotion')` 返回 9 条
- [ ] `add_label('冥想', 'topic')` 后 `get_label_registry('topic')` 含该条
- [ ] `link_session_to_goal` 重复调用不报错；`get_linked_goals_for_session` 返回 list
- [ ] 已同步更新 `docs/api/core.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`_row_to_dict` 的 JSON 降级（`except → []`）是必要防御：旧数据迁移后可能有空字符串或 NULL。`label_registry` 的 `remove_label` 不检查 `is_system`，与 `remove_tag` 风格一致——保护逻辑统一放 UI 层，DB 层保持薄。
