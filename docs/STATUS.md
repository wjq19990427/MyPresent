# Project Status

> 项目状态快照。每次对话先读此文件；任务完成后及时更新。保持 ≤ 50 行。

## 当前版本

`v4.0.0`（已发布）· 下一里程碑：`[Unreleased]`

## 核心架构

- **三层结构**：`core/`（基础设施）· `skills/`（LLM 插件槽）· `components/`（UI 层）
- **主库**：SQLite `data/database.db`，12 张规范化表，WAL 模式，外键级联
- **向量库**：ChromaDB + `BAAI/bge-small-zh-v1.5`，本地持久化
- **LLM 调用层**：`core/llm_client.py` 统一入口，自动 JSON 重试 + `llm_logs` 写库
- **Skills 插件体系**：`BaseSkill(ABC)` + `SkillResult`，已落地 `TaggingSkill` / `StorySkill`
- **Provider/Model 配置**：从 JSON 迁入 SQLite，新增配置走「测试 → 确认」流程
- **媒体目录**：`data/pending|final/`（已脱离 `Assets/`）

## 当前焦点

- **task-1 已派发**：`docs/tasks/task-1.md` — AI 应用标签时立即入库（首次试跑 Codex 协作流程）
- 待 Codex 实现 → 架构师 Review → 你 merge
- 下一步任务卡候选：tab_upload 「✨ AI」按钮双重 bug（dict-vs-list + 不入库）
- 已知技术债：`tab_search` 跨层调用 `vector_db._get_*`；pending 孤儿行无清理脚本；`FIELD_SCHEMA` 增字段需手改 5 处

## 最近完成

- README 激进瘦身：463 → 145 行，删除模块详解 / API 参考 / 数据文件说明 / 扩展开发指南（与 `docs/api/*` 重复段），新增「协作工作流」「给开发者」两节
- Codex 员工化：`AGENTS.md`（修订 4 处偏差）+ `docs/tasks/_template.md`，约定 worktree + 禁 push main
- L2 契约首轮全量回填：`database.md`(11 表) / `core.md`(8 文件) / `skills.md`(3 类) / `components.md`(8 组件)

## 待办 / TODO

- [ ] 
