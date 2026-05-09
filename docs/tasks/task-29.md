# Task #29 — sessions 新增 title / summary 字段

## 目标

为每条记录增加标题与摘要字段：`title` 纳入 `FIELD_SCHEMA` 作为必填项（影响 `is_complete` 计算）；`summary` 仅存库，不进表单流程。同时为存量记录做迁移，避免已归档记录丢失完整状态。

## 必读契约

- `docs/api/core.md` # `constants.py::FIELD_SCHEMA 扩展规则` 节（⚠️ 5 处联动）
- `docs/api/database.md` # 1. sessions

## 改动范围

- **修改**：`core/constants.py`
- **修改**：`core/db_manager.py`
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/database.md`
- **不许碰**：任何 `components/` 文件

## 接口约定

### FIELD_SCHEMA 新增字段（constants.py）

在现有 4 个字段末尾追加：

| key | label | required | type | placeholder |
|---|---|---|---|---|
| `title` | 标题 | `True` | `text` | 为这条记录取个名字 |

### sessions 表新增列（ALTER TABLE，幂等）

| 列名 | 类型 | 默认值 |
|---|---|---|
| `title` | TEXT | `''` |
| `summary` | TEXT | `''` |

### 存量数据迁移（在 init_db 内自动执行）

- 对所有 `title = ''` 的 session，用 `description` 前 20 字填充 `title`（截断到末尾无截字）
- 目的：保持已归档记录的 `is_complete = 1` 不被新必填项破坏

### CRUD 更新（5 处联动）

`_row_to_dict`：新增 `title` / `summary` 字段映射，均以 `or ''` 降级

`create_session`：新增可选参数 `title=''`、`summary=''`，写库

`update_session_fields`：`new_values` 接受 `title` / `summary`；`title` 参与 `is_complete` 计算；`summary` 写库但不计入完整性

## 不要做

- 不要把 `summary` 加入 `FIELD_SCHEMA`
- 不要修改 `validate_session` 对 `summary` 做任何校验
- 不要改任何 `components/` 文件

## 验收清单

- [ ] `from core.constants import FIELD_SCHEMA; print([f["key"] for f in FIELD_SCHEMA])` 末尾含 `'title'`
- [ ] 新建 session 不传 `title` 时 `is_complete=0`；传 `title` 时按原逻辑计算
- [ ] 存量记录重启后 `title` 不为空，`is_complete` 与迁移前一致
- [ ] `get_session()` 返回 dict 含 `title` / `summary` 字段
- [ ] 已同步更新 `docs/api/core.md` + `docs/api/database.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`title` 必填但 AI 可代填——UI 层会在 AnalysisSkill 返回后自动写入，用户最终确认即可。存量迁移截断逻辑：用 Python `[:20]` 按字符截，不要按字节截（避免截断中文）。
