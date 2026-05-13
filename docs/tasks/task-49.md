# Task #49 — vector_db / file_io / media 动态路径感知

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：重构

重构 `core/vector_db.py`、`core/file_io.py`、`core/media.py`，使向量库和媒体文件（pending/final）在 cloud 模式下按用户隔离存储。调用方（`components/`、`skills/`）代码不需要任何修改。

---

## 目标

完成非数据库存储层的路径动态化，让每个 cloud 用户拥有独立的向量库和媒体目录，本地模式路径行为不变。

## 必读契约

- `docs/api/core.md` # vector_db.py 节、# config.py 节（task-47 完成后）
- `core/config.py`（task-47 产出，重点：`get_vector_db_dir`、`get_pending_dir`、`get_final_dir`、`get_current_user`）

## 改动范围

- **修改**：`core/vector_db.py`
- **修改**：`core/file_io.py`
- **修改**：`core/media.py`（若有路径依赖，否则跳过）
- **修改**：`docs/api/core.md`（vector_db 节补充 cloud 模式说明）
- **不许碰**：`components/`、`skills/`、`app.py`、`core/db_manager.py`

## 接口约定

### 一、`core/vector_db.py` — per-user 集合缓存

**问题**：`_get_collection()` 使用 `@st.cache_resource`，当前是全局单例。cloud 模式需要每用户独立实例，但 `tab_search.py` 调用 `_get_collection()` 时不传参数，不能改其签名。

**解决方案**：拆分为两层：

内部缓存函数（新建，非公开）：
```
_get_collection_cached(username: str) -> Collection
```
用 `@st.cache_resource` 装饰，以 `username` 为 cache key，每用户一个独立的 ChromaDB 实例，路径来自 `config.get_vector_db_dir(username)`。

公开函数（保留现有签名）：
```
_get_collection() -> Collection
```
内部读取 `config.get_current_user()`，local 模式传固定 key（如 `"__local__"`），cloud 模式传实际 username，转发给 `_get_collection_cached`。

`_get_embedder()` 是模型加载，**不按用户隔离**（所有用户共享同一模型），保持现有 `@st.cache_resource` 不变，仅需确认无路径硬编码。

所有其他公开函数（`embed_session`、`delete_embedding`、`_ensure_indexed` 等）签名不变，内部调用改为走 `_get_collection()`（已经是这样）。

### 二、`core/file_io.py` — 媒体目录动态化

`file_io.py` 中所有直接引用 `FINAL_DIR` / `PENDING_DIR` 常量的位置，替换为调用 `config.get_final_dir(config.get_current_user())` / `config.get_pending_dir(config.get_current_user())`。

写入前确保目录存在（`mkdir(parents=True, exist_ok=True)`）；读取前若目录不存在返回空结果，不报错。

**所有公开函数签名不变**。

### 三、`core/media.py`

读代码确认是否直接使用 `FINAL_DIR` / `PENDING_DIR`；若有则同上替换；若无则跳过，不做修改。

## 不要做

- 不要修改任何公开函数的签名
- 不要改 `tab_search.py`、`app.py` 或任何 `components/` 文件
- 不要更改 `_get_embedder()` 的缓存逻辑（模型是全局共享资源）
- 不要在此卡中处理已有向量数据的迁移（历史数据迁移是后续独立任务）

## 验收清单

- [ ] `DEPLOY_MODE=local`：`streamlit run app.py` 启动，语义检索正常（EMBEDDING_ENABLED=true 下）
- [ ] `DEPLOY_MODE=cloud`，`set_current_user("alice")` 后调用 `_get_collection()`，使用 `data/users/alice/vector_db/`
- [ ] `DEPLOY_MODE=cloud`，alice 和 bob 的 `_get_collection()` 返回不同 ChromaDB 实例
- [ ] `DEPLOY_MODE=cloud`，`save_session_pending(...)` 在 `data/users/{username}/pending/` 下创建文件
- [ ] `DEPLOY_MODE=cloud`，`save_session_final(...)` 在 `data/users/{username}/final/` 下创建文件
- [ ] `DEPLOY_MODE=local` 全量功能回归：文件上传、归档、搜索路径不变
- [ ] `docs/api/core.md` 已同步
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`@st.cache_resource` 的缓存 key 由函数名 + 参数值共同决定。`_get_collection_cached("__local__")` 和 `_get_collection_cached("alice")` 会产生两条独立缓存条目，行为正确。local 模式固定传 `"__local__"` 而非 `None`，是因为 `None` 作为 cache key 可能与 cloud 模式下 `get_current_user()` 返回 None（未设置用户时）发生混淆。

task-48（db_manager）与本卡（vector_db/file_io）改动文件完全不重叠，可与 task-48 同时在两个 worktree 并行执行。
