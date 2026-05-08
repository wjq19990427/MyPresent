"""LLM 运行看板：API 配置管理 + 模型选择 + 调用统计。"""
from __future__ import annotations

from collections import defaultdict

import streamlit as st

from core.db_manager import (
    get_llm_logs, get_llm_models, get_llm_providers,
    add_llm_provider, remove_llm_provider, update_llm_provider,
    add_llm_model, remove_llm_model, update_llm_model,
    get_operation_logs,
)
from core.llm_client import call_with_config

_TEST_MESSAGE = "这是一个测试字段，来自于MyPresent项目，收到后请回复 你好MyPresent"


# ─── 草稿状态辅助 ────────────────────────────────────────────────────────────────

def _clear_draft() -> None:
    for k in ("_draft_provider", "_draft_model", "_test_result"):
        st.session_state[k] = None
    st.session_state["_draft_test_passed"] = False


def _enter_draft(provider: dict, model: dict) -> None:
    st.session_state["_draft_provider"]    = provider
    st.session_state["_draft_model"]       = model
    st.session_state["_test_result"]       = None
    st.session_state["_draft_test_passed"] = False
    st.session_state["_editing_pvd"]       = None
    st.session_state["_editing_mdl"]       = None


# ─── LLM 配置管理面板 ────────────────────────────────────────────────────────────

