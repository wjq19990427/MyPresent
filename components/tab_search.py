"""搜索 Tab — 日期过滤 / 语义检索 / 智能问答。"""
from __future__ import annotations

import streamlit as st

from core.constants import COLS
from core.db_manager import (
    load_db,
    get_llm_providers, get_llm_models,
    add_llm_provider, remove_llm_provider, update_llm_provider,
    add_llm_model, remove_llm_model, update_llm_model,
)
from core.llm_client import call, call_with_config
from core.vector_db import _get_collection, _get_embedder
from components.cards import _render_card, _render_detail


# ─── 搜索结果渲染 ────────────────────────────────────────────────────────────

def _render_search_results(sessions_scores: list[tuple], state_key: str) -> None:
    all_db  = load_db()
    db_map  = {s["session_id"]: s for s in all_db}
    rows    = [(db_map[sid], sc) for sid, sc in sessions_scores if sid in db_map]

    if not rows:
        st.info("没有找到匹配的记录。")
        return

    for row_start in range(0, len(rows), COLS):
        cols = st.columns(COLS)
        for col, (session, score) in zip(cols, rows[row_start: row_start + COLS]):
            _render_card(col, session, state_key, score=score)

    sel = st.session_state.get(state_key)
    if sel:
        target = db_map.get(sel)
        if target:
            st.divider()
            _render_detail(target, "final", state_key=state_key)


# ─── 日期过滤 ─────────────────────────────────────────────────────────────────

def _render_date_filter() -> None:
    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("开始日期", value=None, key="filter_start")
    with c2:
        end = st.date_input("结束日期", value=None, key="filter_end")

    bc1, bc2 = st.columns([1, 5])
    with bc1:
        do_search = st.button("🔍 查询", type="primary", key="date_filter_btn")
    with bc2:
        if st.button("清除结果", key="date_filter_clear"):
            st.session_state["date_filter_exact"] = None
            st.session_state["date_filter_fuzzy"] = None
            st.session_state["search_selected"]   = None
            st.rerun()

    if do_search:
        if not start or not end:
            st.warning("请选择开始和结束日期")
        elif start > end:
            st.error("开始日期不能晚于结束日期")
        else:
            start_num = int(start.strftime("%Y%m%d"))
            end_num   = int(end.strftime("%Y%m%d"))
            try:
                col   = _get_collection()
                total = col.count()
                if total == 0:
                    st.info("向量库暂无数据，请先归档一些记录。")
                else:
                    exact = col.get(
                        where={"$and": [
                            {"has_exact_date":   {"$eq": True}},
                            {"content_time_num": {"$gte": start_num}},
                            {"content_time_num": {"$lte": end_num}},
                        ]},
                        include=["metadatas"],
                    )
                    fuzzy = col.get(
                        where={"has_exact_date": {"$eq": False}},
                        include=["metadatas"],
                    )
                    st.session_state["date_filter_exact"] = list(
                        zip(exact["ids"], exact["metadatas"])
                    )
                    st.session_state["date_filter_fuzzy"] = fuzzy["ids"]
                    st.session_state["date_filter_range"] = (
                        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
                    )
                    st.session_state["search_selected"] = None
            except Exception as e:
                st.error(f"查询失败：{e}")

    exact_data = st.session_state.get("date_filter_exact")
    if exact_data is None:
        return

    fuzzy_ids          = st.session_state.get("date_filter_fuzzy") or []
    start_str, end_str = st.session_state.get("date_filter_range", ("", ""))

    st.divider()
    st.markdown(f"### 📅 精确日期匹配（{len(exact_data)} 条）")
    if exact_data:
        sorted_data = sorted(
            exact_data,
            key=lambda x: x[1].get("content_time_num", 0),
            reverse=True,
        )
        _render_search_results([(sid, None) for sid, _ in sorted_data], "search_selected")
    else:
        st.caption(f"该日期范围（{start_str} 至 {end_str}）内无精确日期记录")

    if fuzzy_ids:
        st.divider()
        with st.expander(f"⚠️ 以下 {len(fuzzy_ids)} 条记录使用了模糊时间描述，无法按日期过滤"):
            _render_search_results([(sid, None) for sid in fuzzy_ids], "search_selected")

    # ── 阶段回忆录 ──────────────────────────────────────────────────────────
    model_id = st.session_state.get("llm_selected_model") or ""
    if exact_data and model_id:
        st.divider()
        st.markdown("### 📖 阶段回忆录")
        st.caption(f"基于上方 {len(exact_data)} 条精确匹配记录生成叙事文章")
        cache_key = f"_period_story_{start_str}_{end_str}"
        cached    = st.session_state.get(cache_key)
        if cached:
            st.markdown(cached)
            if st.button("🔄 重新生成", key="regen_period_story"):
                del st.session_state[cache_key]
                st.rerun()
        else:
            if st.button(
                "✨ 生成阶段回忆录", key="gen_period_story", type="primary"
            ):
                from core.db_manager import get_session
                from skills.story_skill import StorySkill
                sessions = [
                    s for sid, _ in sorted_data
                    if (s := get_session(sid)) is not None
                ]
                period_label = f"{start_str} 至 {end_str}"
                with st.spinner("生成中，请稍候…"):
                    result = StorySkill().run_period(
                        sessions, period_label, model_id=model_id
                    )
                if result.success:
                    st.session_state[cache_key] = result.data["story"]
                    st.rerun()
                else:
                    st.error(f"生成失败：{result.error}")


