# Task #47 — 基础配置层：core/config.py + .gitignore 加固

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：基础设施 / 重构

新建 `core/config.py` 作为部署配置的唯一入口，读取 `.env` 中的 `DEPLOY_MODE` 并提供路径解析与用户上下文管理，为 task-48/49 提供基础。同时补全 `.gitignore`，确保任何用户数据、密钥或数据库文件永远不会进入 Git 历史。

---

## 目标

完成后，整个项目具备"双态启动"的配置基础：local 模式行为不变；cloud 模式下所有路径动态路由至用户目录。数据安全隔离规则在版本控制层落地。

## 必读契约

- `docs/api/core.md` # constants.py 节
- `core/constants.py`（直接读源码）

## 改动范围

- **新建**：`core/config.py`
- **新建**：`.env`（本地开发用，已在 .gitignore 中忽略）
- **修改**：`.env.example`
- **修改**：`requirements.txt`（新增 `python-dotenv`）
- **修改**：`.gitignore`（补全安全条目）
- **修改**：`docs/api/core.md`（新增 config.py 节）
- **不许碰**：`core/constants.py`（原有常量保留，config.py 是新增层）

## 接口约定

### 一、`core/config.py` 公开接口

#### 部署模式

```
DEPLOY_MODE: str   # "local" | "cloud"，来自环境变量，缺省 "local"
```

模块加载时若值不合法，抛 `ValueError("DEPLOY_MODE 必须为 local 或 cloud")`。

#### 用户上下文

```
set_current_user(username: str | None) -> None
get_current_user() -> str | None
```

- 基于 `contextvars.ContextVar`，线程天然隔离
- `DEPLOY_MODE == "local"` 时：`get_current_user()` 始终返回 `None`，`set_current_user` 静默 no-op
- `DEPLOY_MODE == "cloud"` 时：若 `get_current_user()` 为 `None`，路径函数抛 `RuntimeError("Cloud 模式下未设置当前用户")`

#### 路径解析

```
get_db_path(username: str | None = None) -> Path
get_vector_db_dir(username: str | None = None) -> Path
get_pending_dir(username: str | None = None) -> Path
get_final_dir(username: str | None = None) -> Path
```

`username=None` 时内部调用 `get_current_user()`。路径规则：

| 模式 | 路径 |
|------|------|
| local | 与 `constants.py` 现有常量完全一致 |
| cloud | `data/users/{username}/{db,vector_db,pending,final}` |

路径函数**只返回 Path 对象，不创建目录**。

### 二、`.gitignore` 补全条目

在现有基础上**追加**以下条目（不要删除已有内容）：

```
# 用户数据与媒体文件 - 绝不提交
Assets/
backups/

# 环境配置 - 绝不提交
.env
.env.local

# 数据库文件安全兜底
*.db
*.db-shm
*.db-wal
```

### 三、`.env.example`

```
# 部署模式：local（本地单机）| cloud（云端多用户）
DEPLOY_MODE=local

# Embedding 开关（见 task-46）
EMBEDDING_ENABLED=true
```

### 四、`python-dotenv` 加载

`core/config.py` 顶部调用 `load_dotenv()`，只执行一次。不在其他模块重复调用。

## 不要做

- 不要删改 `core/constants.py` 的任何常量
- 不要在 `config.py` 中 import streamlit
- 不要在路径函数中自动创建目录
- 不要将 `EMBEDDING_ENABLED` 迁移至此文件（它属于 task-46，留在 constants.py）
- 不要在此卡实现登录鉴权逻辑（属于后续 Phase B）

## 验收清单

- [ ] `python -c "from core.config import DEPLOY_MODE, get_db_path, set_current_user, get_current_user"` 无报错
- [ ] `DEPLOY_MODE=local`：`get_db_path()` 返回路径与 `constants.DB_PATH` 一致
- [ ] `DEPLOY_MODE=cloud` + `set_current_user("alice")`：`get_db_path()` 返回 `data/users/alice/database.db`
- [ ] `DEPLOY_MODE=cloud` 未设用户时：`get_db_path()` 抛 `RuntimeError`
- [ ] `DEPLOY_MODE=invalid` 时：模块加载抛 `ValueError`
- [ ] `.gitignore` 含 `Assets/`、`backups/`、`.env`、`*.db` 等新增条目
- [ ] `requirements.txt` 含 `python-dotenv`
- [ ] `.env` 文件本身不出现在 `git status` 的追踪列表中
- [ ] `docs/api/core.md` 新增 config.py 节
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`contextvars.ContextVar` 在 Streamlit 的线程模型中天然隔离：每个用户 session 是独立线程，`set_current_user("alice")` 只影响当前线程的 ContextVar 副本。这是 cloud 模式多租户安全的核心保证，无需额外加锁。

`load_dotenv()` 在进程启动时读取一次 `.env` 文件写入 `os.environ`，之后所有 `os.getenv()` 调用均可获取到值，无需重复加载。