def _render_llm_settings() -> None:
    providers   = get_llm_providers()
    models      = get_llm_models()
    pvd_map     = {p["id"]: p["name"] for p in providers}
    draft_pvd   = st.session_state.get("_draft_provider")
    draft_mdl   = st.session_state.get("_draft_model")
    test_result = st.session_state.get("_test_result")
    test_passed = st.session_state.get("_draft_test_passed", False)

    st.markdown("**🔌 API Provider**")
    if providers:
        for p in providers:
            if st.session_state.get("_confirm_edit_pvd") == p["id"]:
                with st.container(border=True):
                    st.warning(
                        f"修改 `{p['name']}` 的配置后需要**重新测试**（会消耗少量 token），确认继续？"
                    )
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("确认修改", key=f"confirm_edit_pvd_{p['id']}", type="primary"):
                            st.session_state["_confirm_edit_pvd"] = None
                            st.session_state["_editing_pvd"] = p["id"]
                            st.rerun()
                    with cc2:
                        if st.button("取消", key=f"cancel_confirm_pvd_{p['id']}"):
                            st.session_state["_confirm_edit_pvd"] = None
                            st.rerun()
            elif st.session_state.get("_editing_pvd") == p["id"]:
                with st.container(border=True):
                    ep_name = st.text_input("名称",     value=p["name"],     key=f"ep_name_{p['id']}")
                    ep_url  = st.text_input("Base URL", value=p["base_url"], key=f"ep_url_{p['id']}")
                    ep_key  = st.text_input("API Key",  value=p["api_key"],
                                            key=f"ep_key_{p['id']}", type="password")
                    ep_fw   = st.selectbox("框架", ["openai"], key=f"ep_fw_{p['id']}")
                    sa, sb = st.columns(2)
                    with sa:
                        if st.button("🧪 保存并测试", key=f"save_test_pvd_{p['id']}", type="primary"):
                            pvd_models = [m for m in models if m["provider_id"] == p["id"]]
                            if pvd_models:
                                _enter_draft(
                                    provider={
                                        "name": ep_name.strip(), "base_url": ep_url.strip().rstrip("/"),
                                        "api_key": ep_key.strip(), "framework": ep_fw, "_id": p["id"],
                                    },
                                    model={**pvd_models[0], "_readonly": True},
                                )
                                st.rerun()
                            else:
                                st.warning("该 Provider 下暂无模型，请先追加模型后再修改。")
                    with sb:
                        if st.button("取消", key=f"cancel_edit_pvd_{p['id']}"):
                            st.session_state["_editing_pvd"] = None
                            st.rerun()
            else:
                c1, c2, c3 = st.columns([5, 1, 1])
                with c1:
                    st.markdown(f"`{p['name']}`　`{p['base_url']}`　`{p['framework']}`")
                    st.caption(f"Key: {p['api_key'][:8]}…{p['api_key'][-4:]}")
                with c2:
                    if st.button("✏️", key=f"edit_pvd_{p['id']}", help="编辑"):
                        st.session_state["_confirm_edit_pvd"] = p["id"]
                        st.session_state["_confirm_edit_mdl"] = None
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"del_pvd_{p['id']}", help="删除"):
                        remove_llm_provider(p["id"])
                        st.rerun()
    else:
        st.caption("暂无已保存的 Provider。")

    st.divider()

    st.markdown("**🤖 已保存模型**")
    if models:
        for m in models:
            if st.session_state.get("_confirm_edit_mdl") == m["id"]:
                with st.container(border=True):
                    st.warning(f"修改模型 `{m['display_name']}` 后需要**重新测试**，确认继续？")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("确认修改", key=f"confirm_edit_mdl_{m['id']}", type="primary"):
                            st.session_state["_confirm_edit_mdl"] = None
                            st.session_state["_editing_mdl"] = m["id"]
                            st.rerun()
                    with cc2:
                        if st.button("取消", key=f"cancel_confirm_mdl_{m['id']}"):
                            st.session_state["_confirm_edit_mdl"] = None
                            st.rerun()
            elif st.session_state.get("_editing_mdl") == m["id"]:
                with st.container(border=True):
                    em_name = st.text_input("模型 ID",   value=m["name"],         key=f"em_name_{m['id']}")
                    em_disp = st.text_input("显示名称", value=m["display_name"],  key=f"em_disp_{m['id']}")
                    sa, sb = st.columns(2)
                    with sa:
                        if st.button("🧪 保存并测试", key=f"save_test_mdl_{m['id']}", type="primary"):
                            pvd = next((p for p in providers if p["id"] == m["provider_id"]), None)
                            if pvd:
                                _enter_draft(
                                    provider={**pvd, "_id": pvd["id"], "_readonly": True},
                                    model={
                                        "name": em_name.strip(),
                                        "display_name": em_disp.strip() or em_name.strip(),
                                        "_id": m["id"], "provider_id": m["provider_id"],
                                    },
                                )
                                st.rerun()
                            else:
                                st.error("找不到对应 Provider，请检查配置。")
                    with sb:
                        if st.button("取消", key=f"cancel_edit_mdl_{m['id']}"):
                            st.session_state["_editing_mdl"] = None
                            st.rerun()
            else:
                c1, c2, c3 = st.columns([5, 1, 1])
                with c1:
                    st.markdown(
                        f"`{m['display_name']}`　`{m['name']}`　"
                        f"via `{pvd_map.get(m['provider_id'], '?')}`"
                    )
                with c2:
                    if st.button("✏️", key=f"edit_mdl_{m['id']}", help="编辑"):
                        st.session_state["_confirm_edit_mdl"] = m["id"]
                        st.session_state["_confirm_edit_pvd"] = None
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"del_mdl_{m['id']}", help="删除"):
                        remove_llm_model(m["id"])
                        if st.session_state.get("llm_selected_model") == m["id"]:
                            st.session_state["llm_selected_model"] = None
                        st.rerun()
    else:
        st.caption("暂无已保存模型。")

    if providers and not draft_pvd:
        with st.expander("➕ 为已有 Provider 追加模型"):
            nm_pvd  = st.selectbox(
                "所属 Provider",
                options=[p["id"] for p in providers],
                format_func=lambda pid: pvd_map.get(pid, pid),
                key="nm_pvd",
            )
            nm_name = st.text_input("模型 ID", key="nm_name", placeholder="gpt-4o-mini")
            nm_disp = st.text_input("显示名称（留空同模型 ID）", key="nm_disp", placeholder="GPT-4o Mini")
            if st.button("🧪 开始测试", key="add_mdl_btn", type="primary"):
                if nm_name and nm_pvd:
                    pvd = next((p for p in providers if p["id"] == nm_pvd), None)
                    if pvd:
                        _enter_draft(
                            provider={**pvd, "_id": pvd["id"], "_readonly": True},
                            model={
                                "name":         nm_name.strip(),
                                "display_name": nm_disp.strip() or nm_name.strip(),
                                "provider_id":  nm_pvd,
                            },
                        )
                        st.rerun()
                else:
                    st.warning("请填写模型 ID 并选择 Provider")

    st.divider()

    if draft_pvd and draft_mdl:
        is_edit_pvd = "_id" in draft_pvd and not draft_pvd.get("_readonly")
        is_edit_mdl = "_id" in draft_mdl and not draft_mdl.get("_readonly")
        action      = "更新" if (is_edit_pvd or is_edit_mdl) else "保存"

        st.markdown(
            f"**🧪 {'修改' if (is_edit_pvd or is_edit_mdl) else '新增'}配置测试中**"
            f" — `{draft_pvd['name']}`  ·  `{draft_mdl['display_name']}`"
        )
        with st.container(border=True):
            st.caption("**📤 将发送以下固定测试字段：**")
            st.code(_TEST_MESSAGE, language=None)
            if test_result:
                st.markdown(f"**💬 API 回复：** {test_result['reply']}")
            else:
                if st.button("▶ 发送测试", key="draft_send_btn", type="primary"):
                    with st.spinner("调用中…"):
                        try:
                            reply = call_with_config(
                                [{"role": "user", "content": _TEST_MESSAGE}],
                                draft_mdl, draft_pvd,
                            )
                            st.session_state["_test_result"]       = {"reply": reply}
                            st.session_state["_draft_test_passed"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"调用失败：{e}")

        if test_passed:
            st.success(f"✅ API 调用成功！点击「确认{action}」使配置生效。")

        ca, cb, cc = st.columns(3)
        with ca:
            if st.button(f"✅ 确认{action}", key="draft_confirm_btn",
                         type="primary", disabled=not test_passed):
                new_pvd_id = None
                if is_edit_pvd:
                    update_llm_provider(
                        draft_pvd["_id"], name=draft_pvd["name"],
                        base_url=draft_pvd["base_url"], api_key=draft_pvd["api_key"],
                        framework=draft_pvd["framework"],
                    )
                elif not draft_pvd.get("_readonly"):
                    new_pvd_id = add_llm_provider(
                        draft_pvd["name"], draft_pvd["base_url"],
                        draft_pvd["api_key"], draft_pvd["framework"],
                    )
                if is_edit_mdl:
                    update_llm_model(
                        draft_mdl["_id"], name=draft_mdl["name"],
                        display_name=draft_mdl["display_name"],
                    )
                elif not draft_mdl.get("_readonly"):
                    pvd_id_for_model = (
                        new_pvd_id
                        or draft_mdl.get("provider_id")
                        or draft_pvd.get("_id")
                    )
                    add_llm_model(
                        draft_mdl["name"], pvd_id_for_model,
                        draft_mdl["display_name"],
                    )
                _clear_draft()
                st.success(f"配置已{action}！")
                st.rerun()
        with cb:
            if st.button("✏️ 修改配置", key="draft_edit_btn"):
                _clear_draft()
                st.rerun()
        with cc:
            if st.button("❌ 放弃", key="draft_cancel_btn"):
                _clear_draft()
                st.rerun()
    else:
        with st.expander("➕ 新增 Provider + 首个模型", expanded=not providers):
            st.markdown("**Provider 信息**")
            np_name  = st.text_input("名称",     key="np_name", placeholder="老张AI")
            np_url   = st.text_input("Base URL", key="np_url",
                                     placeholder="https://api.laozhang.ai/v1")
            np_key   = st.text_input("API Key",  key="np_key", type="password", placeholder="sk-...")
            np_fw    = st.selectbox("框架", ["openai"], key="np_fw",
                                    help="openai = 兼容 OpenAI SDK 的所有 API")
            st.markdown("**首个模型（用于测试）**")
            np_mname = st.text_input("模型 ID",              key="np_mname", placeholder="gpt-4o-mini")
            np_mdisp = st.text_input("显示名称（留空同模型 ID）", key="np_mdisp", placeholder="GPT-4o Mini")
            if st.button("🧪 开始测试", key="start_test_btn", type="primary"):
                if np_name and np_url and np_key and np_mname:
                    _enter_draft(
                        provider={
                            "name": np_name.strip(), "base_url": np_url.strip().rstrip("/"),
                            "api_key": np_key.strip(), "framework": np_fw,
                        },
                        model={
                            "name": np_mname.strip(),
                            "display_name": np_mdisp.strip() or np_mname.strip(),
                        },
                    )
                    st.rerun()
                else:
                    st.warning("请填写所有必要字段（名称、Base URL、API Key、模型 ID）")


