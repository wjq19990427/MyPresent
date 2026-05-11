# skills/ — LLM 插件槽

> 所有 AI 能力的统一契约。新增能力 = 新增一个 `BaseSkill` 子类。

## 边界规则

- skills/ 只 import `core/`，**不得** import `components/`
- skills 之间不互相调用
- 任何 LLM 调用必须走 `core/llm_client`，禁止直接起 SDK 客户端

## Skill 清单

| 文件 | 职责 | 契约状态 |
|------|------|----------|
| `base_skill.py` | `BaseSkill(ABC)` + `SkillResult(success, data, error)` | ✅ |
| `tagging_skill.py` | 自动打标（从注册表中推荐） | ✅ |
| `analysis_skill.py` | 单次结构化分析（标题/摘要/标签/感受/原因） | ✅ |
| `story_skill.py` | 单条摘要 + 时间段叙事 | ✅ |
| `emotion_scoring_skill.py` | 情绪强度评分（快速统计 + LLM 精准评分） | ✅ |

---

## base_skill.py

> 所有 Skill 的统一契约。新增 LLM 能力 = 新增一个 `BaseSkill` 子类。

### `SkillResult`（dataclass）

| 字段 | 类型 | 默认 | 含义 |
|------|------|------|------|
| `success` | `bool` | — | 业务是否成功（**不是** LLM 调用是否成功） |
| `data` | `dict` | `{}` | 成功时的载荷；结构由各 Skill 自行定义并写入自己的 L2 节 |
| `error` | `str` | `''` | 失败原因（用户可见，需中文） |

### `BaseSkill(ABC)`

#### 类属性

- `name: str = ""` — Skill 标识，写入 `llm_logs.skill_name`，子类必须覆盖
- `description: str = ""` — 一句话描述，用于 UI 展示

#### `run(self, session: dict, **kwargs) -> SkillResult`  *(@abstractmethod)*
- **用途**：Skill 的核心入口（向后兼容签名）
- **入参**：
  - `session` (`dict`)：完整 session（结构与 `db_manager.get_session()` 返回一致）
  - `**kwargs`：Skill 特定参数（如 `model_id`、`label` 等），各 Skill 在自己的 L2 节中声明
- **返回**：`SkillResult`
- **不变量**：
  - 子类若覆盖 `execute()`，可让 `run()` 委托给它（或反之）
  - 任何 LLM 调用必须走 `core/llm_client`，禁止内部起 SDK 客户端
  - 不得直接读写数据库——通过 `core/db_manager` 公开 API
  - 异常不应外抛，转译为 `SkillResult(success=False, error=...)`

#### `execute(self, session_data: dict) -> SkillResult`
- **用途**：标准化新接口（默认委托给 `run()`）
- **入参**：仅 `session_data`，无 `**kwargs`
- **何时覆盖**：当 Skill 的参数完全由 `session_data` 决定、无需额外可配项时，子类可只实现 `execute()`
- **何时保留默认**：Skill 需要 `model_id` / `label` 等运行时参数时，仍实现 `run()`，让 `execute()` 走默认委托

### 子类实现选择

| 场景 | 推荐做法 |
|------|----------|
| 需要 `model_id` 等运行参数 | 覆盖 `run()`，保留 `execute()` 默认 |
| 全部参数由 `session_data` 提供 | 覆盖 `execute()`，让 `run()` 委托过去 |
| 同时需要单条 + 批量入口 | 仍以 `run()` 为主，新增独立方法（如 `StorySkill.run_period()`）

### 已知陷阱

- `run()` 是 `@abstractmethod`——子类**必须**实现，否则实例化时 `TypeError`。即使你只想覆盖 `execute()`，也得保留一个 `run()` 实现（哪怕是 `pass` / 委托）
- `SkillResult.success` 与 LLM 调用成功**解耦**：LLM 返回了内容但内容不合规（例如打标返回了非法标签），仍可 `success=False`

## tagging_skill.py

> 评估现有标签适配度，并生成新的情感标签。`SkillResult.data` 三字段：`suggested_tags / new_tags / reasoning`。

### `class TaggingSkill(BaseSkill)`

- `name = "tagging"` · `description = "评估现有标签适配度，并生成新的情感标签"`

#### `__init__(self, model_id: str = "") -> None`
- `model_id` 可在实例级固定，也可在调用时通过 `session_data["model_id"]` 覆盖

#### `execute(self, session_data: dict) -> SkillResult`
- **入参（按需 dict 字段）**：
  - `text_content` 或 `description`（至少一项非空，否则失败）
  - `feeling`（选填）
  - `model_id`（选填，覆盖实例级）
  - `session_id`（选填，用于 `llm_logs` 关联）
- **返回**：`SkillResult.data` 结构
  ```
  {
    "suggested_tags": list[str],   # 已过滤，仅保留 tags_registry 中存在的
    "new_tags":       list[str],   # LLM 新生成（已 strip 空值）
    "reasoning":      str,
  }
  ```
