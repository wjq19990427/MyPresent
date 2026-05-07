# Project Status

> 项目状态快照。每次对话先读此文件；任务完成后及时更新。保持 ≤ 50 行。

## 当前版本

`v4.0.0`（已发布）· 下一里程碑：`[Unreleased]`

## 核心架构

- **三层结构**：`core/`（基础设施）· `skills/`（LLM 插件槽）· `components/`（UI 层）
- **主库**：SQLite `data/database.db`，11 张规范化表，WAL 模式，外键级联
- **向量库**：ChromaDB + `BAAI/bge-small-zh-v1.5`，本地持久化
- **LLM 调用层**：`core/llm_client.py` 统一入口，自动 JSON 重试 + `llm_logs` 写库
- **Skills 插件体系**：`BaseSkill(ABC)` + `SkillResult`，已落地 `TaggingSkill` / `StorySkill`
- **Provider/Model 配置**：从 JSON 迁入 SQLite，新增配置走「测试 → 确认」流程
- **媒体目录**：`data/pending|final/`（已脱离 `Assets/`）

## 当前焦点

- **AI 双员制首次完整跑通** ✅（task-1 派发 → Codex 实现 → Review → merge）
- 下一步任务卡候选：`tab_upload` 「✨ AI」按钮双重 bug（`dict-vs-list` + 不入库）
- 工作树残留：`app.py`（标题）/ `eval_dashboard.py`（看板扩展）/ `tab_search.py`（大改动）待 commit
- 已知技术债：`tab_search` 跨层调用 `vector_db._get_*`；pending 孤儿行无清理脚本；`FIELD_SCHEMA` 增字段需手改 5 处

## 最近完成

- **task-1 merge**（e863bd4）：`ai_tagging.py` apply 时即入库，L2 契约同步
- README 瘦身（463→182 行）+ AGENTS.md + 任务卡模板，AI 双员制基建完成
- L2 契约首轮全量回填：`database.md`(11 表) / `core.md`(8 文件) / `skills.md`(3 类) / `components.md`(8 组件)

## 待办 / TODO

- [ ] 
