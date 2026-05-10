# Changelog

所有版本的功能修改和更新记录。版本号格式：`主版本.次版本.补丁`。

> 历史版本（v3.0.0 及更早）已归档至 [`docs/CHANGELOG_ARCHIVE.md`](docs/CHANGELOG_ARCHIVE.md)。

---

## [Unreleased]

---

## [v5.0.0] - 2026-05-11

### 规划控制台（Phase 5 完成）

- 年度目标管理：分类 / 优先级 / 截止日期 / 状态；分类支持动态增删
- 日历待办：重复任务 / 关联年度目标 / 延期 / 完成复盘；月视图卡片展示
- 今日事务实录（daily_activities）：活动记录 + 时长统计；保存后可一键跳转记录台预填草稿
- 规划台 → 记录台联动：LLM 整合当日活动与待办生成草稿，导航跳转并预填上传表单

### L-A-T 结构化标签体系

- 新增 `label_registry` 表（领域 / 视角 / 话题 / 情绪 四维，含 `is_system` 保护）
- `sessions` 表新增 7 列：`domains / attributes / topics / emotion_tags / emotion_note / title / summary`
- 新增 `session_linked_goals` 表（session ↔ annual_goal 多对多关联）
- 标签库管理 UI：四维度 sub-tab，系统标签只读，用户标签可增删
- 已归档页三维度筛选（领域 / 话题 / 情绪），颜色区分，默认全选

### AI 分析全面升级

- 新增 `AnalysisSkill`：单次 LLM 调用返回标题、摘要、全部结构化标签、感受与记录原因；支持局部字段重生成 + 三级 hint
- 新增 `ai_analysis.py` 统一分析面板，替代旧 AI 打标 + AI 补全两组件；分析结果标签以 badge 样式展示，已有 / 新增颜色区分
- 废除 StorySkill 摘要入口，改为 `summary` 可编辑字段直接存库

### UI 全面重构

- **主页**：新增项目介绍 + 功能模块卡片面板
- **导航**：外层 6 Tab 改为 session_state 驱动，支持编程跳转（`_nav_target` 协议）；记录台内嵌 3 子 Tab
- **卡片重设计**：展示标题、用户录入时间、记录类型角标（📝/📷/🎬）、结构化标签 badge
- **分组管理升级**：已归档内新增相册格视图，支持新建 / 改名 / 删除分组、批量加入 / 移出
- 文件夹导入不再要求预选标签，直接进灵感墙

### 数据库扩展

- 总表数：11 → 18（新增 `label_registry`、`session_linked_goals`、`goal_categories`、`daily_activities`、`calendar_todos`、`annual_goals`、`operation_logs`）
- 启动时自动幂等迁移，存量数据平滑升级

### 兼容性

- 运行命令不变：`streamlit run app.py`；首次升级自动迁移，无需手动执行脚本
- 旧 `session_tags` 数据保留，`topics` 字段自动桥接向量 embedding

---

## [v4.0.0] - 2026-05-04

### 重构

- **三层架构**：将 `mypresent/` 包重构为 `core/` / `skills/` / `components/` 三层，职责更清晰
  - `core/` — 基础设施：db_manager、file_io、llm_client、vector_db、prompts、media、state、constants
  - `skills/` — LLM 插件槽：BaseSkill 抽象基类 + TaggingSkill + StorySkill
  - `components/` — UI 层：cards、forms、各 Tab、eval_dashboard
- **SQLite 替换 JSON 主库**：`data/database.db` 含 11 张规范化表（sessions、session_files、session_tags、tags_registry、groups、session_groups、edit_history、comments、llm_providers、llm_models、llm_logs），支持 WAL 模式与外键级联删除
- LLM Provider / Model 配置从 `mypresent_config.json` 迁入 SQLite
- 媒体文件目录从 `Assets/Pending|Final/` 迁移至 `data/pending|final/`
- 新增 `migrate.py` 一次性迁移脚本：JSON → SQLite + Assets/ → data/

### 新增

- **`core/llm_client.py`**：统一 LLM 调用层
  - `expect_json=True` 时自动解析 JSON，失败后追加重试提示（最多 2 次）
  - 所有调用自动写入 `llm_logs` 表（model_id、skill_name、延迟、tokens、成功/失败）
  - `call_with_config()` 保留用于新增配置测试
- **`core/prompts.py`**：集中管理所有 System Prompts（打标 / 单条故事 / 时间段叙事 / QA）
- **Skills 插件体系**
  - `skills/base_skill.py`：`BaseSkill(ABC)` + `SkillResult(success, data, error)` 数据类
  - `skills/tagging_skill.py`：实现原 `auto_tag_session` stub，调用 LLM 从注册表中推荐标签，返回 JSON 并校验
  - `skills/story_skill.py`：`run(session)` 生成单条文学化摘要（150-250 字）；`run_period(sessions, label)` 整合多条记忆生成时间段回忆录（300-500 字）
- **UI 新交互**
  - 归档详情页新增「✨ AI 摘要」展开块（基于当前选中模型生成，结果缓存于 session state）
  - 日期过滤搜索结果下方新增「✨ 生成阶段回忆录」按钮，将所有精确匹配记录整合为叙事文章
  - 上传 Tab 的「✨ AI」打标按钮改为使用当前选中的 LLM 模型（不再依赖 `MYPRESENT_API_KEY` 环境变量）
- **`components/eval_dashboard.py`**：LLM 调用看板（第 5 个 Tab「📊 运行看板」）
  - 展示总调用次数、成功率、平均/最大延迟
  - 按 Skill 分组统计
  - 最近 N 条调用日志列表

### 兼容性

- 运行命令不变：`streamlit run app.py`
- 首次运行前需执行 `python migrate.py` 完成数据迁移
- `FIELD_SCHEMA` 扩展接口不变，新增字段只改 `core/constants.py`
