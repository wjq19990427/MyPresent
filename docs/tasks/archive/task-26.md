# Task #26 — app.py 导航重构（6 Tab + 记录台嵌套）

## 目标

将现有 7 个平级 Tab 重组为 6 个，新增主页 Tab，并将记录台的三个子页用 `st.tabs` 嵌套实现，让导航层次更清晰。

**依赖**：task-25 必须先合并。

## 必读契约

- `docs/api/components.md`

## 改动范围

- **修改**：`app.py`
- **不许碰**：`components/tab_upload.py`、`tab_gallery.py`、`tab_archived.py`、`tab_planning.py`、`tab_recycle.py`、`eval_dashboard.py`（所有现有组件内部逻辑不动）

## 接口约定

新 Tab 顺序与标题：

```python
tabs = st.tabs([
    "🏠 主页",
    "📝 记录台",
    "🔍 探索",
    "📋 规划台",
    "🗑️ 回收站",
    "⚙️ 系统",
])
```

「📝 记录台」内部再嵌套：

```python
with tabs[1]:
    inner = st.tabs(["⬆️ 上传", "🗂️ 待处理", "📚 已归档"])
    with inner[0]: render_upload()
    with inner[1]: render_gallery()
    with inner[2]: render_archived()
```

其余 Tab 直接调用对应 render 函数，无嵌套。

## 不要做

- 不要改任何现有 render_* 函数的签名或内部逻辑
- 不要调整 session_state 初始化结构
- 不要给 Tab 加任何条件显示逻辑

## 验收清单

- [ ] `streamlit run app.py` 启动无报错
- [ ] 顶层共 6 个 Tab，顺序与任务卡一致
- [ ] 「记录台」内 3 个子 Tab 可正常切换，功能与重构前一致
- [ ] 主页 Tab 正常渲染（调用 task-25 的 `render_home()`）
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`st.tabs` 在 Streamlit 中不支持三层嵌套（外层 tabs → 内层 tabs 已是极限），本次只做两层，不要尝试更深嵌套。
