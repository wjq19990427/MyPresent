# Task #49 — vector_db / file_io / media 动态路径感知 + OOM 防御

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：重构 / 优化

重构 `core/vector_db.py`、`core/file_io.py`、`core/media.py`，使向量库和媒体文件在 cloud 模式下按用户隔离存储。同时增加内存溢出防御：cloud 模式下若启用本地 embedding，在应用启动时展示醒目警告，提示用户切换至 API 模式以保护服务器稳定性。

---

## 目标

完成后，每位 cloud 用户拥有独立的向量库和媒体目录；低配服务器上意外启用本地 embedding 模型时，用户会在启动阶段获得明确警告而非无声 OOM。本地模式行为不变。

## 必读契约

- `docs/api/core.md` # vector_db.py 节、# config.py 节（task-47 产出）
- `core/config.py`（task-47 产出）

## 改动范围

- **修改**：`core/vector_db.py`
- **修改**：`core/file_io.py`
- **修改**：`core/media.py`（仅当有路径硬编码时；若无则跳过）
- **修改**：`docs/api/core.md`
- **不许碰**：`components/`、`skills/`、`app.py`、`core/db_manager.py`

## 接口约定

### 一、`vector_db.py` — per-user 集合缓存

**现有问题**：`_get_collection()` 是全局 `@st.cache_resource` 单例，cloud 模式下所有用户共享同一向量库。

**解决方案**：拆两层，保持公开签名不变：

```
# 内部缓存函数（新增，私有）
_get_collection_for_user(username: str) -> Collection
# 用 @st.cache_resource 装饰，以 username 为 cache key

# 公开函数（签名不变）
_get_collection() -> Collection
# 内部读 config.get_current_user()，local 模式传 "__local__"，cloud 模式传实际 username
# 转发给 _get_collection_for_user
```

`_get_embedder()` 是模型加载，所有用户共享同一模型实例，保持现有 `@st.cache_resource` 不变。

所有其他公开函数（`embed_session`、`delete_embedding`、`_ensure_indexed` 等）签名不变，内部已通过 `_get_collection()` 间接使用正确路径。

### 二、`file_io.py` — 媒体目录动态化

将所有直接引用 `FINAL_DIR` / `PENDING_DIR` 常量的位置替换为：
- `config.get_final_dir(config.get_current_user())`
- `config.get_pending_dir(config.get_current_user())`

写入前确保目录存在（`mkdir(parents=True, exist_ok=True)`）。读取时若目录不存在，返回空结果，不报错。

**所有公开函数签名不变。**

### 三、`media.py`

读代码确认是否直接引用路径常量；若有则同上替换；若无则跳过，不做任何修改。

### 四、OOM 防御警告

在 `core/vector_db.py` 的 `_ensure_indexed()` 函数入口处（现有函数，在 `app.py` 启动时调用），增加以下判断：

- 条件：`DEPLOY_MODE == "cloud"` 且 `EMBEDDING_ENABLED == True`（`EMBEDDING_ENABLED` 从 `core.constants` 读取）
- 动作：调用 `st.warning("⚠️ 警告：cloud 模式下启用了本地 Embedding 模型，可能导致服务器内存溢出（OOM）。建议将 EMBEDDING_ENABLED 设为 false 并改用 API 进行向量化。")`
- 时机：警告显示后继续执行，不阻断流程（用户可知情后自行处理）

## 不要做

- 不要修改任何公开函数的签名
- 不要改 `tab_search.py`、`app.py` 或任何 `components/` 文件
- 不要更改 `_get_embedder()` 的缓存逻辑
- 不要处理历史向量数据的迁移（属于后续独立任务）

## 验收清单

- [ ] `DEPLOY_MODE=local`：`streamlit run app.py` 启动，语义检索正常（`EMBEDDING_ENABLED=true` 下）
- [ ] `DEPLOY_MODE=cloud` + `set_current_user("alice")` + `EMBEDDING_ENABLED=true`：启动时出现 OOM 警告
- [ ] `DEPLOY_MODE=cloud` + `set_current_user("alice")`：`_get_collection()` 使用 `data/users/alice/vector_db/`
- [ ] alice 和 bob 的 `_get_collection()` 返回不同 ChromaDB 实例
- [ ] `DEPLOY_MODE=cloud`：归档一条记录，文件落在 `data/users/{username}/final/`
- [ ] `DEPLOY_MODE=cloud`：暂存一条记录，文件落在 `data/users/{username}/pending/`
- [ ] `DEPLOY_MODE=local` 全量功能回归：文件路径、向量搜索不变
- [ ] `docs/api/core.md` 已同步
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`@st.cache_resource` 以函数参数为 cache key。`_get_collection_for_user("__local__")` 和 `_get_collection_for_user("alice")` 是不同缓存条目，互不干扰。local 模式固定传 `"__local__"` 而非 `None`，避免与 cloud 模式下未设用户时 `get_current_user()` 返回 `None` 发生 key 混淆。

task-48（db_manager）与本卡改动文件完全不重叠，可在 Wave 2 与 task-48 并行执行。
