# Task #46 — Embedding 功能开关：可停用保护 + API 接入预埋

## 变更说明
> 本节给用户（PM）阅读，不含实现细节。

**类型**：优化 / 基础设施

新增 `EMBEDDING_ENABLED` 环境变量开关。设为 `false` 时，向量模型和 ChromaDB 完全不加载（节省服务器内存），所有写入操作静默跳过，搜索页的语义检索与 AI 问答显示「功能暂未启用」而非报错。开关设为 `true` 时行为与当前完全一致。此卡同时为后续接入 API embedding 预留接口位置。

---

## 目标

在不破坏任何现有功能的前提下，让 embedding 可以被安全地关闭——尤其是在 2C2G 的服务器上，避免因加载 `sentence-transformers` 模型（~300MB）或 ChromaDB 导致 OOM。

## 必读契约

- `docs/api/core.md` # vector_db.py 节
- `docs/api/components.md` # tab_search.py 节

## 改动范围

- **修改**：`core/constants.py`（新增 `EMBEDDING_ENABLED` 常量）
- **修改**：`core/vector_db.py`（所有公开函数加开关保护）
- **修改**：`app.py`（`_ensure_indexed` 调用处加保护）
- **修改**：`components/tab_search.py`（语义检索与问答降级 UI）
- **修改**：`.env.example`（新增 `EMBEDDING_ENABLED=true` 示例）
- **修改**：`docs/api/core.md`
- **不许碰**：`core/db_manager.py` 内部逻辑（其对 `embed_session` / `delete_embedding` 的懒导入在 vector_db 侧做保护后自动变 no-op，无需改调用方）

## 接口约定

### 一、`EMBEDDING_ENABLED` 常量

`core/constants.py` 新增：
```
EMBEDDING_ENABLED: bool  # 读取环境变量 EMBEDDING_ENABLED，缺省值 "true"
```

### 二、`core/vector_db.py` 保护行为

当 `EMBEDDING_ENABLED == False`，以下函数行为变更：

| 函数 | 禁用时行为 |
|------|-----------|
| `embed_session(session)` | 立即 return，不加载模型，不写 ChromaDB |
| `delete_embedding(session_id)` | 立即 return |
| `index_existing_finals()` | return 0 |
| `_ensure_indexed()` | 立即 return |
| `_get_embedder()` | 不得被调用；若被调用抛 `RuntimeError("Embedding 已禁用")` |
| `_get_collection()` | 同上 |

**关键约束**：`SentenceTransformer` 和 `chromadb.PersistentClient` 在 `EMBEDDING_ENABLED=False` 时不得出现在任何执行路径中（包括 `@st.cache_resource` 的 decorator body），以保证进程启动时不触发模型下载或 OOM。

### 三、`app.py` 启动保护

`_ensure_indexed()` 的调用处，用 `EMBEDDING_ENABLED` 做前置判断，为 false 时跳过。

### 四、`tab_search.py` 降级 UI

语义检索子页和 AI 问答子页：在 `EMBEDDING_ENABLED == False` 时，不渲染搜索控件，改为渲染：
```
st.info("向量搜索功能当前未启用（EMBEDDING_ENABLED=false）。")
```
其余子页（日期检索等）不受影响，正常渲染。

### 五、API embedding 预留（不实现，只占位）

`core/vector_db.py` 顶部保留注释占位：
```python
# TODO: 当 EMBEDDING_BACKEND=api 时，替换 _get_embedder() 为远程 API 调用
# 接口草案：embed_via_api(texts: list[str]) -> list[list[float]]
```
不写任何实现代码，只留注释。

## 不要做

- 不要改 `core/db_manager.py` 的任何逻辑（懒导入链路由 vector_db 侧保护即可）
- 不要在禁用时抛出用户可见的异常或 warning（除非被不合理调用）
- 不要修改 `sentence-transformers` / `chromadb` 在 requirements.txt 中的声明（保留依赖，只是不加载）
- 不要新建 `core/config.py`（此卡独立，config.py 属于云部署重构任务）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 无报错
- [ ] `streamlit run app.py` 在 `EMBEDDING_ENABLED=false` 时启动无报错、无模型加载日志
- [ ] 手工：搜索页「语义检索」和「AI 问答」子页显示「功能当前未启用」提示，不报错
- [ ] 手工：归档一条记录 → 无 embedding 报错，记录正常写库
- [ ] 手工：软删除一条记录 → 无 embedding 报错
- [ ] `EMBEDDING_ENABLED=true` 时行为与改动前完全一致（回归）
- [ ] `.env.example` 含 `EMBEDDING_ENABLED=true` 说明注释
- [ ] `docs/api/core.md` vector_db 节已同步
- [ ] commit 符合规范，在 worktree 分支提交，未 push main

## 架构师备注

`db_manager.py` 里对 `embed_session` / `delete_embedding` 的调用均为函数内懒导入（`from .vector_db import embed_session`）。禁用时 vector_db 侧的 early-return 已足够，`db_manager.py` 无需修改。

`_get_embedder` / `_get_collection` 使用 `@st.cache_resource`，decorator 本身不执行 body，只在第一次调用时执行。只要 `tab_search.py` 在禁用时不调用这两个函数，模型就永远不会加载。当前 `tab_search.py` 在模块级 import 了这两个函数对象（但未调用），这是安全的——在渲染函数里加保护判断即可。
