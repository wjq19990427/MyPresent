# Task #11a — 批量管理：cards.py 新增批量行视图

## 目标

在 `cards.py` 新增 `_render_batch_row` 函数，供灵感墙 / 已归档在批量管理模式下渲染一行记录（checkbox + 摘要），替代卡片网格视图。

## 必读契约

- `docs/api/components.md` # `cards.py` 节（现有函数、safe_sid 约定）

## 改动范围

- **修改**：`components/cards.py`（新增一个函数，不改现有函数）
- **更新**：`docs/api/components.md`（cards.py 节追加函数说明）
- **不许碰**：tab_gallery / tab_archived / 其他文件

## 实现要点

### 新函数签名

```python
def _render_batch_row(session: dict, selected_key: str = "batch_selected_ids") -> None:
```

- `session`：完整 session dict
- `selected_key`：存储已选 session_id 集合的 session_state 键（默认 `batch_selected_ids`）

### 实现

```python
def _render_batch_row(session: dict, selected_key: str = "batch_selected_ids") -> None:
    sid      = session["session_id"]
    safe_sid = "".join(c if c.isalnum() else "_" for c in sid)
    selected: set = st.session_state.get(selected_key, set())

    cols = st.columns([0.5, 1, 5, 3])
    with cols[0]:
        checked = st.checkbox("", value=sid in selected, key=f"bchk_{safe_sid}",
                              label_visibility="collapsed")
        if checked and sid not in selected:
            selected.add(sid)
            st.session_state[selected_key] = selected
            st.rerun()
        elif not checked and sid in selected:
            selected.discard(sid)
            st.session_state[selected_key] = selected
            st.rerun()
    with cols[1]:
        thumb = _session_thumb(session)
        if isinstance(thumb, str) and Path(thumb).exists():
            st.image(thumb, width=60)
        elif isinstance(thumb, bytes):
            st.image(thumb, width=60)
    with cols[2]:
        desc = (session.get("description") or "（无描述）")[:80]
        st.markdown(f"**{desc}**")
        st.caption(session.get("upload_time", ""))
    with cols[3]:
        tags = session.get("tags", [])
        st.caption(" · ".join(tags[:5]) if tags else "无标签")
```

### `init_state` 补充

`core/state.py` 的 `init_state()` 中新增：
```python
"batch_selected_ids": set(),
"batch_mode_gallery":  False,
"batch_mode_archived": False,
```

## 不要做

- 不要修改 `_render_card` 现有签名或行为
- 不要在此任务中改动任何 Tab 文件

## 验收清单

- [ ] `python -c "from components.cards import _render_batch_row; print('OK')"` 通过
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `docs/api/components.md` cards.py 节已追加 `_render_batch_row` 说明
- [ ] commit 符合规范（建议 `feat(cards): 新增批量行视图 _render_batch_row · 关联 #11a`）
- [ ] 在 worktree 分支提交，未 push main
