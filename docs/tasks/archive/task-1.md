# Task #1 — AI 应用标签时立即入库

## 目标

详情视图中用户点「✅ 应用选中标签到编辑栏」时，AI 新生成且不在 `tags_registry` 的标签应**立即**入库（不再等保存时再注册），让标签管理面板与其他记录的多选下拉框立刻可见。

## 必读契约

- `docs/api/components.md` # `ai_tagging.py` 节（重点：副作用、键空间约定、已知陷阱）
- `docs/api/components.md` # `cards.py` 节（保存路径的标签注册行为，理解 belt-and-suspenders 关系）
- `docs/api/core.md` # `db_manager.py` 中 `add_tag(name) -> None` 节

## 改动范围

- **修改**：`components/ai_tagging.py`
- **修改**：`docs/api/components.md`（同步更新 `ai_tagging.py` 节的「副作用」与「已知陷阱」）
- **不许碰**：`skills/tagging_skill.py` / `core/db_manager.py` / `components/cards.py` / 其他业务文件

## 实现要点（契约级）

1. 在 `render_ai_tag_picker()` 内，「✅ 应用选中标签到编辑栏」按钮点击时：
   - 在写入 `st.session_state[applied_key] = updated` 之前，调 `core.db_manager.get_tags_registry()` 拿当前注册表
   - 对 `updated` 中**不在**注册表的每个 tag，调 `core.db_manager.add_tag(tag)`
   - `add_tag` 内部已是 `INSERT OR IGNORE`，无需自行去重或 try/except
2. 执行顺序：注册新标签 → 写 `applied_key` → `del apply_key` → `st.rerun()`。这样 rerun 后 `cards._render_detail` 调 `get_tags_registry()` 时已能读到新标签
3. import 风格遵循文件现有约定（已有 `from skills.tagging_skill import auto_tag_session`，新增 `from core.db_manager import add_tag, get_tags_registry`）

## 不要做

- 不要修改 `cards._render_detail` 中现有的 `for t in selected_tags: ... add_tag(t)` 循环——它作为 belt-and-suspenders 保留，**且**兼职捕获 session 历史中残留的非注册表标签
- 不要顺手优化打标 prompt 或 Skill 输出格式
- 不要碰 `components/tab_upload.py` 的「✨ AI」按钮（独立 bug，task-2 处理）
- 不要在 ai_tagging.py 内 `try/except` 包 `add_tag`——内部已容错
- 不要重构 `_ai_tag_*` 键空间命名

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 手工流程跑通（端到端验证）：
  1. 灵感墙或已归档 → 选一条记录 → 展开「✨ 让AI帮我选标签」
  2. 点「🤖 开始分析」→ 等 AI 返回
  3. 至少勾选一个「AI 新生成的情感标签」（即标签库中不存在的）
  4. 点「✅ 应用选中标签到编辑栏」
  5. **不要点保存**，直接展开「⚙️ 管理标签」面板
  6. 验证：刚才勾选的 AI 新标签已出现在管理面板的标签列表中
- [ ] 验证下拉传播：在另一条 session 详情里打开标签 multiselect，新标签出现在选项中
- [ ] `docs/api/components.md` 的 `ai_tagging.py` 节已同步：
  - 「副作用」节追加「调 `add_tag()` 把 `updated` 中不在 registry 的标签写入 `tags_registry`」
  - 「已知陷阱」节中「AI 新生成的标签**不**在此组件入库；用户在详情表单点保存时由 `cards._render_detail` 触发 `add_tag`」一句改为：「应用按钮按下时即调 `add_tag` 入库；`cards._render_detail` 的入库循环作为 belt-and-suspenders 兼职捕获 session 历史孤儿标签」
- [ ] commit 信息符合 AGENTS.md 规范（建议 `feat(ai_tagging): apply 时同步入库新标签 · 关联 #1`）
- [ ] 在 git worktree 分支 push，未 push main

## 架构师备注

- **本任务是协作流程首张试跑卡**，刻意选最小改动范围（单文件 ~5-8 行 + L2 文档同步）
- 旧设计「等保存才入库」是 v4.0.0 初版决策，实际使用暴露 UX 缺陷（管理面板看不到刚生成的标签）。本次修正让行为更符合直觉
- 修改契约范畴：本次只改公开**副作用语义**，不改函数签名——L2 文档对应只更新两段文字
- **如发现实现中 contract 有遗漏或矛盾**：立即停手写 `BLOCKED: <冲突点>` 反馈，**不要**自行扩大改动范围
- 本任务**不修**：上传 Tab「✨ AI」按钮的双重 bug（dict-vs-list + 不入库），已记入 STATUS.md「下一步任务卡」候选