# ─── 语义检索 ─────────────────────────────────────────────────────────────────

def _render_semantic_search() -> None:
    query = st.text_input(
        "描述你想找的内容",
        placeholder="例如：和朋友一起看日落的那次旅行……",
        key="semantic_query",
    )
    top_k = st.slider("最多返回结果数", min_value=1, max_value=10, value=5,
                      key="semantic_topk")

    bc1, bc2 = st.columns([1, 5])
    with bc1:
        do_search = st.button("🔍 检索", type="primary", key="semantic_btn")
    with bc2:
        if st.button("清除结果", key="semantic_clear"):
            st.session_state["semantic_results"]    = None
            st.session_state["semantic_query_used"] = ""
            st.session_state["search_selected"]     = None
            st.rerun()

    if do_search:
        if not query.strip():
            st.warning("请输入检索内容")
        else:
            try:
                col   = _get_collection()
                total = col.count()
                if total == 0:
                    st.info("向量库暂无数据，请先归档一些记录。")
                else:
                    with st.spinner("检索中…"):
                        query_text = "为这个句子生成表示以用于检索相关文章：" + query.strip()
                        embedding  = _get_embedder().encode(
                            query_text, normalize_embeddings=True
                        ).tolist()
                        results = col.query(
                            query_embeddings=[embedding],
                            n_results=min(top_k, total),
                            include=["metadatas", "distances"],
                        )
                    pairs = [
                        (sid, 1 - dist)
                        for sid, dist in zip(results["ids"][0], results["distances"][0])
                    ]
                    st.session_state["semantic_results"]    = pairs
                    st.session_state["semantic_query_used"] = query.strip()
                    st.session_state["search_selected"]     = None
            except Exception as e:
                st.error(f"检索失败：{e}")

    pairs = st.session_state.get("semantic_results")
    if not pairs:
        return

    st.divider()
    q = st.session_state.get("semantic_query_used", "")
    st.markdown(f"### 🎯 语义检索结果（{len(pairs)} 条）")
    if q:
        st.caption(f"检索词：{q}")
    _render_search_results(pairs, "search_selected")


# ─── LLM 配置管理面板 ────────────────────────────────────────────────────────

