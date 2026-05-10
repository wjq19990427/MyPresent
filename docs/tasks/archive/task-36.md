# Task #36 — 卡片展示重设计

## 目标

重设计归档和待处理两个板块的记录卡片：展示标题、用户录入时间、记录类型角标、三维度结构化标签，移除旧 tags 展示。

**依赖**：task-35 先合并（旧 tags UI 已移除，结构化标签字段已稳定）。

## 必读契约

- `docs/api/components.md` # cards.py 节

## 改动范围

- **修改**：`components/cards.py`（`_render_card` 函数）
- **修改**：`docs/api/components.md`
- **不许碰**：卡片点击逻辑、`_render_detail`、batch 模式、其他组件

## 接口约定

### `_render_card(session, ...) -> None` 展示内容变更

**移除**：
- 旧 `tags`（session_tags）展示
- 上传时间（`upload_time`）
- 完整度 badge（`is_complete`）

**新增**：

**记录类型角标**（右上角或标题行）：
- 📝 纯文本：`source_type == "text"` 或所有文件均为 `.txt/.md`
- 📷 图片：主要文件为图片格式
- 🎬 视频：主要文件为视频格式
- 混合（图文/多类型）：📎

判断逻辑：`_infer_record_type(session) -> str`，读 `session["files"]` 的扩展名，取最多的类型；无文件时看 `source_type`。

**标题**：`session["title"]`；若为空则截取 `session["description"]` 前 30 字；均为空则显示"（未命名）"

**内容时间**：`session["content_time"]`；为空则不显示

**结构化标签 badge**（最多展示 6 个，超出显示 +N）：
- 领域标签（domains）：蓝色系
- 视角标签（attributes）：绿色系
- 话题标签（topics）：橙色系
- 超出部分：灰色 `+N`

情绪标签（emotion_tags）不在卡片展示（在详情里看）。

**文件信息**（保留，缩小）：文件数量角标（如有多个文件）

### badge 渲染方式

用 `st.markdown` 输出带颜色的 HTML badge，格式参考现有代码风格，不引入新依赖。

## 不要做

- 不要改卡片的点击交互逻辑
- 不要改 `_render_batch_row`（批量模式行）的布局，只改 `_render_card`
- 不要给卡片加复杂动画或重样式

## 验收清单

- [ ] 已归档和待处理的卡片均显示：标题 / content_time / 类型角标 / 结构化 badge
- [ ] 无旧 tags 字符串展示，无 is_complete badge
- [ ] 纯文本记录显示 📝，图片显示 📷，视频显示 🎬
- [ ] content_time 为空时该行不渲染（不显示空白）
- [ ] 结构化标签超过 6 个时显示 `+N`
- [ ] 已同步更新 `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main
