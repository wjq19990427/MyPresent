# Task #41 — EmotionScoringSkill + emotion_scores 缓存表

## 目标

建立情绪强度评分的数据基础：新增 `emotion_scores` DB 表作为精准模式的持久化缓存；新建 `EmotionScoringSkill`，支持快速（频次统计）和精准（LLM 打分）两种模式，供情绪热力矩阵和洞察报告共同调用。

**可与 task-40 并行。**

## 必读契约

- `docs/api/skills.md`
- `docs/api/core.md` # db_manager.py::初始化 节 + llm_client.py 节
- `docs/api/database.md`

## 改动范围

- **新增**：`skills/emotion_scoring_skill.py`
- **修改**：`core/db_manager.py`（新增 emotion_scores 表 + CRUD）
- **修改**：`core/prompts.py`（精准模式 prompt）
- **修改**：`docs/api/skills.md`
- **修改**：`docs/api/core.md`
- **修改**：`docs/api/database.md`

## 接口约定

### emotion_scores 表（新建，init_db 中 CREATE TABLE IF NOT EXISTS）

| 列名 | 类型 | 约束 |
|---|---|---|
| `session_id` | TEXT | NOT NULL, FK → sessions(id) ON DELETE CASCADE |
| `emotion` | TEXT | NOT NULL |
| `score` | REAL | NOT NULL，范围 0.0～1.0 |
| `mode` | TEXT | NOT NULL，`'quick'` 或 `'precise'` |
| `model_id` | TEXT | default `''`，精准模式记录使用的模型 |
| `computed_at` | TEXT | NOT NULL |
| **PK** | — | `(session_id, emotion, mode)` |

### db_manager.py 新增函数

`upsert_emotion_scores(session_id: str, scores: dict[str, float], mode: str, model_id: str = '') -> None`
- 批量 `INSERT OR REPLACE` 写入 `emotion_scores`
- `scores`：`{emotion_name: score_float}`

`get_emotion_scores(session_ids: list[str], mode: str) -> dict[str, dict[str, float]]`
- 返回 `{session_id: {emotion: score}}`
- 仅返回已缓存的条目；未缓存的 session_id 不出现在结果中

`get_uncached_session_ids(session_ids: list[str], mode: str) -> list[str]`
- 返回在 `emotion_scores` 中 `mode` 对应条目缺失的 session_id 列表

### EmotionScoringSkill

`class EmotionScoringSkill(BaseSkill)`，`name = "emotion_scoring"`

#### `score_quick(sessions: list[dict]) -> dict[str, dict[str, float]]`
- **模式**：无 LLM，纯统计
- **行为**：对每条 session，读取 `emotion_tags`（list）；跨所有 session 统计每种情绪的出现频次；对每条 session 生成该 session 的情绪向量（该 session 含有的情绪 score=1.0，不含的 score=0.0）；写入 `emotion_scores(mode='quick')`
- **返回**：`{session_id: {emotion: score}}`
- **副作用**：批量调 `upsert_emotion_scores`

#### `score_precise(sessions: list[dict], model_id: str) -> dict[str, dict[str, float]]`
- **模式**：LLM 分析 `feeling + emotion_note + description`
- **行为**：
  1. 调 `get_uncached_session_ids` 找出未缓存的 session
  2. 对每条未缓存 session，调 `call_llm(expect_json=True)`，prompt 要求 LLM 返回 `{emotion: 0-1}` 的 JSON
  3. 写入 `emotion_scores(mode='precise', model_id=model_id)`
  4. 合并缓存命中 + 本次新算的结果一并返回
- **返回**：`{session_id: {emotion: score}}`，仅包含请求的 sessions
- **副作用**：写 `llm_logs`（通过 `call_llm` 自动完成）；写 `emotion_scores` 缓存
- **失败路径**：单条 session LLM 失败时静默跳过，不中断整批；返回中该 session 的 score 为已缓存值或空 dict

#### `run(session: dict, model_id: str = '', **kwargs) -> SkillResult`
- 兼容 BaseSkill；`mode=kwargs.get('mode','quick')`；单条调用

### prompts.py 新增

`EMOTION_SCORING_SYSTEM`：要求 LLM 根据文本内容，对指定情绪列表中每个情绪输出 0-1 的强度分，纯 JSON 输出，无文字。

`EMOTION_SCORING_USER_TMPL`：模板变量 `{emotions}`（候选情绪列表）、`{content}`（feeling + emotion_note + description 拼接）

## 不要做

- 不要在 `score_quick` 中调用 LLM
- 不要在 Skill 内直接读写 `sessions` 表（只读传入的 session dict）
- 不要跨 session 做归一化（每条 session 的分值独立，0-1 绝对值）

## 验收清单

- [ ] `emotion_scores` 表在 init_db 后存在，主键约束正确
- [ ] `score_quick([...])` 返回 dict，每条 session 含其 emotion_tags 的 score=1.0，其余 score 缺失（不补0）
- [ ] `score_precise` 对已缓存 session 不重复调用 LLM（`get_uncached_session_ids` 验证）
- [ ] 精准模式 LLM 失败单条时不抛异常，其他 session 正常返回
- [ ] `upsert_emotion_scores` 重复调用幂等
- [ ] 已同步更新 `docs/api/skills.md` + `docs/api/core.md` + `docs/api/database.md`
- [ ] commit message 符合 AGENTS.md 规范
- [ ] git worktree 分支 push，**未** push main

## 架构师备注

`score_quick` 中每条 session 只有含在 `emotion_tags` 里的情绪得 1.0，其余不填（sparse 表示）。热力矩阵渲染时将空值显示为 0 强度（最浅色）。精准模式 prompt 的情绪候选列表由调用方传入（从所有参与 session 的 `emotion_tags` 取并集），避免 prompt 过长。
