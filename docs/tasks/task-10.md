# Task #10 — 回收站记录内容预览

## 目标

回收站每条记录下方增加可展开的内容预览，让用户在决定恢复或永久删除前能看到记录详情。

## 必读契约

- `docs/api/components.md` # `tab_recycle.py` 节

## 改动范围

- **修改**：`components/tab_recycle.py`（仅 `render_recycle_tab` 的循环体）
- **不许碰**：其他任何文件

## 实现要点

在每条记录的 `st.container(border=True)` 内，操作按钮行下方追加：

```python
with st.expander("📄 查看内容"):
    st.markdown(f"**描述**：{s.get('description') or '（无）'}")
    st.markdown(f"**感受**：{s.get('feeling') or '（无）'}")
    st.markdown(f"**记录原因**：{s.get('reason') or '（无）'}")
    tags = s.get("tags", [])
    st.markdown(f"**标签**：{' · '.join(tags) if tags else '（无标签）'}")
    files = s.get("files", [])
    if files:
        st.markdown("**文件**：" + " / ".join(f.get("original_name", "") for f in files))
```

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 回收站每条记录下方出现「📄 查看内容」折叠块，展开可见描述/感受/标签/文件
- [ ] commit 符合规范（建议 `feat(tab_recycle): 增加记录内容预览折叠块 · 关联 #10`）
- [ ] 在 worktree 分支提交，未 push main
