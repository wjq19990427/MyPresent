"""回收站 Tab — 软删除记录的查看 / 恢复 / 永久删除。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from core.db_manager import (
    get_deleted_sessions,
    restore_session,
    purge_expired_deleted,
    log_operation,
)

_KEEP_DAYS = 30


def _days_remaining(deleted_at: str) -> int:
    try:
        dt = datetime.strptime(deleted_at, "%Y-%m-%d %H:%M:%S")
        remaining = _KEEP_DAYS - (datetime.now() - dt).days
        return max(0, remaining)
    except Exception:
        return _KEEP_DAYS


def _purge_now(session_id: str) -> None:
    s_full = get_deleted_sessions()
    target = next((x for x in s_full if x["session_id"] == session_id), None)
    if target:
        for f in target.get("files", []):
            p = Path(f.get("path", ""))
            if p.exists():
                p.unlink(missing_ok=True)

    with __import__("core.db_manager", fromlist=["_conn"])._conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    log_operation(session_id, "purge")


def render_recycle_tab() -> None:
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
        sid         = s["session_id"]
        safe_sid    = "".join(c if c.isalnum() else "_" for c in sid)
        deleted_at  = s.get("deleted_at", "")
        days_left   = _days_remaining(deleted_at)
        desc        = (s.get("description") or "（无描述）")[:60]
        prev_status = s.get("pre_delete_status", "?")
        label       = "📦 待处理" if prev_status == "pending" else "✅ 已归档"

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

        if st.session_state.get(f"_confirm_perm_del_{safe_sid}"):
            with st.container(border=True):
                st.warning("⚠️ 永久删除后**无法恢复**，确认吗？")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("确认永久删除", key=f"perm_confirm_{safe_sid}", type="primary"):
                        _purge_now(sid)
                        st.session_state.pop(f"_confirm_perm_del_{safe_sid}", None)
                        st.rerun()
                with cc2:
                    if st.button("取消", key=f"perm_cancel_{safe_sid}"):
                        st.session_state.pop(f"_confirm_perm_del_{safe_sid}", None)
                        st.rerun()