# ─── 模型选择器（供各 Tab 共用） ────────────────────────────────────────────────────

def render_model_selector(widget_key: str = "llm_model_select_dash") -> str | None:
    """渲染模型选择下拉框，返回当前选中的 model_id。

    同步写入 st.session_state["llm_selected_model"]，全局生效。
    widget_key 用于区分同页面多处调用（搜索 Tab 和看板各用各自的 key）。
    """
    models = get_llm_models()
    if not models:
        st.info("尚未配置模型，请在上方「⚙️ API 配置管理」中添加 Provider 和模型。")
        return None

    model_ids = [m["id"] for m in models]
    cur_model = st.session_state.get("llm_selected_model")
    if cur_model not in model_ids:
        cur_model = model_ids[0]
        st.session_state["llm_selected_model"] = cur_model

    providers = get_llm_providers()
    pvd_name  = {p["id"]: p["name"] for p in providers}
    mdl_label = {
        m["id"]: f"{pvd_name.get(m['provider_id'], '?')}  ·  {m['display_name']}"
        for m in models
    }

    col_sel, col_tip = st.columns([3, 4])
    with col_sel:
        chosen = st.selectbox(
            "当前选用模型",
            options=model_ids,
            index=model_ids.index(cur_model),
            format_func=lambda mid: mdl_label.get(mid, mid),
            key=widget_key,
        )
        if chosen != st.session_state.get("llm_selected_model"):
            st.session_state["llm_selected_model"] = chosen
            st.rerun()
    with col_tip:
        st.caption("此模型全局生效，用于 AI 标签、AI 摘要、阶段回忆录、智能问答等所有功能。")

    return st.session_state.get("llm_selected_model")


