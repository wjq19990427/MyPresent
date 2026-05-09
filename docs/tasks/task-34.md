# Task #34 — Bug 修复三合一 + prompt 截断优化

## 目标

修复三个已知问题：① 待处理/已归档 AI 分析报"内容为空"；② 文件夹导入要求必选标签；③ AnalysisSkill prompt 随标签库增大而变慢。

## 必读契约

- `docs/api/skills.md` # AnalysisSkill 节
- `docs/api/components.md` # ai_analysis.py 节 + tab_upload.py 节
- `docs/api/core.md` # `file_io.py::save_session_pending` 节

## 改动范围

- **修改**：`components/ai_analysis.py`
- **修改**：`skills/analysis_skill.py`
- **修改**：`components/tab_upload.py`
- **修改**：`docs/api/components.md` / `docs/api/skills.md`（如公开契约有变）
- **不许碰**：`core/db_manager.py`、任何其他组件

## Bug 1：AI 分析报"内容为空"

**根因**：`_run_session_analysis(session, ...)` 收到的是调用方已构建好的 session dict（含正确的 description / 文件信息），但内部丢弃该 dict，改用 `session_id` 重查 DB，DB 里 pending 记录的 `description` 往往为空。

**修复**：
- `_run_session_analysis` 改为直接调 `AnalysisSkill().execute_draft(session, ...)`，不再二次查库
- `_build_content(session)` 补充兜底逻辑：当所有文字字段均为空时，把 `session["files"]` 中的 `original_name` 拼入内容，让 LLM 至少知道文件名

`execute_draft` 的 description 判空检查改为：`description` 为空但有文件名时不报错，允许继续分析。

## Bug 2：文件夹导入必须选标签

**根因**：`_render_folder_import` 在调 `import_folder_to_pending` 前校验 `upload_tags` 非空。

**修复**：文件夹导入路径移除标签必填校验，直接调 `import_folder_to_pending(paths, as_one_session)`，不传 tags，文件进灵感墙后由用户统一处理。

## 优化：prompt 截断

**修复**：`_build_registry_section()` 中，每种 label type 最多取前 20 条传入 prompt（按 `is_system DESC, name ASC` 顺序截断），超出部分不传，避免标签库增大后 token 线性增长。

## 不要做

- 不要改 `execute(session_id)` 的行为（归档记录详情仍可用，不影响）
- 不要在文件夹导入路径写入任何默认标签
- 不要改 `_build_registry_section` 的接口签名

## 验收清单

- [ ] 灵感墙（待处理）打开含文件的记录详情，点「✨ AI 分析」不再报"内容为空"
- [ ] `description` 为空但有文件名时，AI 分析结果中可见文件名相关建议
- [ ] 文件夹导入点「开始导入」后直接进灵感墙，不提示"请选标签"
- [ ] `label_registry` 中某 type 有 30 条时，实际传入 prompt 的不超过 20 条（打印 prompt 验证）
- [ ] 已同步更新受影响的 `docs/api/*.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main
