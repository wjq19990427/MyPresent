# Task #19 — DB 层：延期字段 + goal_categories 表 + 新增 CRUD

## 目标

为「规划控制台 v2」提供数据底座：给待办加上延期追踪字段，并将年度规划分类从硬编码常量迁移到数据库表，支持用户动态增删自定义分类。本任务不涉及任何 UI，是 task-20 / task-21 / task-22 的前置依赖。

## 必读契约

- `docs/api/database.md` # 表 13、14 节（现有 schema 约定、`ALTER TABLE` 兼容模式）
- `docs/api/core.md` # `db_manager.py` 节（`_conn()` 上下文、`init_db()` 结构、枚举常量组织位置）

## 改动范围

- **修改**：`core/db_manager.py`
- **更新**：`docs/api/database.md`（表数改为 15，更新 `calendar_todos` 字段，追加 `goal_categories` 说明）
- **更新**：`docs/api/core.md`（追加所有新函数 L2 契约节，更新枚举常量说明）
- **不许碰**：其他任何文件

## 接口约定

### `calendar_todos` 新增两列

`postpone_count` — 整型，默认 0，记录该待办被延期的次数  
`postponed_days` — 整型，默认 0，记录累计延期天数  
- 兼容现有数据库：沿用 `init_db()` 中已有的 ALTER 列存在性检查模式

---

### 新表 `goal_categories`

存储年度规划分类名称及来源（系统内置 / 用户自定义）。

`init_db()` 预填四条系统内置分类：身心健康、亲密关系、事业发展、个人成长；幂等写入。

---

### `postpone_todo(todo_id: str, days: int) -> None`
- 行为：将该待办的执行日期推后 `days` 天，延期次数 +1，累计延期天数 += days
- 副作用：写 `calendar_todos`
- 约束：`days <= 0` 时静默 no-op；不改 `status` 和 `reflection`

---

### `get_goal_categories() -> list[dict]`
- 行为：返回所有分类，系统内置在前，用户自定义在后；每条含 `name`、`is_system` 字段

### `add_goal_category(name: str) -> None`
- 行为：新增一条用户自定义分类
- 约束：`name` 为空或已存在时静默 no-op

### `delete_goal_category(name: str) -> None`
- 行为：删除指定分类
- 约束：系统内置分类静默 no-op，不抛异常；不级联修改已有目标的 `category` 字段

---

### `GOAL_CATEGORIES` 常量

改为仅供 `init_db()` 内部初始化使用；UI 层应改为调用 `get_goal_categories()`。保留导出名以免破坏现有 import，但 L2 契约需标注此用法已过时。

## 不要做

- 不要修改 `annual_goals` 及其他现有表结构
- 不要在 `delete_goal_category` 中级联修改已有目标的 `category` 字段
- 不要实现重复任务自动生成逻辑

## 验收清单

- [ ] `python -c "from core.db_manager import postpone_todo, get_goal_categories, add_goal_category, delete_goal_category; print('OK')"` 通过
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动后 `calendar_todos` 含新两列，`goal_categories` 表存在且含 4 条内置分类
- [ ] `docs/api/database.md` 表数改为 15，字段同步
- [ ] `docs/api/core.md` 新函数契约已追加
- [ ] commit 符合规范（建议 `feat(db): 延期字段 + goal_categories 表 + CRUD · 关联 #19`）
- [ ] worktree 分支提交，未 push main

## 架构师备注

- `goal_categories` 选择独立表而非扩展常量，原因：用户自定义数量不可预测，且需区分是否可删除的权限语义
- task-20 / task-21 均需 import `get_goal_categories`；task-22 需 import `postpone_count` 字段——均依赖本任务先合并
