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

- **v4.1 功能已完成并测试通过** ✅
- 已知技术债：`tab_search` 跨层调用 `vector_db._get_*`；`FIELD_SCHEMA` 增字段需手改 5 处

## 最近完成

- **task-15 merge**：AI补全直接赋值修复 + 灵感墙 AI 标签，全功能测试通过
- **task-10~14b merge**：回收站预览、批量管理、看板筛选、追加模型测试、AI 感受/原因补全
- **task-4~9 merge**：文件夹导入优化、AI Picker、软删除回收站体系

## 待办 / TODO

- [ ] 技术债：`tab_search` 跨层调用 `vector_db._get_*` 改为走公开接口
- [ ] 技术债：pending 孤儿行清理脚本
