# Architecture

> L1 项目骨架。改任何模块前，按下表跳转到对应 L2 契约文档。

## 分层与依赖方向

```
components/    UI 层（Streamlit）
    ↓ 只调用
skills/        LLM 插件槽
    ↓ 只调用
core/          基础设施（DB / LLM / 向量库 / 文件 IO / 媒体）
```

- 反向依赖（`core → skills` 或 `core → components`）= 架构违规
- skills 之间不互相调用，统一通过 core 通信

## 模块清单

| 路径 | 职责 | L2 契约 |
|------|------|---------|
| `core/` | DB / LLM / 向量库 / 媒体 / 文件 / 常量 / state | [`api/core.md`](api/core.md) |
| `skills/` | LLM 能力插件（BaseSkill + 各实现） | [`api/skills.md`](api/skills.md) |
| `components/` | UI 渲染（Tabs / Cards / Forms / Dashboard） | [`api/components.md`](api/components.md) |
| `data/database.db` | SQLite 主库（12 表） | [`api/database.md`](api/database.md) |

## 数据流速览

```
用户操作 (Streamlit)
  → components/tab_*.py          收集输入
  → skills/*.py                  调 LLM 处理（可选）
  → core/db_manager.py           写 SQLite
  → core/vector_db.py            同步 embedding
  → core/file_io.py              落盘 data/
```

## 启动入口

- `app.py`（< 35 行）→ `core/state.py` 初始化 → 渲染 5 个 Tab
- 首次部署需 `python migrate.py`（JSON → SQLite + Assets/ → data/）
