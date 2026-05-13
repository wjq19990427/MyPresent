# Task #48 — core/db_manager.py 动态路径感知

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：重构

重构 `db_manager.py`，使其在 cloud 模式下为每个用户使用独立的数据库文件路径。本地模式行为不变。

---

## 目标

`db_manager.py` 中所有读写操作通过 `core.config` 提供的路径和用户上下文，自动路由到正确的数据库文件，无需改动任何上层调用方（`components/`、`skills/`）的代码。

## 必读契约

- `docs/api/core.md` # db_manager.py 节、# config.py 节（task-47 完成后更新的内容）
- `core/config.py`（task-47 产出，重点：`get_db_path`、`get_current_user`、`trigger_sync_backup`）

## 改动范围

- **修改**：`core/db_manager.py`
- **修改**：`docs/api/core.md`（db_manager 节补充 cloud 模式路径行为说明）
- **不许碰**：`core/constants.py`、所有 `components/`、`skills/`、`app.py`

## 接口约定

### 一、`_conn()` 路径动态化

`_conn()` 中的 `DB_PATH` 替换为 `config.get_db_path(config.get_current_user())`。

### 二、`init_db()` 目录创建

`init_db()` 中的 `DB_PATH.parent.mkdir(...)` 替换为：
- 取 `config.get_db_path(config.get_current_user())` 的 parent
- 调用 `.mkdir(parents=True, exist_ok=True)` 确保目录存在
- 后续 `sqlite3.connect(DB_PATH)` 同步替换为动态路径

cloud 模式下，首次 `init_db()` 会在 `data/users/{username}/` 下创建所有表结构，实现用户数据库的惰性初始化。

### 三、所有其他直接引用 `DB_PATH` 的位置

检索 `db_manager.py` 内所有出现 `DB_PATH` 的位置（除上述两处外如有遗漏一并替换），统一改为调用 `config.get_db_path(config.get_current_user())`。

### 四、公开函数签名

**全部保持不变**。上层代码（`components/`、`skills/`）不需要传入 `username`，也无需感知路径变化。

## 不要做

- 不要修改任何公开函数的签名
- 不要在 `db_manager.py` 中 import streamlit
- 不要修改 `_conn()` 之外的事务管理逻辑
- 不要在 `_conn()` 中添加任何 commit 后的额外副作用

## 验收清单

- [ ] `python -c "from core.db_manager import init_db; init_db()"` 在 local 模式无报错，`data/database.db` 路径不变
- [ ] `DEPLOY_MODE=cloud`，`set_current_user("alice")` 后调用 `init_db()`，`data/users/alice/database.db` 被创建
- [ ] `DEPLOY_MODE=cloud`，两个用户 alice / bob 的 `_conn()` 分别指向各自路径（可用单元测试或手工验证）
- [ ] `DEPLOY_MODE=local` 下全量功能回归：`streamlit run app.py` 启动，归档/读取/删除记录无报错
- [ ] `docs/api/core.md` 已同步
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`_conn()` 是 `db_manager.py` 唯一的数据库连接入口，所有 40+ 个公开函数均通过它访问数据库。只改这一处（加上 `init_db()` 的 `mkdir`）就能覆盖全部读写路径，是最小改动方案。
