# Task #14b — AI 自动补全：UI 组件 + 三处集成

## 目标

新建 `components/ai_fill.py` 提供 `render_ai_fill_picker` 组件，并将其集成到记录舱、灵感墙详情、已归档详情三个可编辑场景。用户可一键 AI 补全感受/原因，不满意可重新生成。

## 依赖

**必须在 task-14a 合并后执行。**

## 必读契约

- `docs/api/components.md` # `cards.py` 节（`_render_detail` 的 form 结构、safe_sid、`render_field_inputs` 调用位置）
- `docs/api/components.md` # `tab_upload.py` 节（upload form 结构，prefix="upload"）
- `docs/api/components.md` # `ai_tagging.py` 节（参照同款组件的状态机设计）
- `docs/api/skills.md` # `completion_skill.py` 节（task-14a 新增）

## 改动范围

- **新建**：`components/ai_fill.py`
- **修改**：`components/cards.py`（`_render_detail` 集成）
- **修改**：`components/tab_upload.py`（上传表单集成）
- **更新**：`docs/api/components.md`（新增 `ai_fill.py` 节 + 更新 cards/tab_upload 节）

## 实现要点

### 1. `components/ai_fill.py`

```python
"""AI 感受与原因自动补全组件。"""
from __future__ import annotations
import streamlit as st
from skills.completion_skill import CompletionSkill


def render_ai_fill_picker(
    session_data: dict,
    model_id: str,
    state_key: str,
    form_prefix: str,
) -> None:
    """
    - session_data: 至少含 description
    - model_id: 当前选中模型；空字符串时显示提示并 return
    - state_key: 本组件独占 session_state 命名空间
    - form_prefix: 关联表单的 prefix（用于强制刷新 feeling/reason 控件）
    """
    result_key  = f"_ai_fill_result_{state_key}"
    pending_key = f"_ai_fill_pending_{state_key}"
    result = st.session_state.get(result_key)

    if not model_id:
        st.caption("💡 在「运行看板」选择模型后可使用 AI 补全")
        return

    if not result:
        if st.button("✨ AI 补全感受与原因", key=f"ai_fill_btn_{state_key}"):
            desc = (session_data.get("description") or "").strip()
            if not desc:
                st.warning("描述为空，无法生成补全")
            else:
                with st.spinner("AI 生成中…"):
                    skill_result = CompletionSkill().execute(
                        {**session_data, "model_id": model_id}
                    )
                if skill_result.success:
                    st.session_state[result_key] = skill_result.data
                    st.rerun()
                else:
                    st.error(f"生成失败：{skill_result.error}")
    else:
        with st.container(border=True):
            st.caption("✨ **AI 补全建议**（点「应用」写入表单，不满意可重新生成）")
            st.markdown(f"**感受**：{result['feeling']}")
            if result.get("reason"):
                st.markdown(f"**记录原因**：{result['reason']}")
            ca, cb = st.columns(2)
            with ca:
                if st.button("✅ 应用", key=f"ai_fill_apply_{state_key}", type="primary"):
                    # 强制表单字段重新渲染
                    st.session_state.pop(f"{form_prefix}_feeling", None)
                    st.session_state.pop(f"{form_prefix}_reason", None)
                    st.session_state[pending_key] = {
                        "feeling": result["feeling"],
                        "reason":  result.get("reason", ""),
                    }
                    st.session_state.pop(result_key, None)
                    st.rerun()
            with cb:
                if st.button("🔄 重新生成", key=f"ai_fill_retry_{state_key}"):
                    st.session_state.pop(result_key, None)
                    st.rerun()
```

### 2. `components/cards.py` 集成

**import 新增**：
```python
from components.ai_fill import render_ai_fill_picker
```

**在 `_render_detail` 的 `with st.form(...)` 之前**，增加（须在 form 外调用）：

```python
model_id = st.session_state.get("llm_selected_model") or ""
fill_state_key = f"fill_{safe_sid}"
render_ai_fill_picker(
    session_data=session,
    model_id=model_id,
    state_key=fill_state_key,
    form_prefix=safe_sid,
)
```

**在 `with st.form(...)` 内，`render_field_inputs` 调用前**，合并 pending：

```python
pending_fill = st.session_state.pop(f"_ai_fill_pending_fill_{safe_sid}", None)
merged = {**session, **(pending_fill or {})}
field_values = render_field_inputs(safe_sid, defaults=merged, skip_keys=skip)
```

### 3. `components/tab_upload.py` 集成

**import 新增**：
```python
from components.ai_fill import render_ai_fill_picker
```

**在 `render_ai_tag_picker(...)` 调用之后，`with st.form("upload_meta_form"):` 之前**：

```python
render_ai_fill_picker(
    session_data={"description": auto_description},
    model_id=st.session_state.get("llm_selected_model") or "",
    state_key="upload_fill",
    form_prefix="upload",
)
```

**在 `with st.form("upload_meta_form"):` 内，`render_field_inputs` 调用前**：

```python
pending_fill = st.session_state.pop("_ai_fill_pending_upload_fill", None)
field_values = render_field_inputs("upload", defaults=pending_fill or {}, skip_keys=skip)
```

## 已知约束

- `render_ai_fill_picker` 必须在 `st.form` **外**调用（依赖 `st.button` 即时回写）
- `st.session_state.pop(pending_key)` 放在 `st.form` 内部也是安全的——pending 不是 widget key

## 不要做

- 不要修改 `render_field_inputs` 函数本身
- 不要在文件夹导入模式下调用此组件（无描述，无法补全）
- 不要对 `CompletionSkill().execute()` 加 try/except——SkillResult 已封装错误

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 记录舱：上传文件后，标签区下方出现「✨ AI 补全感受与原因」按钮
- [ ] 点击 → 出现感受/原因建议框 + 应用/重新生成按钮
- [ ] 点「✅ 应用」→ 表单内感受和记录原因字段预填 AI 内容
- [ ] 点「🔄 重新生成」→ 建议消失，重新调用出现新建议
- [ ] 灵感墙/已归档：详情面板（edit 模式）出现同款组件，应用后表单字段正确预填
- [ ] `docs/api/components.md` 新增 `ai_fill.py` 节
- [ ] commit 符合规范（建议 `feat(ai_fill): AI 感受+原因补全组件 + 三处集成 · 关联 #14b`）
- [ ] 在 worktree 分支提交，未 push main
