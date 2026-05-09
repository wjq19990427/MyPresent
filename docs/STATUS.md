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

- **UI 导航重组已完成** ✅（task-25~26 均合并）
- 待用户测试验收：6 Tab 结构 + 主页面板 + 记录台嵌套子 Tab

## 最近完成

- **task-25~26 merge**：新增主页组件（项目介绍 + 功能模块卡片），app.py 导航重构为 6 Tab
- **task-23~24 merge**：今日事务记录、日历日志视图、优先级文字标签
- **task-19~22 merge**：延期字段、分类动态管理、日历方格重设计、年度规划关联待办进度

## 待办 / TODO

- [ ] 技术债：`_load_month_activities` 按天循环查询，可优化为单次月查询
- [ ] 技术债：`tab_search` 跨层调用 `vector_db._get_*` 改为走公开接口
- [ ] 技术债：pending 孤儿行清理脚本
