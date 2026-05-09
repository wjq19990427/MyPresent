# Task #7 — DB 层：软删除 + 操作日志 schema + CRUD 函数

## 目标

为「删除→回收站→恢复/永久删除」功能打地基：
1. 为 `sessions` 表新增两列（`deleted_at`、`pre_delete_status`）
2. 新增 `operation_logs` 表记录增删改操作
3. 在 `core/db_manager.py` 新增 6 个函数
4. 修改 `load_db()` 默认排除已删除记录

此任务不涉及任何 UI，是 task-8 和 task-9 的前置依赖。

## 必读契约

- `docs/api/core.md` # `db_manager.py` 节（现有函数签名、`_conn()` 模式、`_row_to_dict`）
- `docs/api/database.md`（现有 11 张表的 schema，了解 CASCADE 规则）

## 改动范围

- **修改**：`core/db_manager.py`
- **更新**：`docs/api/core.md`（新函数节）+ `docs/api/database.md`（新表 + 新列）
- **不许碰**：其他任何文件

## 实现要点

### 1. 在 `_SCHEMA` 末尾追加新表

```sql
CREATE TABLE IF NOT EXISTS operation_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL,
    operation    TEXT    NOT NULL,
    operated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
);
```

**注意**：`operation_logs.session_id` **不加 FK**（与 `llm_logs` 同理——记录保留，即使 session 被永久删除）。

`operation` 值枚举：`'create'` / `'update'` / `'archive'` / `'delete'` / `'restore'` / `'purge'`

### 2. `init_db()` 内追加迁移逻辑

在 `conn.executescript(_SCHEMA)` 后面加：

```python
# 迁移：为已有 sessions 表补列
_cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
if "deleted_at" not in _cols:
    conn.execute("ALTER TABLE sessions ADD COLUMN deleted_at TEXT")
if "pre_delete_status" not in _cols:
    conn.execute("ALTER TABLE sessions ADD COLUMN pre_delete_status TEXT")
conn.commit()
```

### 3. 修改 `load_db()`

```python
def load_db() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE status != 'deleted' ORDER BY upload_time DESC"
        ).fetchall()
        return [_row_to_dict(r, _load_aux(conn, r["id"])) for r in rows]
```

### 4. 新增 6 个函数（按此顺序，加在文件末尾）

```python
def log_operation(session_id: str, operation: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO operation_logs(session_id, operation) VALUES (?,?)",
            (session_id, operation),
        )


def get_operation_logs(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM operation_logs ORDER BY operated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def soft_delete_session(session_id: str) -> None:
    """软删除：标记 status='deleted'，保留文件，写入 deleted_at。"""
    session = get_session(session_id)
    if not session:
        return
    from .vector_db import remove_session as vdb_remove
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET status='deleted', pre_delete_status=?, deleted_at=? WHERE id=?",
            (session["status"], now, session_id),
        )
    try:
        vdb_remove(session_id)
    except Exception:
        pass
    log_operation(session_id, "delete")


def restore_session(session_id: str) -> None:
    """从回收站恢复到删除前的 status；final 记录重新入向量库。"""
    with _conn() as conn:
        row = conn.execute(
            "SELECT pre_delete_status FROM sessions WHERE id=? AND status='deleted'",
            (session_id,),
        ).fetchone()
        if not row:
            return
        prev = row["pre_delete_status"] or "pending"
        conn.execute(
            "UPDATE sessions SET status=?, deleted_at=NULL, pre_delete_status=NULL WHERE id=?",
            (prev, session_id),
        )
    if prev == "final":
        session = get_session(session_id)
        if session:
            from .vector_db import embed_session
            try:
                embed_session(session)
            except Exception:
                pass
    log_operation(session_id, "restore")


def get_deleted_sessions() -> list[dict]:
    """返回所有软删除记录（含 deleted_at）。"""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE status='deleted' ORDER BY deleted_at DESC"
        ).fetchall()
        return [_row_to_dict(r, _load_aux(conn, r["id"])) for r in rows]


def purge_expired_deleted(days: int = 30) -> int:
    """永久删除超过 days 天的软删除记录（含磁盘文件）。返回删除数量。"""
    from .constants import PENDING_DIR, FINAL_DIR
    with _conn() as conn:
        rows = conn.execute(
            f"""SELECT id FROM sessions
                WHERE status='deleted'
                AND deleted_at <= datetime('now', 'localtime', '-{days} days')"""
        ).fetchall()
        ids = [r["id"] for r in rows]
    for sid in ids:
        session = get_session(sid)
        if session:
            for f in session.get("files", []):
                path = Path(f.get("path", ""))
                if path.exists():
                    path.unlink(missing_ok=True)
        log_operation(sid, "purge")
        with _conn() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    return len(ids)
```

### 5. `vector_db.py` 中是否有 `remove_session`？

若 `vector_db.remove_session` 不存在，`soft_delete_session` 内的 `try/except` 已做容错，不会报错。task-7 **不需要**去 `vector_db.py` 里新增函数——容错即可，向量清理是 best-effort。

## 不要做

- 不要硬删除任何现有数据
- 不要在 `purge_expired_deleted` 中删除 `operation_logs` 记录（保留审计历史）
- 不要给 `operation_logs` 加 FK（与 `llm_logs` 设计一致）
- 不要修改 `get_session`——它应该仍能查到 deleted 状态的记录（回收站需要）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错，现有数据无丢失
- [ ] `python -c "from core.db_manager import soft_delete_session, restore_session, get_deleted_sessions, purge_expired_deleted, log_operation, get_operation_logs; print('OK')"` 通过
- [ ] `load_db()` 不返回 status='deleted' 的记录（可用 sqlite3 CLI 验证）
- [ ] `docs/api/core.md` 的 `db_manager.py` 节已追加 6 个新函数说明
- [ ] `docs/api/database.md` 已追加 `operation_logs` 表说明和 sessions 新列说明
- [ ] commit 符合规范（建议 `feat(db): 软删除 + operation_logs + 6 个 CRUD 函数 · 关联 #7`）
- [ ] 在 worktree 分支提交，未 push main

## 架构师备注

- `pre_delete_status` 必须在软删前记录，以便 restore 能回到正确状态（pending vs final）
- `purge_expired_deleted` 使用 SQLite 的 `datetime('now', 'localtime', '-30 days')` 做时间比较，不引入 Python datetime 计算
- `load_db()` 加过滤是本任务最关键的改动——若遗漏，灵感墙/已归档/搜索三个 Tab 都会显示已删除记录