- **副作用**：调 `core/llm_client.call_llm`（自动写 `llm_logs`，`skill_name="tagging"`）；读 `tags_registry`
- **失败路径**（不抛异常，转 `SkillResult(success=False, error=...)`）：
  - 缺 `model_id` / 文本与感受全空 / JSON 解析失败 / `suggested_tags`/`new_tags` 不是 list
- **不变量**：`suggested_tags` 必为注册表子集；非注册表条目静默丢弃

#### `run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult`
- 向后兼容：浅拷贝 `session` 后注入 `model_id`，委托给 `execute()`

### 模块级辅助

#### `auto_tag_session(session: dict, model_id: str = "") -> dict`
- **用途**：UI 层直接调用的简化接口（替代旧 stub）
- **返回**：始终是 `{suggested_tags, new_tags, reasoning}` dict（**不**返回 `SkillResult`）
- **失败时**：三字段空 dict，`reasoning` 字段装错误信息
- **`model_id` 为空**：直接返回三字段空 dict，不调 LLM

### Prompt 依赖

- `core/prompts.TAGGING_SYSTEM` / `TAGGING_USER_TMPL`（变量 `{content}`）
- 改 prompt 必须同步检查输出字段名（`suggested_tags / new_tags / reasoning`）

## analysis_skill.py

> 单次 LLM 调用分析一条记录，返回标题、摘要、结构化标签、情绪说明、感受与记录原因；支持局部字段重生成和 hint 引导。

### `class AnalysisSkill(BaseSkill)`

- `name = "analysis"` · `description = "分析记录并返回标题、摘要、结构化标签、感受与记录原因"`

#### `execute(self, session_id: str, model_id: str, *, fields="all", hint="") -> SkillResult`

- **入参**：
  - `session_id`：目标记录 ID；内部调用 `db_manager.get_session()` 读取完整 session
  - `model_id`：必填，传给 `core.llm_client.call_llm`
  - `fields`：`"all"` 或字段名列表；合法字段为 `title / summary / domains / attributes / topics / emotion_tags / emotion_note / feeling / reason`
  - `hint`：可选调整提示；非空时追加进 user prompt
- **返回**：`SkillResult.data` 仅包含请求字段；当请求包含 `topics` 时额外包含 `new_topics`
  ```
  {
    "title": str,
    "summary": str,
    "domains": list[str],
    "attributes": list[str],
    "topics": list[str],
    "new_topics": list[str],
    "emotion_tags": list[str],
    "emotion_note": str,
    "feeling": str,
    "reason": str,
  }
  ```
- **局部模式**：只拼入请求字段依赖的 registry 数据；`feeling / reason / title / summary / emotion_note` 不拼 registry
- **副作用**：调 `core.llm_client.call_llm(expect_json=True)`，自动写 `llm_logs`；只读 `sessions` 和 `label_registry`，不写 DB
- **失败路径**（不抛异常，转 `SkillResult(success=False, error=...)`）：缺 `model_id` / 缺 `session_id` / 记录不存在 / 内容为空 / 非法 `fields` / LLM 调用或 JSON 解析失败

#### `execute_draft(self, draft: dict, model_id: str, *, fields="all", hint="") -> SkillResult`

- **用途**：上传流程保存前的草稿分析；不需要 `session_id`
- **入参**：`draft` 为当前上传表单或详情页当前 UI 草稿；通常含 `description`，若文字字段为空但 `files[].original_name/filename` 存在，则用文件名作为内容兜底；`fields` / `hint` 与 `execute()` 一致
- **返回**：同 `execute()`，`SkillResult.data` 仅包含请求字段；请求 `topics` 时额外含 `new_topics`
- **副作用**：调 `core.llm_client.call_llm(expect_json=True)`，自动写 `llm_logs`；读 `label_registry`；不读写 `sessions`
- **失败路径**：缺 `model_id` / 文本字段与文件名均为空 / 非法 `fields` / LLM 调用或 JSON 解析失败

#### `run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult`

- **用途**：兼容 `BaseSkill.run()`；从 `session["session_id"]` 或 `session["id"]` 取 ID 后委托 `execute()`
- **kwargs**：透传 `fields` / `hint`

### Prompt 依赖

- `core/prompts.ANALYSIS_SYSTEM` / `ANALYSIS_USER_TMPL`（变量 `{content}` `{fields}` `{registry_section}` `{hint_section}`）
- 改 prompt 必须同步检查输出字段名和 `AnalysisSkill._sanitize_result()` 的字段过滤逻辑
- `registry_section` 每个 label type 最多拼入前 20 条候选（沿用 `get_label_registry()` 的 `is_system DESC, name ASC` 顺序），避免标签库增大导致 prompt 线性膨胀

## story_skill.py

> 单条记忆 → 文学化摘要（150-250 字），或多条 → 时间段回忆录（300-500 字）。

### `class StorySkill(BaseSkill)`

- `name = "story"` · `description = "生成单条记忆摘要或时间段回忆录"`
- 不需要 `__init__` 参数（`model_id` 在调用时传入）

#### `run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult`
- **用途**：单条 session → 文学化摘要
- **入参**：
  - `session`：完整 session dict（用 `content_time / description / feeling / reason / session_id`）
  - `model_id`（必填）
