# Task #16 — DB 层：annual_goals + calendar_todos 表 + CRUD 函数

## 目标

为「规划控制台」模块新增两张表及完整 CRUD，建立年度目标与日历待办的底层数据支撑。此任务是 task-17 / task-18 的前置依赖，本任务**不涉及任何 UI**。

## 必读契约

- `docs/api/database.md`（现有 schema 约定、CASCADE 规则、`CREATE TABLE IF NOT EXISTS` 模式）
- `docs/api/core.md` # `db_manager.py` 节（`_conn()` 上下文管理器、`init_db()` 结构、ID 生成约定）

## 改动范围

- **修改**：`core/db_manager.py`（`_SCHEMA` 追加 + 新增 CRUD 函数）
- **更新**：`docs/api/database.md`（表数改为 14，追加两张表说明）
- **更新**：`docs/api/core.md`（追加所有新函数的 L2 契约节）
- **不许碰**：其他任何文件

## 实现要点

### 1. 在 `_SCHEMA` 末尾追加两张表

```sql
CREATE TABLE IF NOT EXISTS annual_goals (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    category    TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT 'Medium',
    deadline    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT '未开始',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS calendar_todos (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    category        TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'Medium',
    target_date     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT '待办',
    recurrence      TEXT NOT NULL DEFAULT '仅一次',
    linked_goal_id  TEXT REFERENCES annual_goals(id) ON DELETE SET NULL,
    reflection      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
);
```

**注意**：`calendar_todos.linked_goal_id` 用 `ON DELETE SET NULL`（目标删除后待办保留，关联置空）。

### 2. ID 生成

沿用项目约定：`datetime.now().strftime("%Y%m%d_%H%M%S_%f")`

### 3. annual_goals CRUD（文件末尾追加）

```python
# ── 枚举常量（供 UI 层引用，不要在 UI 层硬编码）──────────────────────────────
GOAL_CATEGORIES = ["身心健康", "亲密关系", "事业发展", "个人成长", "自定义"]
GOAL_STATUSES   = ["未开始", "进行中", "已完成", "已搁置"]
GOAL_PRIORITIES = ["高", "中", "低"]

def create_annual_goal(
    content: str, category: str, priority: str, deadline: str,
    status: str = "未开始",
) -> dict:
    gid = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO annual_goals(id,content,category,priority,deadline,status)"
            " VALUES(?,?,?,?,?,?)",
            (gid, content, category, priority, deadline, status),
        )
    return get_annual_goal(gid)

def get_annual_goals(status_filter: list[str] | None = None) -> list[dict]:
    with _conn() as conn:
        if status_filter:
            placeholders = ",".join("?" * len(status_filter))
            rows = conn.execute(
                f"SELECT * FROM annual_goals WHERE status IN ({placeholders})"
                " ORDER BY deadline ASC",
                status_filter,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM annual_goals ORDER BY deadline ASC"
            ).fetchall()
    return [dict(r) for r in rows]

def get_annual_goal(goal_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM annual_goals WHERE id=?", (goal_id,)
        ).fetchone()
    return dict(row) if row else None

def update_annual_goal(goal_id: str, **fields) -> None:
    allowed = {"content", "category", "priority", "deadline", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE annual_goals SET {set_clause} WHERE id=?",
            (*updates.values(), goal_id),
        )

def delete_annual_goal(goal_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM annual_goals WHERE id=?", (goal_id,))
```

### 4. calendar_todos CRUD

```python
# ── 枚举常量 ─────────────────────────────────────────────────────────────────
TODO_CATEGORIES  = ["工作", "学习", "生活", "社交", "娱乐"]
TODO_RECURRENCES = ["仅一次", "每天", "每周", "每月", "每年"]
TODO_PRIORITIES  = ["高", "中", "低"]

def create_calendar_todo(
    content: str, category: str, priority: str, target_date: str,
    recurrence: str = "仅一次",
    linked_goal_id: str | None = None,
) -> dict:
    tid = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO calendar_todos"
            "(id,content,category,priority,target_date,recurrence,linked_goal_id)"
            " VALUES(?,?,?,?,?,?,?)",
            (tid, content, category, priority, target_date, recurrence, linked_goal_id),
        )
    return get_calendar_todo(tid)

def get_calendar_todos(
    year: int | None = None,
    month: int | None = None,
    status_filter: list[str] | None = None,
) -> list[dict]:
    """返回指定年月的待办（含跨月重复任务）。year/month 均为 None 时返回全量。"""
    with _conn() as conn:
        if year and month:
            month_prefix = f"{year:04d}-{month:02d}"
            rows = conn.execute(
                "SELECT * FROM calendar_todos"
                " WHERE target_date LIKE ? OR recurrence != '仅一次'"
                " ORDER BY target_date ASC",
                (f"{month_prefix}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM calendar_todos ORDER BY target_date ASC"
            ).fetchall()
    todos = [dict(r) for r in rows]
    if status_filter:
        todos = [t for t in todos if t["status"] in status_filter]
    return todos

def get_calendar_todo(todo_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM calendar_todos WHERE id=?", (todo_id,)
        ).fetchone()
    return dict(row) if row else None

def complete_todo(todo_id: str, reflection: str = "") -> None:
    """标记待办为已完成并写入复盘心得。"""
    with _conn() as conn:
        conn.execute(
            "UPDATE calendar_todos SET status='已完成', reflection=? WHERE id=?",
            (reflection, todo_id),
        )

def update_calendar_todo(todo_id: str, **fields) -> None:
    allowed = {"content", "category", "priority", "target_date",
               "status", "recurrence", "linked_goal_id", "reflection"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE calendar_todos SET {set_clause} WHERE id=?",
            (*updates.values(), todo_id),
        )

def delete_calendar_todo(todo_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM calendar_todos WHERE id=?", (todo_id,))
```

## 不要做

- 不要实现重复任务的自动生成逻辑（recurrence 本期只存储，不处理）
- 不要修改现有表结构
- 枚举常量（`GOAL_CATEGORIES` 等）必须定义在 `db_manager.py` 末尾，供 UI 层 import，不要在 UI 层硬编码字符串

## 验收清单

- [ ] `python -c "from core.db_manager import create_annual_goal, create_calendar_todo; print('OK')"` 通过
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动后数据库自动创建两张新表（可用 sqlite3 CLI 验证：`.tables`）
- [ ] `docs/api/database.md` 表数改为 14，追加 `annual_goals` / `calendar_todos` 完整字段说明
- [ ] `docs/api/core.md` 追加所有 CRUD 函数的 L2 契约节（含枚举常量说明）
- [ ] commit 符合规范（建议 `feat(db): annual_goals + calendar_todos 表 + CRUD · 关联 #16`）
- [ ] 在 worktree 分支提交，未 push main

## 架构师备注

- 两张新表用 `CREATE TABLE IF NOT EXISTS` 直接追加到 `_SCHEMA`，现有数据库下次启动时自动创建，**无需 ALTER TABLE**
- `linked_goal_id ON DELETE SET NULL`：目标删时待办保留、关联置空，保护历史数据
- 枚举常量放在 db_manager 而非 constants.py，因为它们与表结构强绑定，不属于全局 UI 常量
