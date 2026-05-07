# Task #3 — 修复批量导入时 session ID 秒级碰撞

## 目标

批量导入多个文件时，`save_session_pending` 在同一秒内被循环调用多次，导致
`sid = datetime.now().strftime("%Y%m%d_%H%M%S")` 生成相同 ID，触发
`sqlite3.IntegrityError: UNIQUE constraint failed: sessions.id`。

将 `sid` 精度扩展至微秒（`%f`），消除碰撞。

## 必读契约

- `docs/api/core.md` # `file_io.py` 节（`save_session_pending` / `save_session_final` 签名与副作用）

## 改动范围

- **修改**：`core/file_io.py`（仅两处 `strftime` 格式字符串）
- **不许碰**：`core/db_manager.py` / `components/tab_upload.py` / 其他文件

## 实现要点

`core/file_io.py` 中有且仅有两处生成 `sid` 的代码，格式完全相同，均需修改：

**第 113 行**（`save_session_pending`）：
```python
# 原
sid = datetime.now().strftime("%Y%m%d_%H%M%S")
# 改为
sid = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
```

**第 125 行**（`save_session_final`）：
```python
# 原
sid = datetime.now().strftime("%Y%m%d_%H%M%S")
# 改为
sid = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
```

`%f` 是 Python `strftime` 标准指令，输出 6 位微秒，无需额外 import。

## 不要做

- 不要改函数签名或其他任何逻辑
- 不要引入 `uuid` 或 `random`——`%f` 微秒精度已足够
- 不要改 `import_folder_to_pending` 的循环结构
- 不要修改现有数据库中的历史 session ID

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 手工复现修复：记录舱 → 文件夹批量导入 → 选择 3 个以上文件 → 独立模式导入 → 无 IntegrityError，灵感墙出现对应条目
- [ ] commit 信息符合 AGENTS.md 规范（建议 `fix(file_io): session ID 扩展至微秒精度，消除批量导入碰撞`）
- [ ] 在 git worktree 分支提交，未 push main

## 架构师备注

- 改动极小（2 行），风险极低
- `%f` 输出示例：`20260508_025417_123456`，仍保持可读性，文件名前缀不变
- 历史数据无影响：旧 session ID 格式（无 `_f` 部分）与新格式共存于数据库，无冲突
