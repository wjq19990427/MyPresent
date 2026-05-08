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

- **task-4~9 全部完成** ✅：文件夹导入优化 + AI Picker + 软删除回收站
- 已知技术债：`tab_search` 跨层调用 `vector_db._get_*`；`FIELD_SCHEMA` 增字段需手改 5 处

## 最近完成

- **task-9 merge**：回收站 Tab（恢复/永久删除/自动清理）+ 运行看板操作记录
- **task-5/6/8 merge**：文件夹扫描去重 + 记录舱完整 AI Picker + 详情面板软删除按钮
- **task-4/7 merge**：文件夹选择器+递归扫描 + 软删除DB层（12张表 + operation_logs）
- **task-2/3 merge**：AI 按钮 dict 修复 + session ID 微秒精度

## 待办 / TODO

- [ ] 技术债：`tab_search` 跨层调用 `vector_db._get_*` 改为走公开接口
- [ ] 技术债：pending 孤儿行清理脚本
