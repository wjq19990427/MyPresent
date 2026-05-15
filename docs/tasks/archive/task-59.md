# Task-59：AI 内容生成拆分 + 内联字段建议

## 变更说明

**类型**：重构 + 功能优化  
记录台 AI 分析功能当前存在两个问题：① AI 分析（生成全部字段）与 AI 标签建议（task-58）共同运行时产生两次 API 调用且标签重复生成；② 内容建议展示在独立面板，与实际输入框脱节。本任务将二者彻底拆分：标签 AI 只管标签，内容 AI 只管文本字段；文本建议直接在对应输入框正下方展示，逐条采纳。

---

## 核心改动

### 1. `components/forms.py` — `render_field_inputs()`

新增两个可选参数：
- `suggestions: dict[str, str] = {}`：`{field_key: ai_suggested_text}` 的建议映射
- `suggestions_key: str = ""`：上述 dict 在 `st.session_state` 中的存储键，采纳时用于从中删除已处理字段

**行为变更**：对 `type == "textarea"` 和 `type` 为纯文本输入的字段，在 widget 渲染完毕后，若 `suggestions.get(key)` 非空，则在该 widget 正下方渲染内联建议块：
```
🤖 AI 建议：{建议文本}     [ ✓ 采纳 ]
```
"采纳"按钮行为：
- `st.session_state[wkey] = suggestion`（覆盖 widget 当前值）
- 若 `suggestions_key` 非空：从 `st.session_state[suggestions_key]` 中删除该 `key`
- `st.rerun()`

`date_or_text` 类型字段不渲染建议块。

---

### 2. `components/cards.py`

**移除**：`render_session_ai_analysis()` 调用（约 387–393 行）及 `_apply_analysis_to_detail_form()` 函数。同步移除对 `components.ai_analysis` 的 `render_session_ai_analysis` 导入（若 `render_ai_analysis` 也不再使用则整行移除）。

**新增**：在 `render_field_inputs()` 调用之前，渲染一个"✨ AI 生成内容"触发区：
- 按钮点击后 → 调用 `AnalysisSkill().execute_draft(analysis_session, model_id, fields=["title", "feeling", "reason", "summary", "emotion_note"], hint="")` → 将结果 dict 写入 `st.session_state[f"{safe_sid}_ai_content_suggestions"]` → `st.toast("AI 内容建议已生成")` → `st.rerun()`
- 需从 `skills.analysis_skill` 导入 `AnalysisSkill`

**传入建议**：`render_field_inputs()` 调用时追加：
```python
suggestions=st.session_state.get(f"{safe_sid}_ai_content_suggestions", {}),
suggestions_key=f"{safe_sid}_ai_content_suggestions",
```

**`summary` 字段**（独立 `st.text_area`，约 413 行）：在该 text_area 下方，若 `suggestions.get("summary")` 存在，渲染同款内联建议块 + 采纳按钮（采纳时写 `f"{safe_sid}_summary"` 并从 suggestions 中删除）。

**`_render_structured_detail_fields()` 中的 `emotion_note`**（独立 `st.text_area`）：同上，采纳时写 `f"{safe_sid}_emotion_note"`。

**保存/归档时**：清空 `f"{safe_sid}_ai_content_suggestions"`（`st.session_state.pop(key, None)`）。

---

### 3. `components/ai_analysis.py`

- `render_session_ai_analysis()` 函数在 `cards.py` 不再被调用；可保留但标注为仅供未来复用，不删除（避免 git 历史丢失）
- `render_ai_analysis()`（供 `tab_upload.py` 草稿流程使用）**不变**

---

## 已知约束

- `AnalysisSkill.execute_draft()` 接收 session dict + model_id + fields 列表，已支持选择性字段生成，无需改 skill 层
- 建议块只在 `suggestions` 中有对应 key 时才显示；用户采纳后该 key 被删除，建议块消失
- `render_field_inputs()` 新参数均有默认值，其他调用方（`tab_upload.py` 等）无需改动
- L2 契约同步：`docs/api/components.md` 更新 `render_field_inputs` 签名、`cards._render_detail` 渲染流程说明

---

## 验收（用户可见）

- [ ] 记录台详情页不再出现旧的"✨ AI 分析"整体面板
- [ ] 点击"✨ AI 生成内容"→ toast 提示，输入框下方出现对应字段的 AI 建议
- [ ] 点击某字段"✓ 采纳"→ 该字段文本框填入 AI 建议，建议块消失
- [ ] 不采纳的字段建议持续可见，不影响其他字段
- [ ] 点击"🤖 AI 建议标签"→ 只触发标签分析，不重复生成内容字段（两次调用变为两次独立调用，无重叠）
- [ ] 上传草稿流程（tab_upload.py）的 AI 分析功能不受影响
