# Task #12 — 运行看板：日志筛选条件

## 目标

为运行看板的「LLM 调用统计」和「数据操作记录」两个 section 各增加筛选控件，解决数据量大时浏览困难的问题。

## 必读契约

- `docs/api/components.md` # `eval_dashboard.py` 节（四段布局，数据来源）

## 改动范围

- **修改**：`components/eval_dashboard.py`（仅 `render_eval_dashboard` 和 `_render_operation_logs`）
- **不许碰**：`core/db_manager.py` / 其他文件（筛选在内存中做，不改 DB 查询）

## 实现要点

### 1. LLM 调用日志筛选

在现有「调用统计」section 的日志列表上方加筛选栏：

```python
st.markdown("#### 筛选")
fcol1, fcol2, fcol3 = st.columns(3)
with fcol1:
    skill_opts = sorted({r["skill_name"] for r in logs if r.get("skill_name")})
    f_skills = st.multiselect("Skill", skill_opts, key="filter_skills")
with fcol2:
    model_opts = sorted({models_map.get(r["model_id"], r["model_id"]) for r in logs if r.get("model_id")})
    f_models = st.multiselect("模型", model_opts, key="filter_models")
with fcol3:
    f_status = st.radio("状态", ["全部", "成功", "失败"], horizontal=True, key="filter_status")

# 过滤
filtered_logs = logs
if f_skills:
    filtered_logs = [r for r in filtered_logs if r.get("skill_name") in f_skills]
if f_models:
    filtered_logs = [r for r in filtered_logs
                     if models_map.get(r.get("model_id", ""), r.get("model_id", "")) in f_models]
if f_status == "成功":
    filtered_logs = [r for r in filtered_logs if r.get("success")]
elif f_status == "失败":
    filtered_logs = [r for r in filtered_logs if not r.get("success")]
```

将后续日志列表渲染改为使用 `filtered_logs` 而非 `logs`，并在列表标题处显示 `f"最近 {len(filtered_logs)} 条（共 {len(logs)} 条）"`。

### 2. 数据操作记录筛选

在 `_render_operation_logs` 中，`get_operation_logs(limit=50)` 取到数据后加筛选：

```python
op_opts = sorted({r["operation"] for r in op_logs})
f_ops = st.multiselect(
    "操作类型", op_opts,
    format_func=lambda x: op_label.get(x, x),
    key="filter_op_types",
)
if f_ops:
    op_logs = [r for r in op_logs if r["operation"] in f_ops]
st.caption(f"显示 {len(op_logs)} 条")
```

## 不要做

- 不要修改 `get_llm_logs` / `get_operation_logs` 的 DB 查询（内存过滤已足够）
- 不要新增 session_state 键到 `state.py`（filter 控件 key 由 streamlit 自管理）

## 验收清单

- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `streamlit run app.py` 启动无报错
- [ ] 运行看板：选择 Skill 筛选 → 日志列表正确过滤
- [ ] 运行看板：选「失败」→ 仅显示失败记录
- [ ] 数据操作记录：选操作类型 → 正确过滤
- [ ] 筛选条件为空时显示全量数据（行为不变）
- [ ] commit 符合规范（建议 `feat(eval_dashboard): LLM日志+操作记录筛选条件 · 关联 #12`）
- [ ] 在 worktree 分支提交，未 push main
