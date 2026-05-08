# Task #5 — 文件夹导入：自动排除已上传文件

## 目标

扫描结果展示前，自动过滤掉已经上传过的文件（通过文件名比对），并告知用户跳过了多少个，避免重复导入。

## 依赖

**必须在 task-4 合并后执行**，本任务基于 task-4 的新扫描结果结构。

## 必读契约

- `docs/api/components.md` # `tab_upload.py` 节
- `docs/api/core.md` # `file_io.py` 节（了解存储文件名格式：`{sid}_{idx:03d}_{orig_name}`）

## 改动范围

- **修改**：`components/tab_upload.py`（`_render_folder_import` 内，扫描结果处理段）
- **不许碰**：`core/db_manager.py` / `core/file_io.py` / 其他文件

## 实现要点

### 1. 新增私有辅助函数

```python
def _get_uploaded_filenames() -> set[str]:
    """返回 data/pending/ 和 data/final/ 中已存储文件的原始文件名集合。"""
    import re
    from core.constants import PENDING_DIR, FINAL_DIR
    result: set[str] = set()
    for d in (PENDING_DIR, FINAL_DIR):
        if not d.exists():
            continue
        for f in d.iterdir():
            m = re.search(r'_\d{3}_(.+)$', f.name)
            if m:
                result.add(m.group(1))
    return result
```

**原理**：存储文件名格式为 `{sid}_{idx:03d}_{orig_name}`，其中 `idx` 恒为 3 位零填充数字。正则 `_\d{3}_` 定位 idx 分隔符，取其后的部分即为原始文件名。

### 2. 在扫描结果生成后立即过滤

在 `_render_folder_import` 中，找到 `st.session_state["folder_scan_results"] = [str(f) for f in found]` 这一行，改为：

```python
uploaded = _get_uploaded_filenames()
filtered   = [f for f in found if f.name not in uploaded]
skipped_n  = len(found) - len(filtered)
st.session_state["folder_scan_results"]    = [str(f) for f in filtered]
st.session_state["folder_scan_skipped_n"]  = skipped_n
```

### 3. 在结果展示区显示跳过提示

在 `scan_results` 不为空的展示区顶部，加一行提示：

```python
skipped_n = st.session_state.get("folder_scan_skipped_n", 0)
if skipped_n:
    st.caption(f"⚠️ 已自动跳过 **{skipped_n}** 个文件名与已上传记录重复的文件")
```

若 `filtered` 为空但 `skipped_n > 0`，提示「该文件夹内所有文件均已上传」并提前 return。

## 不要做

- 不要使用文件内容哈希（只比文件名，轻量且足够）
- 不要修改 `PENDING_DIR` / `FINAL_DIR` 的引用方式（已在 constants 中定义）
- 不要改变 multiselect 默认全选的行为

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 选包含已上传文件的文件夹 → 扫描后已上传文件不出现在 multiselect 中，显示跳过提示
- [ ] 全新文件夹 → 无提示，行为与 task-4 完全一致
- [ ] 全部已上传 → 提示「所有文件均已上传」，不显示 multiselect
- [ ] commit 符合规范（建议 `feat(tab_upload): 扫描结果自动排除已上传文件 · 关联 #5`）
- [ ] 在 worktree 分支提交，未 push main