def _render_operation_logs() -> None:
    st.divider()
    st.subheader("📋 数据操作记录")
    op_logs = get_operation_logs(limit=50)
    if op_logs:
        op_label = {
            "create": "➕ 新建",
            "update": "✏️ 更新",
            "archive": "📁 归档",
            "delete": "🗑️ 删除",
            "restore": "↩️ 恢复",
            "purge": "💥 永久删除",
        }
        for log in op_logs:
            op = op_label.get(log["operation"], log["operation"])
            st.caption(f"{log['operated_at']}　{op}　`{log['session_id'][:16]}…`")
    else:
        st.caption("暂无操作记录")


# ─── 看板主入口 ─────────────────────────────────────────────────────────────────────

def render_eval_dashboard() -> None:
    st.subheader("📊 LLM 运行看板")

    # ── 配置管理 ──────────────────────────────────────────────────────────────────
    models = get_llm_models()
    with st.expander("⚙️ API 配置管理", expanded=not models):
        _render_llm_settings()

    # ── 全局模型选择 ──────────────────────────────────────────────────────────────
    st.markdown("**🤖 当前选用模型**")
    render_model_selector(widget_key="llm_model_select_dash")

    st.divider()

    # ── 调用统计 ──────────────────────────────────────────────────────────────────
    logs = get_llm_logs(limit=500)
    if not logs:
        st.info("暂无调用记录。使用「AI 推荐标签」或「AI 摘要」功能后，数据将显示在这里。")
        _render_operation_logs()
        return

    models_map    = {m["id"]: m["display_name"] for m in get_llm_models()}
    providers_map = {p["id"]: p["name"]         for p in get_llm_providers()}

    total      = len(logs)
    successes  = sum(1 for r in logs if r["success"])
    success_rt = successes / total if total else 0
    latencies  = [r["latency_ms"] for r in logs if r.get("latency_ms") and r["success"]]
    avg_lat    = sum(latencies) / len(latencies) if latencies else 0
    max_lat    = max(latencies, default=0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总调用次数", total)
    c2.metric("成功率",      f"{success_rt:.1%}")
    c3.metric("平均延迟",    f"{avg_lat:.0f} ms")
    c4.metric("最大延迟",    f"{max_lat:.0f} ms")

    st.divider()

    # ── 按 Skill 统计 ─────────────────────────────────────────────────────────────
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
        alat = stats["latency_sum"] / stats["latency_count"] if stats["latency_count"] else 0
        skill_cols[0].write(skill_name)
        skill_cols[1].write(stats["total"])
        skill_cols[2].write(f"{sr:.1%}")
        skill_cols[3].write(f"{alat:.0f} ms")

    st.divider()

    # ── 最近调用日志 ──────────────────────────────────────────────────────────────
    st.markdown("**最近调用记录**")
    show_n = st.slider("显示条数", min_value=5, max_value=100, value=20, step=5,
                       key="eval_log_limit")
    for r in logs[:show_n]:
        status_icon = "✅" if r["success"] else "❌"
        mdl_name    = models_map.get(r.get("model_id", ""), r.get("model_id", "—") or "—")
        skill       = r.get("skill_name") or "qa"
        lat         = f"{r['latency_ms']} ms" if r.get("latency_ms") else "—"
        err         = r.get("error_message") or ""
        ts          = r.get("created_at", "")
        cols = st.columns([1, 2, 2, 1, 3])
        cols[0].write(status_icon)
        cols[1].write(mdl_name[:20])
        cols[2].write(skill)
        cols[3].write(lat)
        cols[4].write(ts)
        if err:
            st.caption(f"  ⚠️ {err[:100]}")

    _render_operation_logs()
