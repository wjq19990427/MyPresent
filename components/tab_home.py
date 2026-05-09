"""主页 Tab：项目介绍与功能模块概览。"""
from __future__ import annotations

import streamlit as st


_INTRO = """MyPresent 是一个专注于生活记录、思考归档与个人规划的私有化 Agent。
它将你散落在生活中的照片、视频、随笔，以及你对未来的期望与每日的行动，
汇聚为一个可检索、可追溯、可生长的个人知识库——一个真正读懂你的「第二大脑」。"""

_MODULES = [
    (
        "📝 记录台",
        "上传并管理你的个人记录。支持图片、视频与文字，暂存于待处理区后可整理归档。AI 可自动推荐标签、补全感受、生成摘要，让每一条记录完整留存。",
    ),
    (
        "🔍 探索",
        "三种方式找回你的记忆：按日期范围过滤、用自然语言语义检索，或直接向 AI 提问——「那年夏天我去了哪里？」",
    ),
    (
        "📋 规划台",
        "从年度大目标出发，拆解为每日待办，同时记录每天的活动与时间分配。日历视图让你在时间轴上看清规划与执行的全貌，形成完整的个人成长闭环。",
    ),
    (
        "🗑️ 回收站",
        "已删除的记录在这里保留 30 天，随时可一键恢复，防止误删。",
    ),
    (
        "⚙️ 系统",
        "配置 LLM API Provider 与模型，查看 AI 调用统计与响应延迟，追踪所有操作日志。",
    ),
]


def render_home() -> None:
    """渲染主页标题区与功能模块卡片，无交互和状态副作用。"""
    st.title("MyPresent")
    st.markdown(
        '"只要一直在记录思考和当下的状态，以及一些生活琐碎，就是在好好生活。"'
    )
    st.markdown(_INTRO)

    st.divider()

    _render_module_row(_MODULES[:3], 3)
    _render_module_row(_MODULES[3:], 2)


def _render_module_row(modules: list[tuple[str, str]], column_count: int) -> None:
    cols = st.columns(column_count)
    for col, (title, body) in zip(cols, modules):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {title}")
                st.write(body)
