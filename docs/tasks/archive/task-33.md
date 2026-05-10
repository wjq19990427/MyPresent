# Task #33 — 规划台「记录此刻」预填 + 跳转记录台

## 目标

在规划台完成活动记录后，出现「📝 记录此刻想法」入口；用户确认后，LLM 将当天的活动与待办完成情况组织成草稿，预填到上传表单，并跳转到记录台上传页，用户可继续扩充后调用完整 AI 分析。

**依赖**：task-30（AnalysisSkill 可用）+ task-32（导航跳转协议可用）。

## 必读契约

- `docs/api/components.md` # `tab_planning.py` 节
- `docs/api/core.md` # `state.py::_nav_target` 节 + `llm_client.py` 节
- `docs/api/skills.md` # AnalysisSkill 节

## 改动范围

- **修改**：`components/tab_planning.py`
- **修改**：`components/tab_upload.py`
- **修改**：`core/prompts.py`（新增草稿生成 prompt 常量）
- **修改**：`core/state.py`（新增 `upload_prefill` key）
- **修改**：`docs/api/core.md`（state.py 新键登记）
- **不许碰**：`skills/analysis_skill.py` 内部逻辑

## 接口约定

### session_state 新增键（state.py 登记）

| key | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `upload_prefill` | `dict \| None` | `None` | 预填数据；上传表单消费后清空 |

`upload_prefill` 的 dict 结构：
```
{
  "description": str,   # LLM 生成的草稿正文
  "topics":      list,  # 从活动分类推断的话题（可为空列表）
  "source": "planning"  # 标记来源，供上传表单展示提示语
}
```

### tab_planning.py 新增行为

活动记录保存成功后（`create_daily_activity` 调用完成），在当日活动列表下方显示提示：

「📝 记录此刻的想法？」\[去记录\]  \[不了\]

- 点「不了」：关闭提示，不做任何操作
- 点「去记录」：
  1. 调用 LLM（用 `call_llm`，非 AnalysisSkill）生成草稿：输入为当天全部 activities + 当天 todos 完成情况，prompt 常量放 `prompts.py`
  2. 将草稿写入 `st.session_state["upload_prefill"]`
  3. 设置 `st.session_state["_nav_target"] = ("📝 记录台", "⬆️ 上传")`
  4. `st.rerun()`

### tab_upload.py 新增行为

上传页渲染时检测 `upload_prefill`：
- 若存在：在表单顶部显示提示横幅「✍️ 已从今日规划预填内容，可继续扩充」；将 `description` 写入对应 widget 默认值，`topics` 写入标签区；消费后清空 `upload_prefill = None`
- 用户可直接在预填基础上扩充，之后照常调用「✨ AI 分析」（task-31 的组件）生成完整结构化字段

## 不要做

- 不要在草稿生成时调用 AnalysisSkill（草稿只是文字组织，全量分析留给用户主动触发）
- 不要在跳转时自动触发 AI 分析
- 不要把「去记录」入口做成弹窗或模态框——内联显示即可

## 验收清单

- [ ] 保存活动后「记录此刻」提示出现；点「不了」后消失，不影响其他功能
- [ ] 点「去记录」后跳转到上传页，表单 description 含当天内容草稿
- [ ] 上传页顶部出现预填提示横幅
- [ ] 用户在上传页点「✨ AI 分析」可正常调用，不因预填数据报错
- [ ] 再次进入规划台保存活动后，提示重新出现（状态不残留）
- [ ] 已同步更新 `docs/api/core.md` + `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

草稿生成用轻量 `call_llm(expect_json=False)`——只需返回一段文字，不需要结构化 JSON，避免不必要的重试开销。`upload_prefill` 的消费在 `tab_upload.py` 首次渲染时执行（读取后立即 `= None`），防止用户切换回上传页时重复预填。提示横幅建议用 `st.info`，视觉上与正常上传流程区分。
