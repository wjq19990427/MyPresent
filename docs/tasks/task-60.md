# Task-60：详情页布局三段化 + AI 标签四维扩展

## 变更说明

**类型**：重构 + 功能优化  
将记录台详情页改为三段式布局（文本 → 分类 → 元数据），同时将 AI 标签建议从仅针对"话题"扩展到全四维度（领域/视角/话题/情绪），且只在评估后认为标签库确实缺失更合适标签时才提出新标签。同步优化 Prompt 模板与 Skill 返回结构。

---

## 一、布局调整（`components/cards.py`）

`_render_detail()` 内容按以下三段顺序渲染：

**第一段：文本内容**
- 文本正文（is_text 时的文件内容；否则跳过，description 字段由 render_field_inputs 处理）

**第二段：分类标签**（`st.divider()` 分隔）
- `[🤖 AI 建议标签]` 按钮（`render_ai_tag_picker()`）
- 结构化标签（领域 / 视角 / 话题 / 情绪），由 `_render_structured_detail_fields()` 渲染
- ⚠️ `_render_structured_detail_fields()` 移除 `emotion_note` 字段的渲染（移至第三段）

**第三段：内容元数据**（`st.divider()` 分隔）
- `[✨ AI 内容解析]` 按钮（`_render_ai_content_generator()`，按钮文案由 "AI 生成内容" 改为 "AI 内容解析"）
- `summary` 文本框 + 内联建议块
- `render_field_inputs()`（title / description / feeling / reason 等，含内联建议块）
- `emotion_note` 文本框 + 内联建议块（从结构化标签区迁移至此）

---

## 二、AI 标签四维扩展

### 2a. `core/prompts.py`

重写 `TAGGING_SYSTEM` 和 `TAGGING_USER_TMPL`：

**TAGGING_SYSTEM** 核心要点：
- 描述四维标签体系：领域（domain）/ 视角（attribute）/ 话题（topic）/ 情绪（emotion）
- 从各维度现有标签中优先选取，每维度 0-3 个
- **仅当**某维度现有标签明显不足以描述记录的重要特征时，才可提出新标签（每维度 ≤ 1 个）；不确定时宁可空列表，不强行新增
- 新标签须 2-6 字，风格与同维度现有标签一致

**输出 JSON 结构**（须在 Prompt 中明确示意）：
```json
{
  "suggested": {
    "domains":     ["..."],
    "attributes":  ["..."],
    "topics":      ["..."],
    "emotion_tags":["..."]
  },
  "new_labels": {
    "domains":     [],
    "attributes":  [],
    "topics":      [],
    "emotion_tags":["..."]
  },
  "reasoning": "50字以内"
}
```

**TAGGING_USER_TMPL** 需包含四维现有标签列表（格式：各维度名称 + 标签列表），以及记录内容（description / feeling）。

### 2b. `skills/tagging_skill.py`

**`TaggingSkill.execute()`**：
- 改用 `get_label_registry(type)` 分别获取四维标签：domain / attribute / topic / emotion
- 将四维标签列表注入 `TAGGING_USER_TMPL`
- 解析新 JSON 结构，校验 `suggested.*` 的每个条目必须存在于对应维度注册表中（不存在则丢弃）；`new_labels.*` 不校验（允许全新词条）
- 返回 `SkillResult.data` 结构改为：
  ```python
  {
    "suggested":  {"domains": [], "attributes": [], "topics": [], "emotion_tags": []},
    "new_labels": {"domains": [], "attributes": [], "topics": [], "emotion_tags": []},
    "reasoning":  "...",
  }
  ```
- `auto_tag_session()` 返回值同步改为上述结构；失败时返回各维度空列表

**向后兼容**：`run()` 方法不变（只委托给 execute）

### 2c. `components/ai_tagging.py`

**`render_ai_tag_picker()` 签名变更**：
- 移除 `apply_key: str`，改为 `apply_keys: dict[str, str] = {}`，格式：`{field_name: session_state_key}`，如 `{"domains": "{safe_sid}_domains", ...}`
- `new_tags_key: str` 保留，但对应的 session state 值改为 `dict[str, list[str]]`（键为维度名）

**点击"🤖 AI 建议标签"后**：
- 调用 `auto_tag_session()` 获取新结构
- 对 `suggested` 的每个维度：合并写入 `apply_keys[field]` 对应的 session state
- 对 `new_labels` 的每个维度：合并写入 `st.session_state[new_tags_key][field]`（dict 结构）
- `st.toast()` + `st.rerun()`

### 2d. `components/cards.py`（标签相关部分）

**`render_ai_tag_picker` 调用**改为传入 `apply_keys` dict（四个维度全部传入）：
```python
apply_keys={
    "domains":     f"{safe_sid}_domains",
    "attributes":  f"{safe_sid}_attributes",
    "topics":      f"{safe_sid}_topics",
    "emotion_tags":f"{safe_sid}_emotion_tags",
}
```

**`_structured_options(field, session)`**：从 `st.session_state[new_tags_key]` 取对应维度的新标签列表追加进 options（当前是取整个 flat list，改为取 `dict.get(field, [])`）

**`_render_ai_new_tags_notice(safe_sid, field, selected)`**：扩展为对任意维度均可调用（由调用方传 `field` 参数），在 `_render_structured_detail_fields()` 中每个 multiselect 后均调用

**`_clear_ai_new_tags_state(safe_sid)`**：不变，仍 pop 整个 `_ai_new_tags` key（现在该 key 存 dict，整体清空即可）

---

## 已知约束

- `get_label_registry(type)` 返回 `[{"name": "...", ...}]`，Codex 自行取 `item["name"]`
- `_render_structured_detail_fields()` 函数签名加 `suggestions` / `suggestions_key` 参数（已有），`emotion_note` 渲染逻辑整体迁移到调用方（`_render_detail()`），函数内不再渲染 emotion_note
- `ai_tagging.py` 中 `_clean_tags()` 工具函数保持不变
- L2 契约同步：`docs/api/components.md` 更新 `render_ai_tag_picker` 签名与 `cards._render_detail` 布局说明

---

## 验收（用户可见）

- [ ] 详情页三段式布局：文本正文 → 分类标签 → 内容元数据，各段间有分割线
- [ ] 情绪描述（emotion_note）出现在第三段（内容元数据），不再在结构化标签区
- [ ] "AI 建议标签"按钮位于结构化标签正上方
- [ ] "AI 内容解析"按钮位于第三段，不再叫"AI 生成内容"
- [ ] 点击"AI 建议标签"→ 四个维度均可能获得建议，不仅限于话题
- [ ] AI 新标签（未入库）仅在评估后确认缺失时才出现，不强行生成
- [ ] 各维度 AI 新标签的橙色提示块分别显示在对应 multiselect 下方
- [ ] 保存/归档后 AI 标签建议缓存（dict 结构）正确清空
