"""LLM 调用评估看板。"""
from __future__ import annotations

import streamlit as st

from core.db_manager import get_llm_logs, get_llm_models, get_llm_providers


def render_eval_dashboard() -> None:
    st.subheader("📊 LLM 调用看板")

    logs = get_llm_logs(limit=500)
    if not logs:
        st.info("暂无调用记录。使用「AI 推荐标签」或「AI 摘要」功能后，数据将显示在这里。")
        return

    models    = {m["id"]: m["display_name"] for m in get_llm_models()}
    providers = {p["id"]: p["name"]         for p in get_llm_providers()}

    # ── 汇总指标 ──────────────────────────────────────────────────────────────
    total      = len(logs)
    successes  = sum(1 for r in logs if r["success"])
    failures   = total - successes
    success_rt = successes / total if total else 0

    latencies  = [r["latency_ms"] for r in logs if r["latency_ms"] and r["success"]]
    avg_lat    = sum(latencies) / len(latencies) if latencies else 0
    max_lat    = max(latencies, default=0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总调用次数", total)
    c2.metric("成功率",      f"{success_rt:.1%}")
    c3.metric("平均延迟",    f"{avg_lat:.0f} ms")
    c4.metric("最大延迟",    f"{max_lat:.0f} ms")

    st.divider()

    # ── 按 Skill 统计 ─────────────────────────────────────────────────────────
    from collections import defaultdict
    by_skill: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "success": 0, "latency_sum": 0, "latency_count": 0}
    )
    for r in logs:
        key = r.get("skill_name") or "qa"
        by_skill[key]["total"]   += 1
        by_skill[key]["success"] += int(bool(r["success"]))
        if r.get("latency_ms") and r["success"]:
            by_skill[key]["latency_sum"]   += r["latency_ms"]
            by_skill[key]["latency_count"] += 1

    st.markdown("**按 Skill 分组**")
    skill_cols = st.columns([2, 1, 1, 1])
    skill_cols[0].markdown("**Skill**")
    skill_cols[1].markdown("**调用次数**")
    skill_cols[2].markdown("**成功率**")
    skill_cols[3].markdown("**均延迟**")
    for skill_name, stats in sorted(by_skill.items()):
        sr   = stats["success"] / stats["total"] if stats["total"] else 0
        alat = (
            stats["latency_sum"] / stats["latency_count"]
            if stats["latency_count"] else 0
        )
        skill_cols[0].write(skill_name)
        skill_cols[1].write(stats["total"])
        skill_cols[2].write(f"{sr:.1%}")
        skill_cols[3].write(f"{alat:.0f} ms")

    st.divider()

    # ── 最近调用日志 ──────────────────────────────────────────────────────────
    st.markdown("**最近调用记录**")
    show_n = st.slider("显示条数", min_value=5, max_value=100, value=20, step=5,
                       key="eval_log_limit")
    recent = logs[:show_n]
    for r in recent:
        status_icon = "✅" if r["success"] else "❌"
        mdl_name    = models.get(r.get("model_id", ""), r.get("model_id", "—") or "—")
        skill       = r.get("skill_name") or "qa"
        lat         = f"{r['latency_ms']} ms" if r.get("latency_ms") else "—"
        err         = r.get("error_message") or ""
        ts          = r.get("created_at", "")

        with st.container():
            cols = st.columns([1, 2, 2, 1, 3])
            cols[0].write(status_icon)
            cols[1].write(mdl_name[:20])
            cols[2].write(skill)
            cols[3].write(lat)
            cols[4].write(ts)
            if err:
                st.caption(f"  ⚠️ {err[:100]}")
