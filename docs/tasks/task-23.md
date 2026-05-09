# Task #23 — DB 层：daily_activities 表 + CRUD

## 目标

新增「今日事务」记录表，支持用户在具体日期下动态记录已完成的事情、对应分类与时长。本任务不涉及任何 UI，是 task-24 的前置依赖。

## 必读契约

- `docs/api/database.md`（现有 schema 约定、`CREATE TABLE IF NOT EXISTS` 模式）
- `docs/api/core.md` # `db_manager.py` 节（`_conn()` 上下文、`init_db()` 结构、ID 生成约定）

## 改动范围

- **修改**：`core/db_manager.py`
- **更新**：`docs/api/database.md`（表数改为 16，追加 `daily_activities` 说明）
- **更新**：`docs/api/core.md`（追加新函数 L2 契约节）
- **不许碰**：其他任何文件

## 接口约定

### 新表 `daily_activities`

记录某一天用户实际完成的事务，与 `calendar_todos` 独立（一个是计划，一个是实录）。

字段：
- `id` — TEXT PRIMARY KEY，沿用项目 ID 约定
- `date` — TEXT NOT NULL，格式 `YYYY-MM-DD`，表示该事务属于哪天
- `description` — TEXT NOT NULL，事务描述
- `category` — TEXT NOT NULL，分类，取值范围与 `TODO_CATEGORIES` 一致
- `duration` — INTEGER NOT NULL DEFAULT 0，时长（分钟），0 表示未填写
- `created_at` — TEXT NOT NULL，默认数据库本地时间

---

### `create_daily_activity(date: str, description: str, category: str, duration: int = 0) -> dict`
- 行为：插入一条今日事务记录，返回新建记录的完整 dict
- 副作用：写 `daily_activities`

### `get_daily_activities(date: str) -> list[dict]`
- 行为：返回指定日期的所有事务，按 `created_at ASC` 排序

### `delete_daily_activity(activity_id: str) -> None`
- 行为：删除指定事务记录
- 副作用：写 `daily_activities`

## 不要做

- 不要实现 update 函数（本期只支持增删）
- 不要修改 `calendar_todos` 或其他现有表

## 验收清单

- [ ] `python -c "from core.db_manager import create_daily_activity, get_daily_activities, delete_daily_activity; print('OK')"` 通过
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动后 `daily_activities` 表存在
- [ ] `docs/api/database.md` 表数改为 16，字段说明已追加
- [ ] `docs/api/core.md` 新函数契约已追加
- [ ] commit 符合规范（建议 `feat(db): daily_activities 表 + CRUD · 关联 #23`）
- [ ] worktree 分支提交，未 push main

## 架构师备注

- `daily_activities.category` 取值与 `TODO_CATEGORIES` 保持一致，但不做 FK 约束（分类是枚举值，不是表引用）
- `duration` 用整型分钟，0 表示未填，UI 层可按需显示"未记录"
