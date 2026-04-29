"""搜索 Tab — 日期过滤（Phase 2.2）+ 语义检索（Phase 2.3）。"""
from __future__ import annotations

import streamlit as st

from ..constants import COLS
from ..db import load_db
from ..vector_db import _get_collection, _get_embedder
from .components import _render_card, _render_detail


def _render_search_results(sessions_scores: list[tuple], state_key: str) -> None:
    """渲染搜索结果卡片列表，score 为 None 时不显示相似度。"""
    all_db  = load_db()
    db_map  = {s["session_id"]: s for s in all_db}

    rows = []
    for sid, score in sessions_scores:
        session = db_map.get(sid)
        if session:
            rows.append((session, score))

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


def _render_date_filter() -> None:
    """Phase 2.2：日期范围过滤检索。结果持久化到 session_state。"""
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
        _render_search_results(
            [(sid, None) for sid, _ in sorted_data], "search_selected"
        )
    else:
        st.caption(f"该日期范围（{start_str} 至 {end_str}）内无精确日期记录")

    if fuzzy_ids:
        st.divider()
        with st.expander(f"⚠️ 以下 {len(fuzzy_ids)} 条记录使用了模糊时间描述，无法按日期过滤"):
            _render_search_results(
                [(sid, None) for sid in fuzzy_ids], "search_selected"
            )


def _render_semantic_search() -> None:
    """Phase 2.3：自然语言语义检索。结果持久化到 session_state。"""
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


def render_search_tab() -> None:
    mode = st.radio(
        "检索模式",
        ["📅 日期过滤", "🔍 语义检索", "💬 智能问答（即将上线）"],
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

    if mode == "💬 智能问答（即将上线）":
        st.info("智能问答功能正在开发中（Phase 2.4），敬请期待。")
        return

    st.divider()

    if mode == "📅 日期过滤":
        _render_date_filter()
    else:
        _render_semantic_search()
