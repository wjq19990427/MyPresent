"""搜索 Tab — 日期过滤 / 语义检索 / 智能问答。"""
from __future__ import annotations

import streamlit as st

from ..constants import COLS
from ..db import load_db
from ..vector_db import _get_collection, _get_embedder
from ..llm import (
    get_llm_providers, get_llm_models,
    add_llm_provider, remove_llm_provider, update_llm_provider,
    add_llm_model, remove_llm_model, update_llm_model,
    call_llm,
)
from .components import _render_card, _render_detail


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
        sorted_data = sorted(exact_data,
                             key=lambda x: x[1].get("content_time_num", 0),
                             reverse=True)
        _render_search_results([(sid, None) for sid, _ in sorted_data], "search_selected")
    else:
        st.caption(f"该日期范围（{start_str} 至 {end_str}）内无精确日期记录")

    if fuzzy_ids:
        st.divider()
        with st.expander(f"⚠️ 以下 {len(fuzzy_ids)} 条记录使用了模糊时间描述，无法按日期过滤"):
            _render_search_results([(sid, None) for sid in fuzzy_ids], "search_selected")


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

def _render_llm_settings() -> None:
    """Provider + Model 增删改管理，放在 expander 内。"""
    providers = get_llm_providers()
    models    = get_llm_models()
    pvd_map   = {p["id"]: p["name"] for p in providers}

    # ── Provider 列表 ──────────────────────────────────────────────────────
    st.markdown("**🔌 API Provider**")
    if providers:
        for p in providers:
            editing = st.session_state.get("_editing_pvd") == p["id"]
            if editing:
                with st.container(border=True):
                    ep_name = st.text_input("名称", value=p["name"],
                                            key=f"ep_name_{p['id']}")
                    ep_url  = st.text_input("Base URL", value=p["base_url"],
                                            key=f"ep_url_{p['id']}")
                    ep_key  = st.text_input("API Key", value=p["api_key"],
                                            key=f"ep_key_{p['id']}", type="password")
                    ep_fw   = st.selectbox("框架", ["openai"], key=f"ep_fw_{p['id']}")
                    sa, sb, sc = st.columns(3)
                    with sa:
                        if st.button("💾 保存", key=f"save_pvd_{p['id']}", type="primary"):
                            update_llm_provider(p["id"], name=ep_name,
                                                base_url=ep_url, api_key=ep_key,
                                                framework=ep_fw)
                            st.session_state["_editing_pvd"] = None
                            st.rerun()
                    with sb:
                        if st.button("取消", key=f"cancel_pvd_{p['id']}"):
                            st.session_state["_editing_pvd"] = None
                            st.rerun()
                    with sc:
                        if st.button("🗑️ 删除", key=f"del_pvd_{p['id']}"):
                            remove_llm_provider(p["id"])
                            st.session_state["_editing_pvd"] = None
                            st.rerun()
            else:
                c1, c2, c3 = st.columns([5, 1, 1])
                with c1:
                    st.markdown(f"`{p['name']}`　`{p['base_url']}`　`{p['framework']}`")
                    st.caption(f"Key: {p['api_key'][:8]}…{p['api_key'][-4:]}")
                with c2:
                    if st.button("✏️", key=f"edit_pvd_{p['id']}", help="编辑"):
                        st.session_state["_editing_pvd"] = p["id"]
                        st.session_state["_editing_mdl"] = None
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"del_pvd2_{p['id']}", help="删除"):
                        remove_llm_provider(p["id"])
                        st.rerun()
    else:
        st.caption("暂无 Provider，请在下方添加。")

    with st.expander("➕ 添加 Provider", expanded=not providers):
        np_name = st.text_input("名称", key="np_name", placeholder="老张AI")
        np_url  = st.text_input("Base URL", key="np_url",
                                placeholder="https://api.laozhang.ai/v1")
        np_key  = st.text_input("API Key", key="np_key", type="password",
                                placeholder="sk-...")
        np_fw   = st.selectbox("框架", ["openai"], key="np_fw",
                               help="openai = 兼容 OpenAI SDK 的所有 API")
        if st.button("添加 Provider", key="add_pvd_btn", type="primary"):
            if np_name and np_url and np_key:
                try:
                    add_llm_provider(np_name, np_url, np_key, np_fw)
                    for k in ("np_name", "np_url", "np_key"):
                        st.session_state.pop(k, None)
                    st.success("Provider 已添加")
                    st.rerun()
                except Exception as e:
                    st.error(f"添加失败：{e}")
            else:
                st.warning("名称 / Base URL / API Key 均不能为空")

    st.divider()

    # ── Model 列表 ─────────────────────────────────────────────────────────
    st.markdown("**🤖 模型列表**")
    if models:
        for m in models:
            editing = st.session_state.get("_editing_mdl") == m["id"]
            if editing:
                with st.container(border=True):
                    em_name = st.text_input("模型 ID", value=m["name"],
                                            key=f"em_name_{m['id']}")
                    em_disp = st.text_input("显示名称", value=m["display_name"],
                                            key=f"em_disp_{m['id']}")
                    sa, sb, sc = st.columns(3)
                    with sa:
                        if st.button("💾 保存", key=f"save_mdl_{m['id']}", type="primary"):
                            update_llm_model(m["id"], name=em_name,
                                             display_name=em_disp or em_name)
                            st.session_state["_editing_mdl"] = None
                            st.rerun()
                    with sb:
                        if st.button("取消", key=f"cancel_mdl_{m['id']}"):
                            st.session_state["_editing_mdl"] = None
                            st.rerun()
                    with sc:
                        if st.button("🗑️ 删除", key=f"del_mdl_{m['id']}"):
                            remove_llm_model(m["id"])
                            if st.session_state.get("llm_selected_model") == m["id"]:
                                st.session_state["llm_selected_model"] = None
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
                        st.session_state["_editing_mdl"] = m["id"]
                        st.session_state["_editing_pvd"] = None
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"del_mdl2_{m['id']}", help="删除"):
                        remove_llm_model(m["id"])
                        if st.session_state.get("llm_selected_model") == m["id"]:
                            st.session_state["llm_selected_model"] = None
                        st.rerun()
    else:
        st.caption("暂无模型，请在下方添加。")

    if providers:
        with st.expander("➕ 添加模型", expanded=not models):
            nm_pvd  = st.selectbox(
                "所属 Provider",
                options=[p["id"] for p in providers],
                format_func=lambda pid: pvd_map.get(pid, pid),
                key="nm_pvd",
            )
            nm_name = st.text_input("模型 ID", key="nm_name",
                                    placeholder="gpt-4o-mini")
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
    else:
        st.info("请先添加 Provider 再添加模型。")


