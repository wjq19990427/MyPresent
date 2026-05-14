# Task #43 — InsightReportSkill + 洞察报告 UI

## 目标

新建 `InsightReportSkill`，分段生成个人洞察报告（情绪画像 / 话题聚焦 / 行为规律 / 目标追踪 / 代表语录）；在「🪞 洞见」的「📋 洞察报告」sub-tab 中实现报告 UI，支持分段按需触发和局部重生成。

**依赖**：task-40（洞见 Tab 结构）+ task-41（EmotionScoringSkill，报告的情绪段依赖其输出）均已合并。与 task-42 可并行。

## 必读契约

- `docs/api/skills.md`
- `docs/api/core.md` # prompts.py 节 + llm_client.py 节
- `docs/api/components.md` # tab_insight.py 节

## 改动范围

- **新增**：`skills/insight_report_skill.py`
- **修改**：`core/prompts.py`（新增报告各段 prompt 常量）
- **修改**：`components/tab_insight.py`（填充「洞察报告」sub-tab，替换占位内容）
- **修改**：`docs/api/skills.md`
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/components.md`

## 接口约定

### InsightReportSkill

`class InsightReportSkill(BaseSkill)`，`name = "insight_report"`

#### `execute(self, sessions: list[dict], stats: dict, period_label: str, model_id: str, *, sections: list[str] | str = "all") -> SkillResult`

- **`sessions`**：已过滤的 session dict 列表（由 UI 层准备）
- **`stats`**：预计算统计数据（由 UI 层传入，Skill 不做统计计算），结构：
  ```
  {
    "emotion_scores": {session_id: {emotion: score}},  # 来自 EmotionScoringSkill
    "emotion_freq": {emotion: count},                   # 情绪出现频次
    "topic_freq": {topic: count},                       # 话题出现频次
    "domain_freq": {domain: count},                     # 领域出现频次
    "record_dates": [date_str, ...],                    # 所有有效日期列表
    "linked_goal_ids": [goal_id, ...],                  # 涉及的年度目标 id
  }
  ```
- **`period_label`**：报告时间段描述，如 `"2026年4月"` / `"2026年第17周"`
- **`sections`**：`"all"` 或 `["emotions", "topics", "patterns", "goals", "quotes"]` 的子集
- **返回 `SkillResult.data`**：
  ```
  {
    "emotions":  str | None,   # 情绪画像段落
    "topics":    str | None,   # 话题聚焦段落
    "patterns":  str | None,   # 行为规律段落
    "goals":     str | None,   # 目标追踪段落（无关联目标时为 None）
    "quotes":    list[str],    # 代表性语录（1-3条）
  }
  ```
- **副作用**：每个 section 独立调 `call_llm`，写 `llm_logs`；不写 DB；单段失败不影响其他段
- **失败路径**：某段 LLM 失败时该段返回 `None`，`SkillResult.success` 仍为 True（部分成功）；所有段全部失败才返回 `success=False`

#### 各段 LLM 输入设计（prompt 要求）

| 段 | 主要输入 | 期望输出 |
|---|---|---|
| `emotions` | emotion_freq top5 + emotion_scores 时序摘要 | 100-150字，第一人称，描述情绪特征与变化 |
| `topics` | topic_freq top5 + 相关 session 的 description 片段（随机抽 5 条） | 100-150字，描述关注焦点 |
| `patterns` | record_dates 分布（按星期几、按时段） | 80-120字，描述记录习惯与行为规律 |
| `goals` | linked_goal 标题 + 关联 session 数量 | 80-120字，描述目标推进情况；无目标时跳过 |
| `quotes` | 随机抽 15 条 session 的 feeling / description 片段 | 返回 JSON 数组，1-3条最有代表性的原文句子 |

### prompts.py 新增常量

- `INSIGHT_REPORT_SYSTEM`：通用 system prompt，说明角色（私人成长分析助手）、输出风格（第一人称、真实、克制）
- `INSIGHT_EMOTIONS_TMPL`、`INSIGHT_TOPICS_TMPL`、`INSIGHT_PATTERNS_TMPL`、`INSIGHT_GOALS_TMPL`、`INSIGHT_QUOTES_TMPL`：各段 user prompt 模板

### 洞察报告 UI（tab_insight.py）

**控制区**（独立于情绪趋势，可共享时间范围选择的 session_state 键）：
- 时间范围选择（同情绪趋势，复用 `insight_date_start` / `insight_date_end`）
- 评分模式选择（快速/精准，决定传给 Skill 的 emotion_scores 来源）
- 「📋 一键生成全部」按钮

**报告区**（五个折叠卡片，`st.expander`）：
- 每个 section 一个 expander，标题含图标（🌈 情绪画像 / 🗺️ 话题聚焦 / 🔄 行为规律 / 🎯 目标追踪 / 💬 代表语录）
- expander 内：生成的文本内容 + 「↺ 重新生成」按钮
- 未生成时显示「点击右上角「生成」按钮生成本段内容」提示
- 每段独立可触发（单段「生成」按钮 + spinner）
- 报告内容缓存在 `session_state`（key = `_insight_report_{section}`），切换时间范围后自动清空

**stats 预计算**：UI 层在调用 Skill 前完成所有统计计算，组装 `stats` dict 传入 Skill。

## 不要做

- 不要在 Skill 内部直接调用 `load_db()` 或任何 DB 函数（Skill 只接收已过滤好的 sessions 和 stats）
- 不要持久化报告内容到 DB（session_state 内存缓存即可）
- 不要在单段失败时让整个 `execute()` 报错

## 验收清单

- [ ] 「洞察报告」sub-tab 不再显示占位，显示控制区 + 五个折叠段落
- [ ] 「一键生成全部」触发所有段（顺序调用，每段完成后逐个展示）
- [ ] 单独点击某段「生成」只触发该段，其他段不变
- [ ] 「↺ 重新生成」只重新调用该段 LLM，其余缓存不清空
- [ ] 切换时间范围后所有已生成内容清空
- [ ] 无关联目标时「目标追踪」段不渲染（或显示「本时段无关联目标记录」）
- [ ] 「代表语录」以引用块或高亮样式展示
- [ ] 已同步更新 `docs/api/skills.md` + `docs/api/core.md` + `docs/api/components.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`quotes` 段要求 LLM 从原文中选句，应使用 `expect_json=True` 返回数组，避免 LLM 自行创作。`patterns` 段的 record_dates 分析：UI 预处理时把日期列表转为「星期几分布」和「时间段分布（早/午/晚）」统计字典传入，而非把原始日期全部塞进 prompt。情绪趋势与洞察报告两个 sub-tab 可共享 `insight_date_start` / `insight_date_end` 两个 session_state 键，切换 sub-tab 时时间范围保持不变，减少用户重复操作。
