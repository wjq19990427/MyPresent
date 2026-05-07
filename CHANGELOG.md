# Changelog

所有版本的功能修改和更新记录。版本号格式：`主版本.次版本.补丁`。

> 历史版本（v3.0.0 及更早）已归档至 [`docs/CHANGELOG_ARCHIVE.md`](docs/CHANGELOG_ARCHIVE.md)。

---

## [Unreleased]

- 文档分层与 Codex 协作基建：`docs/ARCHITECTURE.md` + `docs/api/*` 全量 L2 契约 + `AGENTS.md` 实现工手册 + 任务卡模板。
- README 重构：删除与 `docs/api/*` 重复的模块详解 / API 参考段，新增「协作工作流」与「给开发者」两节。
- 修正 v4.0.0 中「12 张表」笔误（实际 11 张）。

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
