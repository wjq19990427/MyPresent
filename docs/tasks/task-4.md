# Task #4 — 文件夹导入：资源管理器选文件夹 + 递归扫描

## 目标

将「导入文件夹」的路径输入方式从手动文字框改为系统文件夹选择器（Windows 资源管理器），并将扫描从单层 `iterdir()` 升级为递归 `rglob()`，自动覆盖子目录。

## 必读契约

- `docs/api/components.md` # `tab_upload.py` 节（文件夹导入流程、session_state 键）

## 改动范围

- **修改**：`components/tab_upload.py`（仅 `_render_folder_import` 函数）
- **不许碰**：`core/` / `skills/` / 其他组件

## 实现要点

### 1. 新增私有辅助函数（在 `_render_folder_import` 上方）

```python
def _pick_folder_dialog() -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', True)
    folder = filedialog.askdirectory(title="选择导入文件夹")
    root.destroy()
    return folder or ""
```

### 2. 替换路径输入区（`_render_folder_import` 内）

删除：
```python
folder_str = st.text_input(
    "文件夹路径",
    placeholder=r"例：C:\Users\xxx\Pictures  或  /home/xxx/photos",
    key="folder_path_input",
)
```

替换为：
```python
folder_str: str = st.session_state.get("folder_selected_path", "")
col_pick, col_disp = st.columns([1, 3])
with col_pick:
    if st.button("📂 选择文件夹", key="pick_folder_btn"):
        picked = _pick_folder_dialog()
        if picked:
            st.session_state["folder_selected_path"] = picked
            st.session_state["folder_scan_results"]  = []
            st.rerun()
with col_disp:
    if folder_str:
        st.caption(f"已选：`{folder_str}`")
    else:
        st.caption("请点击左侧按钮选择文件夹")
```

### 3. 更新扫描逻辑

扫描按钮内，将非递归改为递归：

```python
# 原
found = sorted(
    [f for f in folder.iterdir()
     if f.is_file() and f.suffix.lower() in SUPPORTED_IMPORT_EXTS],
    key=lambda p: p.name,
)
# 改为
found = sorted(
    [f for f in folder.rglob("*")
     if f.is_file() and f.suffix.lower() in SUPPORTED_IMPORT_EXTS],
    key=lambda p: p.name,
)
```

### 4. 更新扫描触发条件

原来依赖 `do_scan = st.button(...)` 且需 `folder_str.strip()` 非空。改为依赖 `folder_str` 来自 session_state；扫描按钮仍保留：

```python
do_scan = st.button("🔍 扫描文件夹", type="primary", key="scan_folder_btn",
                    disabled=not folder_str)
if do_scan:
    folder = Path(folder_str)
    # 去掉"路径为空"和"路径不存在"的 warning（pick_folder_dialog 已保证路径有效）
    # 只保留 is_dir() 检查（理论上不会触发，但保留为防御）
    ...
```

## 不要做

- 不要改 multiselect 选文件、导入按钮、标签等后续逻辑
- 不要跨平台兼容（项目仅在 Windows 本地运行，tkinter 默认可用）
- 不要在 `_pick_folder_dialog` 内 try/except（对话框取消时返回空字符串，调用方已处理）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 点「📂 选择文件夹」→ 弹出系统文件夹选择器 → 选择后路径显示在按钮旁
- [ ] 点「🔍 扫描文件夹」→ 扫描结果包含子目录下的文件
- [ ] commit 符合规范（建议 `feat(tab_upload): 文件夹选择器替换手动路径 + 递归扫描 · 关联 #4`）
- [ ] 在 worktree 分支提交，未 push main

## 架构师备注

- `folder_selected_path` 新增 session_state 键，需在 `core/state.py` 的 `init_state` 中初始化；若 Codex 发现该文件中有统一初始化逻辑，必须同步补充，不可遗漏。
- 扫描后清空 `folder_scan_results` 是期望行为（换了新路径就重置结果）
