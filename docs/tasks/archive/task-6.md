# Task #6 — 记录舱：升级为完整 AI 标签 Picker

## 目标

将记录舱（上传 Tab）现有的简化「✨ AI」一键按钮升级为与灵感墙/已归档详情面板相同的完整 `render_ai_tag_picker` 组件（含推理说明、勾选框、应用按钮）。

## 背景

灵感墙和已归档的详情面板已通过 `cards._render_detail` 内嵌了完整 AI Picker，无需改动。
记录舱目前只有一个「✨ AI」按钮，直接将 AI 结果填入 multiselect，缺少推理展示和用户勾选步骤。

## 必读契约

- `docs/api/components.md` # `tab_upload.py` 节（标签区布局、上传流程）
- `docs/api/components.md` # `ai_tagging.py` 节（`render_ai_tag_picker` 签名、副作用、必须在 `st.form` 外调用）

## 改动范围

- **修改**：`components/tab_upload.py`
- **不许碰**：`components/ai_tagging.py` / `components/cards.py` / `core/` / `skills/`

## 实现要点

### 1. 更新 import

```python
# 删除（不再直接调用）
from skills.tagging_skill import auto_tag_session

# 新增
from components.ai_tagging import render_ai_tag_picker
```

（`add_tag` import 在 task-2 已加入，保留不动）

### 2. 替换标签区 AI 按钮

找到标签区布局（`tag_col, ai_col = st.columns([5, 1])`），将 `with ai_col:` 整块替换，同时扩展布局为全宽：

删除：
```python
tag_col, ai_col = st.columns([5, 1])
with tag_col:
    upload_tags = st.multiselect(...)
with ai_col:
    model_id  = st.session_state.get("llm_selected_model") or ""
    ai_ready  = bool(model_id)
    if st.button("✨ AI", ...):
        with st.spinner("AI 推荐标签中…"):
            suggestions = auto_tag_session(...)
        combined = suggestions["suggested_tags"] + suggestions["new_tags"]
        if combined:
            for tag in suggestions["new_tags"]:
                add_tag(tag)
            st.session_state[f"upload_tags_{st.session_state.upload_key}"] = combined
            st.rerun()
        else:
            st.warning("未能推荐到标签，请手动选择")
```

替换为：
```python
upload_tags = st.multiselect(
    "标签",
    options=get_tags_registry(),
    key=f"upload_tags_{st.session_state.upload_key}",
    label_visibility="collapsed",
    placeholder="至少选择一个标签",
)
model_id = st.session_state.get("llm_selected_model") or ""
render_ai_tag_picker(
    session_data={"description": auto_description, "feeling": ""},
    model_id=model_id,
    state_key="upload_ai",
    apply_key=f"upload_tags_{st.session_state.upload_key}",
)
```

### 3. 确认调用位置

`render_ai_tag_picker` 必须在 `st.form("upload_meta_form")` **之前**调用。检查当前代码，标签区已在 form 之前，无需调整位置。

## 不要做

- 不要改动 `upload_meta_form` 内的任何逻辑
- 不要修改 `render_ai_tag_picker` 函数本身
- 不要在文件夹导入模式（`_render_folder_import`）中添加 AI Picker（文件夹模式无描述内容，无法打标）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 上传文件后，标签区出现「🤖 开始分析」按钮（原「✨ AI」按钮消失）
- [ ] 点「🤖 开始分析」→ 显示推理说明 + suggested/new 分类 + 勾选框
- [ ] 点「✅ 应用选中标签」→ 标签 multiselect 默认值更新，新标签写入标签库
- [ ] commit 符合规范（建议 `feat(tab_upload): 升级 AI 标签为完整 Picker · 关联 #6`）
- [ ] 在 worktree 分支提交，未 push main
