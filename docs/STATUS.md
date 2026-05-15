# Project Status

> 项目状态快照。每次对话先读此文件；任务完成后及时更新。保持 ≤ 50 行。

## 当前版本

`v0.6.1` · 下一里程碑：Phase 6 数据分析 / LLM 深化

## 核心架构

- **三层结构**：`core/`（基础设施）· `skills/`（LLM 插件槽）· `components/`（UI 层）
- **主库**：SQLite，local 模式 `data/database.db`，cloud 模式 `data/users/{username}/database.db`
- **向量库**：ChromaDB + `BAAI/bge-small-zh-v1.5`，per-user 隔离；`EMBEDDING_ENABLED=false` 可完全跳过加载
- **部署配置层**：`core/config.py`，双态（local / cloud），ContextVar 用户隔离，统一路径解析
- **LLM 调用层**：`core/llm_client.py` 统一入口，自动 JSON 重试 + `llm_logs` 写库
- **Skills 插件体系**：`BaseSkill(ABC)` + `SkillResult`，已落地 `TaggingSkill` / `AnalysisSkill`
- **标签体系**：L-A-T 三维（领域 / 视角 / 话题）+ 情绪，`label_registry` 统一管理
- **CI/CD**：`deploy.sh` + GitHub Actions SSH 自动部署；`infra/` 提供 Nginx + systemd 模板

## 当前焦点

- **v5.3.0 已发布** ✅（登录鉴权 + Windows 同步工具链）
- 下一阶段：Phase 6 深化续（数据分析 / LLM 深化 / 用户管理 UI）

## 最近完成

- **task-55**：系统页新增修改密码面板（cloud 已登录用户）；用户看板升级为卡片式布局，显示总数 + 管理员标识
- **task-56**：修复待办树形层级缩进失效：改用列比例分割 + CSS 竖线/L 形连接线
- **task-54**：已完成事务支持编辑（描述/分类/时间段/时长均可改，`update_daily_activity` 新增）
- **task-53**：待办升级为无限递归树形结构；勾选级联完成子树、已移入节点置灰禁交互、父节点半勾/百分比
- **v5.3.0**：多用户登录体系（users 表 + PBKDF2 密码）、admin 账户 plus7、Windows SFTP 数据同步工具链（pull_data.py + setup_sync_key.ps1）、REMOTE_DEV.md 开发指南
- **v5.2.0**：config.py 部署配置层、db/vector_db/file_io 多用户路径隔离、EMBEDDING_ENABLED 开关、CI/CD 自动部署基础设施、.gitignore 安全加固

## 待办 / TODO

- [ ] Phase 6 深化：数据分析 + LLM 深化功能
- [ ] Phase 6 深化：数据分析 + LLM 深化功能
- [ ] 技术债：`_load_month_activities` 按天循环查询，可优化为单次月查询
- [ ] 技术债：`tab_search` 跨层调用 `vector_db._get_*` 改为走公开接口
- [ ] 技术债：`_render_batch_row` 在批量模式中每行调用 `get_groups()`，可提取到外层
- [ ] 技术债：向量 embedding 从 `session_tags` 迁移到 `topics` 字段
