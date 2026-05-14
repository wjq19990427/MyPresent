# Task #48 — core/db_manager.py 动态路径感知

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：重构

重构 `db_manager.py`，使其在 cloud 模式下为每个用户使用独立的数据库文件。所有上层调用方（`components/`、`skills/`）代码不需要任何修改。本地模式行为与现在完全一致。

---

## 目标

完成后，cloud 模式下每位用户拥有物理隔离的 SQLite 文件，首次写入时自动创建用户目录。现有迁移策略（`ALTER TABLE` + 字段检查）继续沿用，不允许任何破坏性 schema 操作。

## 必读契约

- `docs/api/core.md` # db_manager.py 节、# config.py 节（task-47 完成后的内容）
- `core/config.py`（task-47 产出）

## 改动范围

- **修改**：`core/db_manager.py`
- **修改**：`docs/api/core.md`（补充 cloud 模式路径行为）
- **不许碰**：`core/constants.py`、所有 `components/`、`skills/`、`app.py`

## 接口约定

### 一、`_conn()` 路径动态化

将 `_conn()` 中的 `DB_PATH` 替换为 `config.get_db_path(config.get_current_user())`。连接前对路径的 parent 目录调用 `mkdir(parents=True, exist_ok=True)`（cloud 模式下首次使用自动创建用户目录）。

### 二、`init_db()` 同步更新

`init_db()` 中硬编码的 `DB_PATH` 和 `DB_PATH.parent.mkdir(...)` 同步替换为动态路径，逻辑不变。

### 三、Schema 迁移约束（强制）

检查 `db_manager.py` 全文，确认所有 schema 变更均通过以下方式之一实现，**禁止出现 DROP TABLE / 删库重建**：
- `_add_column_if_missing(conn, table, column, definition)`（现有辅助函数，继续复用）
- 或等价的 `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` 模式

如发现不符合规范的历史代码，在同一 commit 中修正。

### 四、所有公开函数签名不变

40+ 个公开函数签名全部保持不变，调用方无需感知任何变化。

## 不要做

- 不要修改任何公开函数的签名
- 不要在 `db_manager.py` 中 import streamlit
- 不要在 `_conn()` 的 commit/rollback 逻辑之外添加副作用
- 不要删除或重建任何数据表

## 验收清单

- [ ] `DEPLOY_MODE=local`：`python -c "from core.db_manager import init_db; init_db()"` 无报错，`data/database.db` 路径不变
- [ ] `DEPLOY_MODE=cloud` + `set_current_user("alice")`：`init_db()` 后 `data/users/alice/database.db` 被创建
- [ ] `DEPLOY_MODE=cloud`：alice 与 bob 的 `_conn()` 分别指向各自路径（手工验证或单测）
- [ ] `DEPLOY_MODE=local` 全量功能回归：`streamlit run app.py` 启动，归档/读取/删除记录正常
- [ ] `db_manager.py` 全文无 `DROP TABLE` 语句
- [ ] `docs/api/core.md` 已同步
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`_conn()` 是整个 db_manager 的唯一数据库入口，40+ 个公开函数全部经过它。只改这一处（加上 `init_db()` 的路径替换）即可覆盖全部读写路径，是最小改动方案。

`mkdir(parents=True, exist_ok=True)` 放在 `_conn()` 内而非 `config.get_db_path()` 内，是因为路径函数只负责"告知路径"，创建目录是写入方的职责。
