# Task #8 — UI：灵感墙 + 已归档详情面板增加删除按钮

## 目标

在灵感墙（pending）和已归档（final）的记录详情面板中，增加「🗑️ 删除」按钮，将记录移入回收站（软删除），同时写入操作日志。

## 依赖

**必须在 task-7 合并后执行。**

## 必读契约

- `docs/api/components.md` # `cards.py` 节（`_render_detail` 的 mode / state_key 参数、do_save / do_archive 按钮的位置与行为）
- `docs/api/core.md` # `db_manager.py` 节（`soft_delete_session` / `log_operation`，task-7 新增）

## 改动范围

- **修改**：`components/cards.py`（`_render_detail` 函数）
- **不许碰**：`tab_gallery.py` / `tab_archived.py` / `core/` / `skills/`

## 实现要点

### 1. 新增 import

```python
from core.db_manager import (
    ...,          # 已有的 import
    soft_delete_session,
    log_operation,
)
```

### 2. 在 `_render_detail` 内添加删除按钮

删除按钮放在表单**外**（避免 st.form 内 button 刷新限制），紧接在主操作按钮区（归档/保存区域）的下方，用 `st.divider()` 分隔：

```python
st.divider()
if st.button("🗑️ 移入回收站", key=f"delete_btn_{safe_sid}", type="secondary"):
    soft_delete_session(sid)
    st.session_state[state_key] = None   # 关闭详情面板
    st.rerun()
```

**`state_key` 的确定**：
- `_render_detail` 已接收 `state_key` 参数（默认按 mode 推导）
- 用传入的 `state_key` 清空选中态，使面板自动关闭

**`safe_sid` 的使用**：函数内已有 `safe_sid = "".join(c if c.isalnum() else "_" for c in sid)` 净化逻辑，直接复用，不要重复定义。

### 3. 两种 mode 均需要删除按钮

- `mode == "pending"`：pending 记录可删除
- `mode == "final"`：archived 记录也可删除

删除逻辑相同，无需按 mode 分支。

## 不要做

- 不要添加二次确认弹窗（软删除可在回收站恢复，无需确认）
- 不要在删除时清理磁盘文件（软删除保留文件，purge 才清理）
- 不要修改 `_render_card`（卡片视图不加删除按钮）
- 不要修改 `do_archive` 等已有按钮逻辑

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 灵感墙：展开任意 pending 详情 → 底部出现「🗑️ 移入回收站」→ 点击 → 面板关闭 → 该记录从灵感墙消失
- [ ] 已归档：展开任意 final 详情 → 同上操作 → 记录从已归档消失
- [ ] 已删除记录在灵感墙/已归档均不再显示
- [ ] commit 符合规范（建议 `feat(cards): 详情面板增加软删除按钮 · 关联 #8`）
- [ ] 在 worktree 分支提交，未 push main
