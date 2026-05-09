# Task #27 — 标签体系常量 + Schema 扩展 + 迁移函数

## 目标

在 `constants.py` 写入 L-A-T 标签与情绪的默认种子值；新建 `label_registry` 统一注册表（支持四种标签类型的动态增删）；在 `sessions` 表加入结构化标签列；新建 `session_linked_goals` 表；提供一次性迁移函数把旧 `session_tags` 数据平移到新 `topics` 字段。

## 必读契约

- `docs/api/core.md` # `constants.py` 节 + `db_manager.py::初始化` 节
- `docs/api/database.md` # 1. sessions + 跨表不变量

## 改动范围

- **修改**：`core/constants.py`
- **修改**：`core/db_manager.py`
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/database.md`
- **不许碰**：`session_tags` / `tags_registry` 表定义（保留，不删除，向量 embedding 仍依赖）
- **不许碰**：现有任何 CRUD 函数签名（task-28 处理）

## 接口约定

### constants.py 新增常量（默认种子值，`init_db()` 灌入 label_registry）

```python
DOMAINS    = ["个人成长", "情绪感受", "工作经验", "人际关系", "兴趣爱好", "财务理财"]
ATTRIBUTES = ["反思避坑", "灵光一现", "阶段里程碑", "干货总结", "疑问困惑", "日常流水"]
EMOTIONS   = ["喜悦", "平静", "充实", "期待", "疲惫", "焦虑", "愤怒", "失落", "迷茫"]
TOPICS     = []   # 无默认值，纯动态
```

四种类型均支持多选，均支持动态增删（通过 label_registry 表管理）。

### label_registry 表（新建）

| 列名 | 类型 | 约束 |
|---|---|---|
| `name` | TEXT | NOT NULL |
| `type` | TEXT | NOT NULL，取值：`'domain'` / `'attribute'` / `'topic'` / `'emotion'` |
| `is_system` | INTEGER | NOT NULL, default `0` |
| **PK** | — | `(name, type)` |

`init_db()` 启动时把上面四组常量用 `INSERT OR IGNORE` 灌入，对应 `is_system=1`。

### sessions 表新增列（ALTER TABLE，幂等）

| 列名 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `domains` | TEXT | `'[]'` | JSON 数组，多选 |
| `attributes` | TEXT | `'[]'` | JSON 数组，多选 |
| `topics` | TEXT | `'[]'` | JSON 数组，多选 |
| `emotion_tags` | TEXT | `'[]'` | JSON 数组，多选 |
| `emotion_note` | TEXT | `''` | 情绪描述文本 |

注意：列名为 `domains`（复数），与旧版 `domain` 不同。

### session_linked_goals 表（新建）

| 列名 | 类型 | 约束 |
|---|---|---|
| `id` | TEXT | PK（`YYYYMMDD_HHMMSS_ffffff`） |
| `session_id` | TEXT | NOT NULL, FK → sessions(id) ON DELETE CASCADE |
| `goal_id` | TEXT | NOT NULL, FK → annual_goals(id) ON DELETE CASCADE |
| `ai_reasoning` | TEXT | default `''` |
| `created_at` | TEXT | NOT NULL |
| UNIQUE | — | `(session_id, goal_id)` |

### 迁移函数

`migrate_tags_to_topics() -> int`
- 行为：读每条 session 在 `session_tags` 中的标签 → 序列化为 JSON 写入 `sessions.topics`；仅处理 `topics = '[]'` 或空的行（幂等）；`domains` 置 `'["未分类"]'`（仅当为 `'[]'` 或空时）
- 副作用：批量 UPDATE `sessions`
- 返回：实际更新的行数
- 约束：不删除 `session_tags` 已有数据

### init_db() 更新

- 新建 `label_registry` 表，灌入四组默认种子
- `ALTER TABLE sessions ADD COLUMN` 新增五列（捕获 duplicate column 异常实现幂等）
- 新建 `session_linked_goals` 表
- 启动时自动调用 `migrate_tags_to_topics()`

## 不要做

- 不要删除 `session_tags` 表或 `tags_registry` 表
- 不要修改 `_row_to_dict`、`load_db`、`create_session` 等 CRUD 函数（task-28 处理）
- 不要给 constants.py 的新常量写注释块

## 验收清单

- [ ] `python -c "from core.constants import DOMAINS, ATTRIBUTES, EMOTIONS, TOPICS; print(len(DOMAINS))"` 输出 `6`
- [ ] `streamlit run app.py` 启动后：`sessions` 表含 `domains/attributes/topics/emotion_tags/emotion_note` 五列，`label_registry` 和 `session_linked_goals` 表存在
- [ ] `label_registry` 中 `type='domain'` 的行有 6 条，`is_system=1`
- [ ] 在已有数据库上重复启动两次，无报错（幂等验证）
- [ ] `migrate_tags_to_topics()` 返回值 ≥ 0，不抛异常
- [ ] 已同步更新 `docs/api/core.md` + `docs/api/database.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

SQLite 不支持 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`，标准做法是 `try/except OperationalError` 捕获 "duplicate column name" 静默跳过。`label_registry` 的设计参考 `goal_categories`（同有 `is_system` 保护系统默认值），UI 层删除时应检查 `is_system=0`，DB 层不做保护（与现有 `remove_tag` 策略一致）。
