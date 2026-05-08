# Task #9 — UI：回收站 Tab + 操作记录展示

## 目标

1. 新建「🗑️ 回收站」Tab，展示软删除的记录，支持恢复和永久删除，并在 Tab 加载时自动清理超期记录
2. 在「📊 运行看板」Tab 末尾追加「数据操作记录」section，展示最近 50 条操作日志

## 依赖

**必须在 task-7 和 task-8 均合并后执行。**

## 必读契约

- `docs/api/components.md` # `eval_dashboard.py` 节（`render_eval_dashboard` 结构，现有三段布局）
- `docs/api/core.md` # `db_manager.py` 节（task-7 新增的 `get_deleted_sessions` / `restore_session` / `purge_expired_deleted` / `get_operation_logs`）

## 改动范围

- **新建**：`components/tab_recycle.py`
- **修改**：`app.py`（新增第 6 个 Tab）
- **修改**：`components/eval_dashboard.py`（追加操作记录 section）
- **更新**：`docs/api/components.md`（追加 `tab_recycle.py` 节）

## 实现要点

### 1. `components/tab_recycle.py`

```python
"""回收站 Tab — 软删除记录的查看 / 恢复 / 永久删除。"""
from __future__ import annotations
from datetime import datetime, timedelta
import streamlit as st
from core.db_manager import get_deleted_sessions, restore_session, purge_expired_deleted

_KEEP_DAYS = 30


def _days_remaining(deleted_at: str) -> int:
    try:
        dt = datetime.strptime(deleted_at, "%Y-%m-%d %H:%M:%S")
        remaining = (_KEEP_DAYS - (datetime.now() - dt).days)
        return max(0, remaining)
    except Exception:
        return _KEEP_DAYS


def render_recycle_tab() -> None:
    # 每次加载自动清理超期记录
    purged = purge_expired_deleted(_KEEP_DAYS)
    if purged:
        st.toast(f"已自动清理 {purged} 条超过 {_KEEP_DAYS} 天的记录")

    sessions = get_deleted_sessions()
    st.markdown(f"### 🗑️ 回收站（{len(sessions)} 条）")
    st.caption(f"删除后保留 **{_KEEP_DAYS} 天**，到期自动永久删除。")

    if not sessions:
        st.info("回收站为空")
        return

    for s in sessions:
        sid          = s["session_id"]
        safe_sid     = "".join(c if c.isalnum() else "_" for c in sid)
        deleted_at   = s.get("deleted_at", "")
        days_left    = _days_remaining(deleted_at)
        desc         = (s.get("description") or "（无描述）")[:60]
        prev_status  = s.get("pre_delete_status", "?")
        label        = "📦 待处理" if prev_status == "pending" else "✅ 已归档"

        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                st.markdown(f"**{desc}**")
                st.caption(
                    f"{label}　·　删除于 {deleted_at}　·　还剩 **{days_left}** 天到期"
                )
            with c2:
                if st.button("↩️ 恢复", key=f"restore_{safe_sid}"):
                    restore_session(sid)
                    st.rerun()
            with c3:
                if st.button("🗑️ 永久删除", key=f"perm_del_{safe_sid}", type="secondary"):
                    st.session_state[f"_confirm_perm_del_{safe_sid}"] = True
                    st.rerun()

        # 永久删除二次确认（此处需要确认，因为不可恢复）
        if st.session_state.get(f"_confirm_perm_del_{safe_sid}"):
            with st.container(border=True):
                st.warning("⚠️ 永久删除后**无法恢复**，确认吗？")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("确认永久删除", key=f"perm_confirm_{safe_sid}", type="primary"):
                        from core.db_manager import log_operation
                        from pathlib import Path
                        s_full = get_deleted_sessions()  # re-fetch for files
                        target = next((x for x in s_full if x["session_id"] == sid), None)
                        if target:
                            for f in target.get("files", []):
                                p = Path(f.get("path", ""))
                                if p.exists():
                                    p.unlink(missing_ok=True)
                        from core.db_manager import _conn as _db_conn  # noqa: F401
                        with __import__('core.db_manager', fromlist=['_conn'])._conn() as conn:
                            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
                        log_operation(sid, "purge")
                        st.session_state.pop(f"_confirm_perm_del_{safe_sid}", None)
                        st.rerun()
                with cc2:
                    if st.button("取消", key=f"perm_cancel_{safe_sid}"):
                        st.session_state.pop(f"_confirm_perm_del_{safe_sid}", None)
                        st.rerun()
```

**注意**：永久删除使用二次确认，因为不可恢复（与软删除不同）。

### 2. `app.py` 新增第 6 个 Tab

```python
from components.tab_recycle import render_recycle_tab

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗂️ 记录舱（上传）",
    "🖼️ 灵感墙（待处理）",
    "📁 已归档",
    "🔍 搜索",
    "📊 运行看板",
    "🗑️ 回收站",
])
# ... 前 5 个 with 块不变 ...
with tab6:
    render_recycle_tab()
```

### 3. `eval_dashboard.py` 追加操作记录 section

在 `render_eval_dashboard()` 末尾追加：

```python
st.divider()
st.subheader("📋 数据操作记录")
from core.db_manager import get_operation_logs
op_logs = get_operation_logs(limit=50)
if op_logs:
    op_label = {
        "create": "➕ 新建", "update": "✏️ 更新", "archive": "📁 归档",
        "delete": "🗑️ 删除", "restore": "↩️ 恢复", "purge": "💥 永久删除",
    }
    for log in op_logs:
        op = op_label.get(log["operation"], log["operation"])
        st.caption(f"{log['operated_at']}　{op}　`{log['session_id'][:16]}…`")
else:
    st.caption("暂无操作记录")
```

## 不要做

- `tab_recycle.py` 中不要实现翻页（条目超多时 Streamlit scroll 已够用）
- 永久删除按钮**必须**加二次确认（唯一例外于项目「软删除不加确认」原则，因为不可恢复）
- 不要在 `purge_expired_deleted` 以外的地方写文件删除逻辑（职责在 core 层）——`render_recycle_tab` 内的永久删除是补充路径（用户主动触发），须同样处理文件删除

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动，顶部出现第 6 个「🗑️ 回收站」Tab
- [ ] 从灵感墙删除一条记录 → 切换到回收站 → 该记录出现，显示剩余天数
- [ ] 点「↩️ 恢复」→ 记录重回灵感墙/已归档，回收站中消失
- [ ] 点「🗑️ 永久删除」→ 弹出二次确认 → 确认后记录从回收站消失，磁盘文件删除
- [ ] 运行看板 Tab 末尾显示操作记录列表
- [ ] `docs/api/components.md` 已追加 `tab_recycle.py` 节
- [ ] commit 符合规范（建议 `feat(recycle): 回收站 Tab + 操作记录展示 · 关联 #9`）
- [ ] 在 worktree 分支提交，未 push main
