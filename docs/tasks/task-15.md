# Task #15 — 修复 AI 补全填入失效 + 灵感墙 AI 标签缺失

## 目标

修复两个 bug：
1. `render_ai_fill_picker` 点「✅ 应用」后感受/原因未填入表单（`pending_fill` 间接注入对 `st.form` 内 widget 不可靠）
2. 灵感墙（pending 模式）详情面板缺少 AI 标签推荐 Picker

## 必读契约

- `docs/api/components.md` # `ai_fill.py` 节 / `cards.py` 节

## 改动范围

- **修改**：`components/ai_fill.py`
- **修改**：`components/cards.py`
- **修改**：`components/tab_upload.py`
- **不许碰**：`core/` / `skills/` / 其他组件

## 实现要点

### Fix 1 — `components/ai_fill.py`：改为直接赋值

找到「✅ 应用」按钮的点击处理块，**全部替换**如下：

```python
# 原（删除这段）：
if st.button("✅ 应用", key=f"ai_fill_apply_{state_key}", type="primary"):
    st.session_state.pop(f"{form_prefix}_feeling", None)
    st.session_state.pop(f"{form_prefix}_reason", None)
    st.session_state[pending_key] = {
        "feeling": result["feeling"],
        "reason":  result.get("reason", ""),
    }
    st.session_state.pop(result_key, None)
    st.rerun()

# 改为：
if st.button("✅ 应用", key=f"ai_fill_apply_{state_key}", type="primary"):
    st.session_state[f"{form_prefix}_feeling"] = result["feeling"]
    if result.get("reason"):
        st.session_state[f"{form_prefix}_reason"] = result["reason"]
    st.session_state.pop(result_key, None)
    st.rerun()
```

`pending_key` 变量不再使用，可以删除其定义行。

### Fix 2 — `components/cards.py`：移除 pending_fill 逻辑

在 `with st.form(...)` 内，找到：
```python
pending_fill = st.session_state.pop(f"_ai_fill_pending_{fill_state_key}", None)
merged = {**session, **(pending_fill or {})}
field_values = render_field_inputs(edit_prefix, defaults=merged, skip_keys=skip_keys)
```

替换为：
```python
field_values = render_field_inputs(edit_prefix, defaults=session, skip_keys=skip_keys)
```

### Fix 3 — `components/tab_upload.py`：移除 pending_fill 逻辑

在 `with st.form("upload_meta_form"):` 内，找到：
```python
pending_fill = st.session_state.pop("_ai_fill_pending_upload_fill", None)
field_values = render_field_inputs(
    "upload",
    defaults=pending_fill or {},
    skip_keys=skip,
)
```

替换为：
```python
field_values = render_field_inputs("upload", skip_keys=skip)
```

### Fix 4 — `components/cards.py`：AI 标签 Picker 扩展到 pending 模式

找到：
```python
if mode == "final":
    render_ai_tag_picker(
        session_data=session,
        model_id=model_id,
        state_key=ai_picker_key,
        apply_key=tags_widget_key,
    )
    _render_ai_summary(session)
```

替换为：
```python
render_ai_tag_picker(
    session_data=session,
    model_id=model_id,
    state_key=ai_picker_key,
    apply_key=tags_widget_key,
)
if mode == "final":
    _render_ai_summary(session)
```

## 不要做

- 不要修改 `render_ai_fill_picker` 的函数签名
- 不要修改 `render_ai_tag_picker` 本身
- 不要在 `_render_ai_summary` 的调用逻辑外做任何其他改动

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 灵感墙或已归档 → 打开详情 → 点「✨ AI 补全感受与原因」→ 点「✅ 应用」→ 表单内感受/原因字段**立即显示** AI 生成文本
- [ ] 灵感墙 → 打开 pending 详情 → 出现「🤖 开始分析」AI 标签 Picker
- [ ] 已归档 → AI 标签 Picker 仍正常工作（回归检查）
- [ ] commit 符合规范（建议 `fix(ai_fill,cards): AI补全直接赋值+灵感墙AI标签 · 关联 #15`）
- [ ] 在 worktree 分支提交，未 push main
