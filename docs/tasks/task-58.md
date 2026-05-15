# Task-58：AI 标签直接填入 + 视觉区分

## 变更说明

**类型**：功能优化  
当前 AI 标签建议需在独立 expander 内勾选后点"应用"才填入标签框，操作分散且视觉割裂。本任务将流程改为：点击按钮即触发分析、结果直接填入标签 multiselect，toast 提示用户，AI 新增的标签（未入库）以橙色视觉区分，保存时才正式写库。

---

## 整体新流程

```
用户点击"🤖 AI 建议标签"
  → auto_tag_session() 分析内容
  → ① suggested_tags 合并进现有 tags multiselect 的 session state
  → ② new_tags 存入 {safe_sid}_ai_new_tags（未入库，仅 session）
  → ③ st.toast("AI 建议标签已更新，确认后保存生效")
  → rerun

页面重渲染：
  - tags multiselect 已包含 AI 建议项，用户可直接在此取消勾选
  - multiselect 正下方显示橙色 info 块，列出哪些是 AI 新增（未入库）的标签

用户点击"保存"：
  - 遍历 _ai_new_tags，仍在选中列表中的 → 写库（add_tag 或对应入库函数）
  - 清空 _ai_new_tags session state
```

---

## ai_tagging.py 改动行为

- **移除 `st.expander("✨ 让AI帮我选标签")`**；改为直接渲染按钮 + 提示区，无折叠层
- 点击分析按钮后调用 `auto_tag_session()`，将 `suggested_tags + new_tags` 合并写入 `apply_key` 对应的 multiselect session state，不再有独立 checkbox 列表
- **新增参数** `new_tags_key: str = ""`：函数将 `new_tags`（未入库的新标签）写入此键，供调用方在保存时处理入库
- 函数内**不再调用** `add_tag()`；入库时机移交调用方
- `st.toast("AI 建议标签已更新，确认后保存生效")` 在此函数内触发

## cards.py 改动行为

**集成点**：在 `_render_structured_detail_fields()` 或其调用位置附近增加 AI 标签触发区

- 调用 `render_ai_tag_picker(session_data, model_id, state_key=f"ai_tags_{safe_sid}", apply_key=<tags multiselect 的 widget key>, new_tags_key=f"{safe_sid}_ai_new_tags")`
  - `apply_key` 的具体格式：Codex 自行读 `render_field_inputs()` 确认 tags 字段的 widget key 命名规则
- `_render_structured_detail_fields()` 内，每个 multiselect 的 `options` 需将 `f"{safe_sid}_ai_new_tags"` 中尚未入库的标签追加进去（使其可被选中展示，但 DB 中暂无）
- 每个 multiselect 正下方：若 `_ai_new_tags` 中有标签仍在当前选中值里，渲染橙色信息块（HTML inline，仅展示不可交互）：
  ```
  🤖 AI 新增（保存后入库）: [tag1] [tag2] ...
  ```
- 保存逻辑（`do_save` / `do_archive` 两处）：
  - 从 `{safe_sid}_ai_new_tags` 取出未入库标签列表
  - 过滤出仍在最终选中值中的 → 调用 `add_tag()` 或对应函数写库
  - 从 session_state 删除 `{safe_sid}_ai_new_tags`

---

## 已知约束

- 新标签在保存前只存于 session state，不写 DB
- `st.toast()` 在 `ai_tagging.py` 内触发，`cards.py` 不重复触发
- multiselect 本身无法对单个选项染色（Streamlit 限制）；橙色区分通过 multiselect 下方独立 HTML 信息块实现（方案 A）
- `auto_tag_session()` 的返回结构（`suggested_tags` / `new_tags`）已存在，Codex 不需要改 `skills/tagging_skill.py`
- L2 契约同步：`docs/api/components.md` 中 `render_ai_tag_picker` 签名与行为描述需更新

---

## 验收（用户可见）

- [ ] 点击"🤖 AI 建议标签"→ toast 弹出提示，无需额外操作
- [ ] tags multiselect 自动包含 AI 建议项，用户无需手动勾选/应用
- [ ] AI 新增（未入库）的标签在 multiselect 正下方橙色块中显示
- [ ] 用户可在 multiselect 直接取消勾选任意 AI 建议标签
- [ ] 点击保存后：仍被选中的新标签写入库，橙色块消失
- [ ] 若用户在保存前取消勾选某 AI 新增标签，保存后该标签不入库
