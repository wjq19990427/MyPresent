# Project Status

> 项目状态快照。每次对话先读此文件；任务完成后及时更新。保持 ≤ 50 行。

## 当前版本

`v5.1.0`（已发布）· 下一里程碑：Phase 6

## 核心架构

- **三层结构**：`core/`（基础设施）· `skills/`（LLM 插件槽）· `components/`（UI 层）
- **主库**：SQLite `data/database.db`，18 张规范化表，WAL 模式，外键级联
- **向量库**：ChromaDB + `BAAI/bge-small-zh-v1.5`，本地持久化
- **LLM 调用层**：`core/llm_client.py` 统一入口，自动 JSON 重试 + `llm_logs` 写库
- **Skills 插件体系**：`BaseSkill(ABC)` + `SkillResult`，已落地 `TaggingSkill` / `AnalysisSkill`
- **标签体系**：L-A-T 三维（领域 / 视角 / 话题）+ 情绪，`label_registry` 统一管理
- **媒体目录**：`data/pending|final/`；导航协议：`_nav_target` session_state 驱动跨 Tab 跳转

## 当前焦点

- **v5.1.0 已发布** ✅（洞见模块 + 规划台优化 + 远程访问支持）
- Cloudflare Tunnel 配置中（待用户完成 DNS 切换）
- 下一阶段：Phase 6（数据分析 + LLM 深化）

## 最近完成

- **v5.1.0**：情绪热力矩阵、洞察报告、规划台多项优化、密码门 + Cloudflare Tunnel 准备
- **task-38~39.5 merge**：规划台优化、标签体系改进、时长统计
- **task-40~44 merge**：洞见 Tab、EmotionScoringSkill、热力矩阵、InsightReportSkill、报告 UI、待办预填

## 待办 / TODO

- [ ] 技术债：`_load_month_activities` 按天循环查询，可优化为单次月查询
- [ ] 技术债：`tab_search` 跨层调用 `vector_db._get_*` 改为走公开接口
- [ ] 技术债：`_render_batch_row` 在批量模式中每行调用 `get_groups()`，可提取到外层
- [ ] 技术债：向量 embedding 从 `session_tags` 迁移到 `topics` 字段
