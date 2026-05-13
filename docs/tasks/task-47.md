# Task #47 — 新建 core/config.py：部署模式 + 动态路径 + 用户上下文 + 回传配置

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：基础设施 / 重构

新建 `core/config.py`，作为整个部署配置的唯一入口。读取 `.env` 文件中的 `DEPLOY_MODE`（local/cloud）并提供路径解析函数和用户上下文管理。后续 task-48/49 依赖此文件完成各自的路径感知重构。

---

## 目标

建立一个零依赖的配置层，让其他模块通过调用函数（而非读取模块级常量）获取当前路径，为多用户隔离和回传策略提供统一接口。

## 必读契约

- `docs/api/core.md` # constants.py 节（了解现有路径常量）
- `core/constants.py`（直接读源码，了解 DB_PATH / FINAL_DIR 等现有常量的使用方式）

## 改动范围

- **新建**：`core/config.py`
- **新建**：`.env`（本地开发默认配置，加入 `.gitignore`）
- **修改**：`.env.example`（补全所有新增变量的说明）
- **修改**：`requirements.txt`（新增 `python-dotenv`）
- **修改**：`docs/api/core.md`（新增 config.py 节）
- **不许碰**：`core/constants.py`（原有常量保留，config.py 是新增层，不是替换）

## 接口约定

### `core/config.py` 公开接口

#### 部署模式

```
DEPLOY_MODE: str   # "local" | "cloud"，来自 DEPLOY_MODE 环境变量，缺省 "local"
```

启动时若 `DEPLOY_MODE` 不在合法值内，抛出 `ValueError`。

#### 用户上下文（contextvars）

```
set_current_user(username: str | None) -> None
get_current_user() -> str | None
```

- 使用 `contextvars.ContextVar`，天然线程隔离（Streamlit 每 session 独立线程）
- `DEPLOY_MODE == "local"` 时 `get_current_user()` 始终返回 `None`，`set_current_user` 调用静默 no-op
- `DEPLOY_MODE == "cloud"` 时若 `get_current_user()` 返回 `None`，路径函数应抛 `RuntimeError("Cloud 模式下未设置当前用户")`

#### 路径解析函数

```
get_db_path(username: str | None = None) -> Path
get_vector_db_dir(username: str | None = None) -> Path
get_pending_dir(username: str | None = None) -> Path
get_final_dir(username: str | None = None) -> Path
```

- `username=None` 时使用 `get_current_user()` 的返回值
- local 模式路径与 `constants.py` 现有常量完全一致（不改变本地行为）
- cloud 模式路径规则：

| 函数 | 返回路径 |
|------|---------|
| `get_db_path` | `data/users/{username}/database.db` |
| `get_vector_db_dir` | `data/users/{username}/vector_db/` |
| `get_pending_dir` | `data/users/{username}/pending/` |
| `get_final_dir` | `data/users/{username}/final/` |

- 路径函数只返回 `Path` 对象，不负责创建目录（由各自的写入方负责 `mkdir`）

#### 回传配置与触发（Phase C）

```
SYNC_BACKUP_COMMAND: str | None
# 来自环境变量 SYNC_BACKUP_COMMAND，缺省 None
# 示例值："rsync -az {src} user@mynas.local:/backup/mypresent/"

trigger_sync_backup(db_path: Path) -> None
```

`trigger_sync_backup` 行为：
- 仅 `DEPLOY_MODE == "cloud"` 且 `SYNC_BACKUP_COMMAND` 非空时执行
- 用 `str(db_path)` 替换命令模板中的 `{src}` 占位符
- 在 **daemon 线程**中执行 `subprocess.run(cmd, shell=True)`，不阻塞调用方
- 若上一次 sync 线程仍在运行（用模块级 `threading.Lock` 非阻塞检测），本次跳过（避免堆积）
- 执行失败只记录 `logging.warning`，不抛出异常

### `.env` / `.env.example` 变量说明

```
DEPLOY_MODE=local          # local | cloud
SYNC_BACKUP_COMMAND=       # 留空表示不同步；cloud 模式填写 rsync/scp 命令模板，{src} 为 db 文件路径
```

`python-dotenv` 在 `core/config.py` 顶部 `load_dotenv()` 加载，只加载一次。

## 不要做

- 不要删除或修改 `core/constants.py` 中的任何现有常量
- 不要在 `config.py` 中 import streamlit
- 不要在路径函数中自动创建目录
- 不要把 `EMBEDDING_ENABLED` 迁移进来（它目前在 constants.py，不在本卡范围内）

## 验收清单

- [ ] `python -c "from core.config import get_db_path, get_current_user, trigger_sync_backup"` 无报错
- [ ] `DEPLOY_MODE=local`：`get_db_path()` 返回路径与 `constants.DB_PATH` 一致
- [ ] `DEPLOY_MODE=cloud`，`set_current_user("alice")` 后：`get_db_path()` 返回 `data/users/alice/database.db`
- [ ] `DEPLOY_MODE=cloud`，未调用 `set_current_user` 时：`get_db_path()` 抛 `RuntimeError`
- [ ] `trigger_sync_backup` 在 `SYNC_BACKUP_COMMAND` 为空时不执行任何子进程
- [ ] `requirements.txt` 含 `python-dotenv`
- [ ] `.env.example` 含所有变量及说明注释
- [ ] `.env` 已加入 `.gitignore`（检查是否已有，没有则添加）
- [ ] `docs/api/core.md` 新增 config.py 节
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`contextvars.ContextVar` 在 Python 的线程模型中行为：每个线程启动时继承父线程的 Context 副本。Streamlit 为每个 session 创建独立线程，因此 `set_current_user` 在一个 session 线程中调用不会影响其他 session。这是此方案的核心安全假设，无需额外锁。

`trigger_sync_backup` 的 skip 逻辑用 `threading.Lock(acquire(blocking=False))` 实现：拿到锁说明上次 sync 已完成，在新线程里执行后释放；拿不到锁说明上次仍在跑，直接跳过。
