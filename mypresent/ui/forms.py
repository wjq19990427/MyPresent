"""表单字段渲染工具。"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from ..constants import FIELD_SCHEMA


def _render_date_or_text(field: dict, prefix: str, default: str = "") -> str:
    """渲染日历选取 + 自由输入双控件，自由输入优先。"""
    default_date = None
    default_free = default
    if default:
        try:
            default_date = datetime.strptime(default, "%Y-%m-%d").date()
            default_free = ""
        except ValueError:
            pass

    col1, col2 = st.columns(2)
    with col1:
        sel_date = st.date_input(
            "📅 日历选取",
            value=default_date,
            key=f"{prefix}_{field['key']}_date",
        )
    with col2:
        free = st.text_input(
            "✏️ 自由输入",
            value=default_free,
            placeholder=field["placeholder"],
            key=f"{prefix}_{field['key']}_text",
        )
    return free.strip() if free.strip() else (str(sel_date) if sel_date else "")


def render_field_inputs(
    prefix: str,
    defaults: dict | None = None,
    skip_keys: set | None = None,
) -> dict:
    """根据 FIELD_SCHEMA 渲染所有字段，返回 {key: value}。
    skip_keys 中的字段不渲染控件，但其已有值仍保留在返回值中。
    """
    defaults         = defaults or {}
    skip_keys        = skip_keys or set()
    values           = {}
    shown_opt_header = False

    for field in FIELD_SCHEMA:
        key = field["key"]

        if key in skip_keys:
            values[key] = str(defaults.get(key, ""))
            continue

        if not field["required"] and not shown_opt_header:
            st.divider()
            st.caption("以下为选填项")
            shown_opt_header = True

        badge = " **\\*（必填）**" if field["required"] else " （选填）"
        st.markdown(f"**{field['label']}**{badge}")
        if field.get("help"):
            st.caption(field["help"])

        default = str(defaults.get(key, ""))
        wkey    = f"{prefix}_{key}"

        if field["type"] == "date_or_text":
            values[key] = _render_date_or_text(field, prefix, default)
        elif field["type"] == "textarea":
            values[key] = st.text_area(
                field["label"],
                value=default,
                placeholder=field["placeholder"],
                height=100,
                key=wkey,
                label_visibility="collapsed",
            )
        else:
            values[key] = st.text_input(
                field["label"],
                value=default,
                placeholder=field["placeholder"],
                key=wkey,
                label_visibility="collapsed",
            )

    return values
