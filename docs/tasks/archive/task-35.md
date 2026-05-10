# Task #35 — 标签体系重构 + 界面整理

## 目标

废弃旧扁平标签系统的 UI，统一使用新结构化标签（domains/attributes/topics/emotion_tags）；废除 AI 摘要功能（StorySkill）改为可编辑 summary 字段；调整上传页和详情页的布局顺序；新增四维度标签库管理面板。

**依赖**：task-34 先合并。

## 必读契约

- `docs/api/components.md` # cards.py + tab_upload.py + tab_archived.py + ai_analysis.py 节
- `docs/api/core.md` # db_manager.py::Tags Registry 节 + Label Registry 节

## 改动范围

- **修改**：`components/cards.py`
- **修改**：`components/tab_upload.py`
- **修改**：`components/tab_archived.py`
- **修改**：`components/ai_analysis.py`
- **修改**：`docs/api/components.md`
- **不许碰**：`components/ai_tagging.py` / `components/ai_fill.py`（保留，不删文件）
- **不许碰**：`core/db_manager.py` 的 `session_tags` / `tags_registry` 相关函数（后端保留）

## 接口约定

### 一、移除旧标签 UI

**cards.py `_render_detail`**：
- 删除 `selected_tags` multiselect（"标签，可多选，不计入编辑历史"）
- 删除 `tags_widget_key`、`ai_applied_tags`、`extra_tags`、`tag_options` 相关变量
- 删除 `_render_tag_manager()` 调用入口（管理标签 expander）
- 保存时 `field_values["tags"]` 改为从 `structured_values["topics"]` 同步（向量 embedding 桥接：保存前调 `update_session_tags(sid, topics)`）

**tab_upload.py**：
- 删除 `upload_tags` multiselect 控件
- 删除标签必填校验（"请至少选择一个标签"）
- 保存时 `tags` 参数改为从 `structured_values["topics"]` 传入

### 二、废除 AI 摘要，改为可编辑摘要

**cards.py**：
- 删除 `_render_ai_summary()` 调用和 expander（"✨ 生成 AI 摘要"）
- 在字段编辑区新增 `summary` 文本框（label="摘要"，选填，高度 90px）
- 保存时将 summary 写入 `field_values["summary"]`

**tab_upload.py**：
- `_render_structured_analysis_fields` 中已有 summary 文本框，确认其 label 为"摘要"（非"AI 摘要"）

### 三、AI 分析结果标签样式优化

**ai_analysis.py `_render_field_row`**：
- 对 `domains / attributes / topics / emotion_tags` 字段，将纯文字展示改为 badge 样式
- 已有（label_registry 中存在）：正常颜色 badge
- 新增（label_registry 中不存在）：加 ✨ 前缀或用括号标注"新"
- `new_topics` 改为在 topics 行内一并展示（标注"新"），不再单独显示 caption

### 四、标签库管理改为四维度

**cards.py `_render_tag_manager` 替换为 `_render_label_manager`**：
- 四个 sub-tab：领域 / 视角 / 话题 / 情绪
- 每个 tab：展示当前标签列表（系统标签 🔒 不可删）；文本输入 + 添加按钮；删除按钮（用户自定义标签）
- 调 `get_label_registry(type)` / `add_label(name, type)` / `remove_label(name, type)`
- 旧 `_render_tag_manager`（操作 `tags_registry`）删除

### 五、已归档页筛选三维度化

**tab_archived.py**：
- 筛选区增加三行：领域筛选 / 话题筛选 / 情绪筛选
- 每行默认全选（全部勾选 = 不筛选）
- 三个维度用不同颜色区分（用 `st.markdown` 带颜色的 badge 或 `st.pills` 实现）
- 筛选逻辑：同一维度内 OR（选多个领域取并集），跨维度 AND
- 旧 `archived_tag_filter`（基于 `tags_registry`）相关 state 和 UI 删除

### 六、上传页布局重排

按以下顺序渲染（调整 `render_upload_tab` 内部顺序）：
1. ✨ AI 分析面板
2. 📋 必填信息（render_field_inputs，含 title / content_time / description / feeling / reason）
3. 🧩 结构化标签（_render_structured_analysis_fields）
4. 📝 摘要（summary 文本框，选填）
5. 操作按钮

## 不要做

- 不要删除 `session_tags` 表或任何 db_manager 函数
- 不要删除 `ai_tagging.py` / `ai_fill.py` 文件
- 不要在 `_render_label_manager` 里保护系统标签（is_system=1）——DB 层不保护，UI 层只做 🔒 展示，不挂删除按钮

## 验收清单

- [ ] 上传页无旧标签 multiselect，保存/暂存时 topics 自动同步到 session_tags
- [ ] 详情页无旧标签 multiselect，有可编辑摘要文本框
- [ ] 无"AI 摘要"expander，详情页只有"摘要"文本框
- [ ] AI 分析结果中标签字段用 badge 展示，新增标签有明显标注
- [ ] 管理标签库 expander 内有四个 sub-tab，可增删（系统标签不挂删除按钮）
- [ ] 已归档页有三行颜色区分的筛选，默认全选，多维度 AND 逻辑正确
- [ ] 上传页五个区域顺序正确
- [ ] 已同步更新 `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

session_tags 桥接：保存时调 `update_session_tags(sid, topics_list)` 即可，topics 是字符串列表，与旧 session_tags 格式一致，向量 embedding 不需要感知变化。`archived_tag_filter` session_state 键删除时同步在 `state.py` 移除，避免孤儿键。