- **返回**：`SkillResult.data = {"story": str}`（已 strip）
- **副作用**：调 `core/llm_client.call`（**非** JSON 模式，纯文本）；自动写 `llm_logs`
- **失败路径**：缺 `model_id` 或 LLM 调用异常 → `success=False`
- **不变量**：缺字段以「未知时间 / （无描述） / （无感受）」占位，不报错

#### `run_period(self, sessions: list[dict], period_label: str, model_id: str = "") -> SkillResult`
- **用途**：多条 session → 时间段回忆录
- **入参**：
  - `sessions`：session list；过滤掉 `description` 与 `feeling` 都为空的条目
  - `period_label`：时间段标签字符串（如 `"2026-04 ~ 2026-05"`），用户自定义
  - `model_id`（必填）
- **返回**：`SkillResult.data = {"story": str}`
- **失败路径**：缺 `model_id` / `sessions` 空 / 全部条目无有效内容
- **副作用**：写 `llm_logs`（**注意**：`session_id` 留空，因为是聚合调用）

### Prompt 依赖

- `STORY_SINGLE_SYSTEM` / `STORY_SINGLE_USER_TMPL`：`{content_time, description, feeling, reason_section}`
- `STORY_PERIOD_SYSTEM` / `STORY_PERIOD_USER_TMPL`：`{period, memories}`
- 全部位于 `core/prompts.py`

## emotion_scoring_skill.py

> 为情绪热力矩阵和洞察报告生成 `{session_id: {emotion: score}}` 情绪强度数据。

### `class EmotionScoringSkill(BaseSkill)`

- `name = "emotion_scoring"` · `description = "生成记录的情绪强度评分"`

#### `score_quick(self, sessions: list[dict]) -> dict[str, dict[str, float]]`

- **用途**：无 LLM 的快速评分
- **入参**：session list；仅读取传入 dict 的 `session_id/id` 与 `emotion_tags`
- **返回**：`{session_id: {emotion: 1.0}}`；仅包含该 session 实际命中的情绪，未命中情绪不填
- **副作用**：批量调用 `db_manager.upsert_emotion_scores(..., mode="quick")`
- **不变量**：不调用 LLM；不直接读取 `sessions` 表；不跨 session 归一化

#### `score_precise(self, sessions: list[dict], model_id: str) -> dict[str, dict[str, float]]`

- **用途**：LLM 精准情绪强度评分，带 DB 缓存
- **入参**：session list；候选情绪来自所有传入 session 的 `emotion_tags` 并集；`model_id` 传给 `call_llm`
- **返回**：`{session_id: {emotion: score}}`，仅包含请求的 session；单条失败时该 session 返回已缓存值或空 dict
- **副作用**：
  - 读 `db_manager.get_emotion_scores()` / `get_uncached_session_ids()`
  - 对未缓存 session 调 `core.llm_client.call_llm(expect_json=True)`，自动写 `llm_logs`
  - 写 `db_manager.upsert_emotion_scores(..., mode="precise", model_id=model_id)`
- **失败路径**：单条 LLM 调用或 JSON 解析失败时静默跳过该 session，不中断整批
- **不变量**：不直接读取 `sessions` 表；不跨 session 归一化；分数 clamp 到 `0.0..1.0`

#### `run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult`

- **用途**：兼容 `BaseSkill.run()` 的单条入口
- **kwargs**：`mode` 默认为 `"quick"`，可传 `"precise"`
- **返回**：`SkillResult.data = {emotion: score}`

### Prompt 依赖

- `core/prompts.EMOTION_SCORING_SYSTEM` / `EMOTION_SCORING_USER_TMPL`（变量 `{emotions}` `{content}`）

## completion_skill.py

> 根据记录描述自动补全「感受」与「记录原因」。`SkillResult.data` 两字段：`feeling / reason`。

### `class CompletionSkill(BaseSkill)`

- `name = "CompletionSkill"` · `description = "根据描述自动补全感受与记录原因"`

#### `execute(self, session_data: dict) -> SkillResult`
- **入参（必填 dict 字段）**：
  - `description`：记录描述，必须非空；调用 LLM 前截断到 800 字
  - `model_id`：模型 ID，必须非空
- **返回**：`SkillResult.data` 结构
  ```
  {
    "feeling": str,
    "reason":  str,
  }
  ```
- **副作用**：调 `core/llm_client.call_llm`（JSON 模式，自动写 `llm_logs`，`skill_name="CompletionSkill"`）
- **失败路径**（不抛异常，转 `SkillResult(success=False, error=...)`）：
  - 缺 `model_id` / `description` 为空 / LLM 调用异常 / 返回非 dict / `feeling` 为空
- **不变量**：`feeling` 为空时必须返回失败；`reason` 可为空字符串

#### `run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult`
- 向后兼容：浅拷贝 `session` 后注入 `model_id`，委托给 `execute()`

### Prompt 依赖

- `core/prompts.COMPLETION_SYSTEM` / `COMPLETION_USER_TMPL`（变量 `{description}`）
- 改 prompt 必须同步检查输出字段名（`feeling / reason`）
