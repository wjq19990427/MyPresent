# Task #11b — 批量管理：灵感墙 + 已归档批量操作 UI

## 目标

在灵感墙和已归档 Tab 各新增「批量管理」切换按钮，激活后以列表形式展示记录（调用 task-11a 的 `_render_batch_row`），并提供批量操作栏。

## 依赖

**必须在 task-11a 合并后执行。**

## 必读契约

- `docs/api/components.md` # `tab_gallery.py` 节 / `tab_archived.py` 节 / `cards.py` 节
- task-11a 新增的 `_render_batch_row` 函数签名

## 改动范围

- **修改**：`components/tab_gallery.py`
- **修改**：`components/tab_archived.py`
- **不许碰**：`cards.py` / `core/` / `skills/`

## 实现要点（两个 Tab 逻辑对称）

### 1. 批量模式切换（各 Tab 顶部）

```python
col_title, col_batch = st.columns([6, 1])
with col_batch:
    batch_mode = st.session_state.get("batch_mode_gallery", False)  # 或 batch_mode_archived
    if st.button("🔲 批量管理" if not batch_mode else "✅ 退出批量", key="toggle_batch_gallery"):
        st.session_state["batch_mode_gallery"] = not batch_mode
        st.session_state["batch_selected_ids"] = set()
        st.rerun()
```

### 2. 批量模式下的操作栏（batch_mode=True 时，在卡片区上方）

```python
selected: set = st.session_state.get("batch_selected_ids", set())
st.markdown(f"已选 **{len(selected)}** 条")
col_a, col_b, col_c = st.columns(3)

# 灵感墙操作栏
with col_a:
    if st.button("🗑️ 批量移入回收站", disabled=not selected):
        for sid in list(selected):
            soft_delete_session(sid)
        st.session_state["batch_selected_ids"] = set()
        st.rerun()
with col_b:
    if st.button("📁 批量归档", disabled=not selected):
        from core.file_io import move_to_final
        for sid in list(selected):
            move_to_final(sid)
        st.session_state["batch_selected_ids"] = set()
        st.rerun()
with col_c:
    if st.button("↩️ 全部取消选择", disabled=not selected):
        st.session_state["batch_selected_ids"] = set()
        st.rerun()
```

**已归档操作栏** 差异：
- 无「批量归档」按钮（已经是 final）
- 增加「🏷️ 批量加标签」：弹出 multiselect 选标签，确认后对每条调用 `update_session_tags(sid, existing + new)`

```python
# 已归档专有
with col_b:
    new_tags = st.multiselect("选择要添加的标签", get_tags_registry(), key="batch_add_tags")
    if st.button("🏷️ 添加标签", disabled=not selected or not new_tags):
        for sid in list(selected):
            s = get_session(sid)
            if s:
                merged = list(set(s.get("tags", []) + new_tags))
                update_session_tags(sid, merged)
        st.session_state["batch_selected_ids"] = set()
        st.rerun()
```

### 3. 卡片区切换

```python
if batch_mode:
    for session in sessions:        # sessions 已过滤好
        _render_batch_row(session)
    st.divider()
else:
    # 原有卡片网格逻辑不变
    ...
```

### 4. 退出批量模式时清空选中态

切换 batch_mode 时已清空 `batch_selected_ids`（见步骤 1）。

## 不要做

- 不要修改现有卡片网格逻辑（`_render_card` 调用不变）
- 不要在批量模式下显示详情面板
- 批量操作不加二次确认（软删除可恢复；归档可在已归档里删除）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 灵感墙顶部出现「🔲 批量管理」按钮，点击进入列表+checkbox 视图
- [ ] 勾选多条 → 「批量移入回收站」→ 记录消失，出现在回收站
- [ ] 勾选多条 → 「批量归档」→ 记录移入已归档
- [ ] 已归档：批量加标签流程跑通
- [ ] 退出批量模式回到卡片网格视图
- [ ] commit 符合规范（建议 `feat(tab_gallery,tab_archived): 批量管理模式 · 关联 #11b`）
- [ ] 在 worktree 分支提交，未 push main
