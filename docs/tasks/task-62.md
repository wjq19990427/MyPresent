# task-62 · 上传 Tab 简化：移除文件夹导入，多文件各自成独立记录

## 变更说明

**类型**：优化  
移除上传页的「导入文件夹」入口，保留文件上传和粘贴文字两种模式。同时调整多文件上传的行为：选中 N 个文件，生成 N 条独立的待处理记录，不再合并为一条。

---

## 涉及文件

- `components/tab_upload.py`
- `core/file_io.py`（`import_folder_to_pending` 可随之删除）
- `core/constants.py`（`SUPPORTED_IMPORT_EXTS` 如仅供文件夹导入使用则一并清理）
- `core/state.py`（清理 `folder_scan_results`、`folder_import_done`、`folder_selected_path`、`folder_scan_skipped_n` 等 state 键）

---

## 变更清单

### 1. 移除文件夹导入

- 上传方式 radio 从三项缩减为两项：`📁 上传文件` / `📝 粘贴文字`
- 删除 `_render_folder_import()`、`_pick_folder_dialog()` 及所有相关 session_state 键
- 删除 `import_folder_to_pending()` 函数（file_io.py）

### 2. 多文件上传：每个文件独立成一条待处理记录

**当前行为**：上传 N 个文件 → 填写一张表单 → 生成一条包含 N 个文件的 session。

**新行为**：
- 上传 N 个文件时，跳过表单，直接批量生成 N 条独立的 pending session，每条只含一个文件
- 生成完成后给出提示（如"已创建 3 条待处理记录，前往灵感墙处理"），不展示表单
- 单文件上传行为不变：仍展示表单，用户可填写字段后选择暂存或直接归档

---

## 验收标准

- 上传页只有「上传文件」和「粘贴文字」两个入口，无文件夹相关 UI
- 一次选中多个文件上传后，灵感墙中出现对应数量的独立记录，每条记录只含一个文件
- 单文件上传流程与当前完全一致，无回归
- 粘贴文字流程与当前完全一致，无回归
