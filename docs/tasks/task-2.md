# Task #2 — 修复上传 Tab「✨ AI」按钮双重 bug

## 目标

`components/tab_upload.py` 中「✨ AI」打标按钮存在两个 bug：

1. **dict-vs-list**：`auto_tag_session()` 自 v4.0.0 重构后返回 `dict`，但上传 Tab 仍将整体 dict 赋给 multiselect 的 widget state（期望 `list[str]`），导致 multiselect 默认值无效或报错。
2. **新标签不入库**：AI 生成的 `new_tags` 从未调 `add_tag()` 注册到 `tags_registry`，其他 session 的标签下拉框看不到这些新标签。

## 必读契约

- `docs/api/components.md` # `tab_upload.py` 节（上传流程、标签必填约束、已知陷阱）
- `docs/api/skills.md` # `tagging_skill.py` 节（`auto_tag_session` 返回结构）
- `docs/api/core.md` # `db_manager.py` 中 `add_tag(name) -> None` 节

## 改动范围

- **修改**：`components/tab_upload.py`
- **不许碰**：`skills/tagging_skill.py` / `core/db_manager.py` / `components/ai_tagging.py` / `components/cards.py` / 其他文件

## 实现要点（契约级）

### 1. 补充 import（第 9 行）

```python
# 原行
from core.db_manager import get_tags_registry, validate_session
# 改为
from core.db_manager import get_tags_registry, validate_session, add_tag
```

### 2. 修复 AI 按钮回调（L195–L204）

原始代码：
```python
suggestions = auto_tag_session(
    {"description": auto_description, "feeling": ""},
    model_id=model_id,
)
if suggestions:
    st.session_state[f"upload_tags_{st.session_state.upload_key}"] = suggestions
    st.rerun()
else:
    st.warning("未能推荐到标签，请手动选择")
```

修改为：
```python
suggestions = auto_tag_session(
    {"description": auto_description, "feeling": ""},
    model_id=model_id,
)
combined = suggestions["suggested_tags"] + suggestions["new_tags"]
if combined:
    for tag in suggestions["new_tags"]:
        add_tag(tag)
    st.session_state[f"upload_tags_{st.session_state.upload_key}"] = combined
    st.rerun()
else:
    st.warning("未能推荐到标签，请手动选择")
```

### 3. 修复 help 文案（L193）

```python
# 原
help="在「搜索」Tab 选择模型后可自动推荐标签" if not ai_ready else "AI 推荐标签",
# 改为
help="在「运行看板」Tab 选择模型后可自动推荐标签" if not ai_ready else "AI 推荐标签",
```

## 执行顺序约束

`add_tag()` 调用必须在写 widget state **之前**完成，保证 rerun 后 `get_tags_registry()` 已能读到新标签。

## 不要做

- 不要改 `auto_tag_session` 函数签名或返回结构
- 不要对 `add_tag` 加 try/except（内部已 `INSERT OR IGNORE`，容错完备）
- 不要改动 upload 流程的其他逻辑（标签必填校验、归档前 `validate_session` 等）
- 不要顺手重构上传 Tab 其他部分

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 手工流程跑通：
  1. 记录舱 Tab → 上传任意文件或粘贴文字
  2. 点「✨ AI」按钮 → 等 AI 返回
  3. 验证：标签 multiselect **默认已选中** AI 推荐的标签（之前 bug 下默认值为 dict 对象，无效）
  4. 归档或暂存后，展开「⚙️ 管理标签」面板
  5. 验证：AI 新生成的标签（`new_tags`）已出现在标签列表中
- [ ] commit 信息符合 AGENTS.md 规范（建议 `fix(tab_upload): 修复 AI 按钮 dict-vs-list + 新标签不入库 · 关联 #2`）
- [ ] 在 git worktree 分支提交，未 push main

## 架构师备注

- **根因**：`auto_tag_session` 在 v4.0.0 从返回 `list[str]` 改为返回 `dict`（三字段），上传 Tab 未同步适配。`ai_tagging.py` 已正确消费 dict 结构，此处是漏网之鱼。
- **new_tags 入库**：与 task-1 同源需求——AI 生成的标签应在用户确认（此处即点击 AI 按钮时默认信任）时立即入库。上传场景用户看到推荐标签就视为认可，无需再做二次确认流程。
- **改动体量**：约 8 行，比 task-1 还小。如发现契约有遗漏或矛盾，立即停手写 `BLOCKED: <冲突点>` 反馈。
