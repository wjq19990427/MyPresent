# Task #30 — AnalysisSkill（全量 + 局部 + hint）

## 目标

新建 `AnalysisSkill`，一次 LLM 调用分析文本并返回所有结构化字段；支持 `fields` 参数缩减输出范围（局部重生成）；支持 `hint` 参数引导 LLM 调整方向。替代主流程中 `TaggingSkill` + `CompletionSkill` 的使用。

**依赖**：task-29 先合并（需 `title` / `summary` 字段已存在）。

## 必读契约

- `docs/api/skills.md`
- `docs/api/core.md` # `prompts.py` 节 + `llm_client.py` 节

## 改动范围

- **新增**：`skills/analysis_skill.py`
- **修改**：`core/prompts.py`（新增 prompt 常量）
- **修改**：`docs/api/skills.md`
- **不许碰**：`skills/tagging_skill.py` / `skills/completion_skill.py`（保留，其他地方仍在用）
- **不许碰**：任何 `components/` 文件

## 接口约定

### `AnalysisSkill(BaseSkill).execute(session_id, model_id, *, fields="all", hint="") -> SkillResult`

- **`fields`**：
  - `"all"` → 返回所有字段
  - `list[str]` → 仅返回指定字段子集，如 `["title"]`、`["domains", "topics"]`
  - 合法字段名：`title / summary / domains / attributes / topics / emotion_tags / emotion_note / feeling / reason`
- **`hint`**：传入时追加到 prompt，引导 LLM 调整；空字符串时忽略
- **返回 `SkillResult.data`**（dict，仅含请求字段）：
  ```
  {
    title:         str,
    summary:       str,
    domains:       list[str],   # 从 label_registry type='domain' 中选
    attributes:    list[str],   # 从 label_registry type='attribute' 中选
    topics:        list[str],   # 从 label_registry type='topic' 中选
    new_topics:    list[str],   # LLM 建议新增但 registry 中没有的话题
    emotion_tags:  list[str],   # 从 label_registry type='emotion' 中选
    emotion_note:  str,
    feeling:       str,
    reason:        str,
  }
  ```
- **Prompt 设计要求**：
  - 全量模式：prompt 包含文本内容 + 四类 label_registry 现有标签列表
  - 局部模式：prompt 裁剪为仅包含所需字段对应的 registry 数据，减少 token
  - LLM 返回严格 JSON，走 `call_llm(expect_json=True)` + 自动重试
- **副作用**：写 `llm_logs`（通过 `call_llm` 自动完成）

## 不要做

- 不要在 Skill 层读取或写入 `session_state`
- 不要在 Skill 层调用 `db_manager` 的写入方法
- 不要在 Skill 内部做分支区分"上传"和"规划台"场景——调用方传参控制

## 验收清单

- [ ] `python -c "from skills.analysis_skill import AnalysisSkill"` 无报错
- [ ] `fields="all"` 时返回 dict 含全部 9 个字段
- [ ] `fields=["title"]` 时 `SkillResult.data` 仅含 `title`（不含其他字段）
- [ ] `hint="太长了"` 时 prompt 内容含该提示（可打印 prompt 验证）
- [ ] LLM 返回非 JSON 时自动重试，不崩溃
- [ ] 已同步更新 `docs/api/skills.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

局部模式裁剪 prompt 的关键：每个字段对应的 registry 数据是独立的，按 `fields` 参数只拼入相关 registry 列表即可。`new_topics` 只在 `fields` 包含 `topics` 时出现——LLM 从 registry 外建议的新话题，UI 层负责决定是否调用 `add_label` 注册。`feeling` / `reason` 不依赖 registry，局部模式请求它们时 prompt 只需文本内容即可。
