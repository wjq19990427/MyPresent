# Task #13 — 运行看板：追加模型也走测试→确认流程

## 目标

「为已有 Provider 追加模型」当前直接调 `add_llm_model` 入库，跳过测试。改为与「新增 Provider」一致的 `_enter_draft` → 测试 → 确认流程，确保新模型 API 可用后才落库。

## 必读契约

- `docs/api/components.md` # `eval_dashboard.py` 节（配置「确认+重测」流程状态机）

## 改动范围

- **修改**：`components/eval_dashboard.py`（`_render_llm_settings` 内「追加模型」expander）
- **不许碰**：其他任何文件

## 实现要点

找到「➕ 为已有 Provider 追加模型」expander，将其按钮从直接入库改为进入草稿：

```python
with st.expander("➕ 为已有 Provider 追加模型"):
    nm_pvd  = st.selectbox(
        "所属 Provider",
        options=[p["id"] for p in providers],
        format_func=lambda pid: pvd_map.get(pid, pid),
        key="nm_pvd",
    )
    nm_name = st.text_input("模型 ID", key="nm_name", placeholder="gpt-4o-mini")
    nm_disp = st.text_input("显示名称（留空同模型 ID）", key="nm_disp", placeholder="GPT-4o Mini")
    if st.button("🧪 开始测试", key="add_mdl_btn", type="primary"):
        if nm_name and nm_pvd:
            pvd = next((p for p in providers if p["id"] == nm_pvd), None)
            if pvd:
                _enter_draft(
                    provider={**pvd, "_id": pvd["id"], "_readonly": True},
                    model={
                        "name":         nm_name.strip(),
                        "display_name": nm_disp.strip() or nm_name.strip(),
                        "provider_id":  nm_pvd,
                    },
                )
                st.rerun()
        else:
            st.warning("请填写模型 ID 并选择 Provider")
```

**关键变化**：
- 按钮文案：「添加模型」→「🧪 开始测试」
- 点击后调 `_enter_draft`（provider 为 `_readonly=True`，不更新 Provider）而非直接 `add_llm_model`
- 草稿确认阶段：`is_edit_pvd=False`，`is_edit_mdl=False`，`pvd._readonly=True`，`mdl.provider_id` 存在
- 确认时走 `add_llm_model(draft_mdl["name"], pvd_id_for_model, draft_mdl["display_name"])` 分支（已有逻辑覆盖，无需另写）

## 不要做

- 不要修改草稿确认逻辑（已有的 `_clear_draft` / 确认按钮流程不变）
- 不要动「新增 Provider + 首个模型」expander（已正确）
- 不要动编辑 Provider / 编辑模型的流程

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 运行看板 → 为已有 Provider 追加模型 → 点「🧪 开始测试」→ 出现草稿测试面板
- [ ] 测试通过 → 「✅ 确认保存」→ 模型入库，下拉选择器出现新模型
- [ ] 未测试直接确认按钮不可用（`disabled=not test_passed`）
- [ ] commit 符合规范（建议 `fix(eval_dashboard): 追加模型改为测试→确认流程 · 关联 #13`）
- [ ] 在 worktree 分支提交，未 push main