# ─── 智能问答 ─────────────────────────────────────────────────────────────────

def _render_qa() -> None:
    models = get_llm_models()

    # ── 配置管理面板（有模型时默认折叠） ────────────────────────────────────
    with st.expander("⚙️ 模型与 API 配置", expanded=not models):
        _render_llm_settings()

    if not models:
        st.info("请先在上方「模型与 API 配置」中添加 Provider 和模型。")
        return

    # ── 模型选择 + 清空按钮（同行） ─────────────────────────────────────────
    model_ids = [m["id"] for m in models]
    cur_model = st.session_state.get("llm_selected_model")
    if cur_model not in model_ids:
        cur_model = model_ids[0]
        st.session_state["llm_selected_model"] = cur_model

    providers   = get_llm_providers()
    pvd_name    = {p["id"]: p["name"] for p in providers}
    mdl_label   = {
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

    # ── 对话气泡（固定高度滚动区，消息始终可见） ─────────────────────────────
    history = st.session_state.get("llm_chat_history", [])
    with st.container(height=460, border=True):
        if not history:
            st.caption("💬 对话将显示在这里，请在下方输入问题。")
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── 输入框（Streamlit 自动固定在页面底部） ───────────────────────────────
    user_input = st.chat_input("输入问题…")

    if user_input and user_input.strip():
        history = st.session_state.get("llm_chat_history", [])
        history.append({"role": "user", "content": user_input.strip()})
        st.session_state["llm_chat_history"] = history

        model_id = st.session_state.get("llm_selected_model")
        with st.spinner("思考中…"):
            try:
                reply = call_llm(history, model_id)
                history.append({"role": "assistant", "content": reply})
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