_TEST_MESSAGE = "这是一个测试字段，来自于MyPresent项目，收到后请回复 你好MyPresent"


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
                    ep_name = st.text_input("名称", value=p["name"], key=f"ep_name_{p['id']}")
                    ep_url  = st.text_input("Base URL", value=p["base_url"], key=f"ep_url_{p['id']}")
                    ep_key  = st.text_input("API Key", value=p["api_key"],
                                            key=f"ep_key_{p['id']}", type="password")
                    ep_fw   = st.selectbox("框架", ["openai"], key=f"ep_fw_{p['id']}")
                    sa, sb = st.columns(2)
                    with sa:
                        if st.button("🧪 保存并测试", key=f"save_test_pvd_{p['id']}", type="primary"):
                            pvd_models = [m for m in models if m["provider_id"] == p["id"]]
                            if pvd_models:
                                _enter_draft(
                                    provider={
                                        "name": ep_name.strip(),
                                        "base_url": ep_url.strip().rstrip("/"),
                                        "api_key": ep_key.strip(),
                                        "framework": ep_fw,
                                        "_id": p["id"],
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
                    st.warning(
                        f"修改模型 `{m['display_name']}` 后需要**重新测试**，确认继续？"
                    )
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
                    em_name = st.text_input("模型 ID", value=m["name"], key=f"em_name_{m['id']}")
                    em_disp = st.text_input("显示名称", value=m["display_name"], key=f"em_disp_{m['id']}")
                    sa, sb = st.columns(2)
                    with sa:
                        if st.button("🧪 保存并测试", key=f"save_test_mdl_{m['id']}", type="primary"):
                            pvd = next((p for p in providers if p["id"] == m["provider_id"]), None)
                            if pvd:
                                _enter_draft(
                                    provider={**pvd, "_id": pvd["id"], "_readonly": True},
                                    model={
                                        "name":         em_name.strip(),
                                        "display_name": em_disp.strip() or em_name.strip(),
                                        "_id":          m["id"],
                                        "provider_id":  m["provider_id"],
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
            nm_disp = st.text_input("显示名称（留空同模型 ID）", key="nm_disp",
                                    placeholder="GPT-4o Mini")
            if st.button("添加模型", key="add_mdl_btn", type="primary"):
                if nm_name and nm_pvd:
                    try:
                        add_llm_model(nm_name, nm_pvd, nm_disp)
                        for k in ("nm_name", "nm_disp"):
                            st.session_state.pop(k, None)
                        st.success("模型已添加")
                        st.rerun()
                    except Exception as e:
                        st.error(f"添加失败：{e}")
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
            np_name  = st.text_input("名称", key="np_name", placeholder="老张AI")
            np_url   = st.text_input("Base URL", key="np_url",
                                     placeholder="https://api.laozhang.ai/v1")
            np_key   = st.text_input("API Key", key="np_key", type="password",
                                     placeholder="sk-...")
            np_fw    = st.selectbox("框架", ["openai"], key="np_fw",
                                    help="openai = 兼容 OpenAI SDK 的所有 API")
            st.markdown("**首个模型（用于测试）**")
            np_mname = st.text_input("模型 ID", key="np_mname", placeholder="gpt-4o-mini")
            np_mdisp = st.text_input("显示名称（留空同模型 ID）", key="np_mdisp",
                                     placeholder="GPT-4o Mini")
            if st.button("🧪 开始测试", key="start_test_btn", type="primary"):
                if np_name and np_url and np_key and np_mname:
                    _enter_draft(
                        provider={
                            "name":      np_name.strip(),
                            "base_url":  np_url.strip().rstrip("/"),
                            "api_key":   np_key.strip(),
                            "framework": np_fw,
                        },
                        model={
                            "name":         np_mname.strip(),
                            "display_name": np_mdisp.strip() or np_mname.strip(),
                        },
                    )
                    st.rerun()
                else:
                    st.warning("请填写所有必要字段（名称、Base URL、API Key、模型 ID）")


# ─── 智能问答 ─────────────────────────────────────────────────────────────────

def _render_qa() -> None:
    models = get_llm_models()

    with st.expander("⚙️ 模型与 API 配置", expanded=not models):
        _render_llm_settings()

    if not models:
        st.info("请先在上方「模型与 API 配置」中添加 Provider 和模型。")
        return

    model_ids   = [m["id"] for m in models]
    cur_model   = st.session_state.get("llm_selected_model")
    if cur_model not in model_ids:
        cur_model = model_ids[0]
        st.session_state["llm_selected_model"] = cur_model

    providers = get_llm_providers()
    pvd_name  = {p["id"]: p["name"] for p in providers}
    mdl_label = {
        m["id"]: f"{pvd_name.get(m['provider_id'], '?')}  ·  {m['display_name']}"
        for m in models
    }

    col_sel, col_clr = st.columns([4, 1])
    with col_sel:
        chosen = st.selectbox(
            "选择模型",
            options=model_ids,
            index=model_ids.index(cur_model),
            format_func=lambda mid: mdl_label.get(mid, mid),
            key="llm_model_select",
            label_visibility="collapsed",
        )
        if chosen != st.session_state.get("llm_selected_model"):
            st.session_state["llm_selected_model"] = chosen
            st.rerun()
    with col_clr:
        history: list[dict] = st.session_state.get("llm_chat_history", [])
        if st.button("🗑️ 清空", key="clear_chat_btn", disabled=not history):
            st.session_state["llm_chat_history"] = []
            st.rerun()

    history = st.session_state.get("llm_chat_history", [])
    with st.container(height=460, border=True):
        if not history:
            st.caption("💬 对话将显示在这里，请在下方输入问题。")
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("输入问题…")

    if user_input and user_input.strip():
        history = st.session_state.get("llm_chat_history", [])
        history.append({"role": "user", "content": user_input.strip()})
        st.session_state["llm_chat_history"] = history

        model_id = st.session_state.get("llm_selected_model")
        with st.spinner("思考中…"):
            try:
                reply = call(history, model_id)
                history.append({"role": "assistant", "content": str(reply)})
                st.session_state["llm_chat_history"] = history
                st.rerun()
            except Exception as e:
                history.pop()
                st.session_state["llm_chat_history"] = history
                st.error(f"调用失败：{e}")


# ─── Tab 入口 ─────────────────────────────────────────────────────────────────

def render_search_tab() -> None:
    mode = st.radio(
        "检索模式",
        ["📅 日期过滤", "🔍 语义检索", "💬 智能问答"],
        horizontal=True,
        key="search_mode",
    )

    prev = st.session_state.get("_search_mode_prev")
    if prev != mode:
        st.session_state["semantic_results"]  = None
        st.session_state["date_filter_exact"] = None
        st.session_state["date_filter_fuzzy"] = None
        st.session_state["search_selected"]   = None
        st.session_state["_search_mode_prev"] = mode

    st.divider()

    if mode == "📅 日期过滤":
        _render_date_filter()
    elif mode == "🔍 语义检索":
        _render_semantic_search()
    else:
        _render_qa()
