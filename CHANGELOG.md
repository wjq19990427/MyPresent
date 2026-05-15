# Changelog

所有版本的功能修改和更新记录。版本号格式：`主版本.次版本.补丁`。

> 历史版本（v3.0.0 及更早）已归档至 [`docs/CHANGELOG_ARCHIVE.md`](docs/CHANGELOG_ARCHIVE.md)。

---

## [Unreleased]

### Bug修复
- 规划台日历切换月份不再触发待办迁移，迁移改由真实系统时钟驱动（`tab_planning.py` · #bug1）

---

## [v5.3.0] - 2026-05-15

### 登录鉴权 + Windows 开发者同步工具链（Phase 6 深化）

- **多用户登录体系**：全局认证库 `data/database.db` 仅保留 `users` 表；业务数据迁移至 `data/users/{username}/`；`core/db_manager` 新增 `init_global_db()` / `verify_user()` / `get_user_is_admin()`；`core/config` 新增 `get_global_db_path()`
- **登录页**：`app.py` 将单密码门替换为用户名 + 密码表单；cloud 模式必须登录，local 模式直接放行；密码使用 PBKDF2-SHA256（20 万次迭代）存储
- **admin 账户**：初始管理员 `plus7` 已写入，`is_admin=1`
- **Windows 数据同步**：`scripts/pull_data.py`（Python + paramiko，无需额外工具）实现备份 → SFTP 下载 → SQLite integrity_check → 原子替换的安全拉取；`scripts/setup_sync_key.ps1` 生成专用只读 SSH 密钥并输出服务器 `authorized_keys` 配置行
- **开发指南**：新增 `REMOTE_DEV.md`，覆盖 Windows 首次配置、日常流程、安全机制说明

---

## [v5.2.0] - 2026-05-14

### 云部署基础设施（Phase 6 启动）

- **`core/config.py`**：新建部署配置入口，读取 `DEPLOY_MODE`（local / cloud）；提供基于 `ContextVar` 的线程隔离用户上下文（`set_current_user` / `get_current_user`）及四条动态路径函数（`get_db_path` / `get_vector_db_dir` / `get_pending_dir` / `get_final_dir`）
- **数据库多用户隔离**：`db_manager._conn()` 与 `init_db()` 改为通过 `config` 动态解析路径；cloud 模式下每位用户拥有独立 SQLite 文件（`data/users/{username}/database.db`），首次写入自动创建目录
- **向量库与媒体目录隔离**：`vector_db._get_collection()` 拆为两层，底层 `_get_collection_for_user(username)` 以 username 为 `@st.cache_resource` cache key，不同用户向量库物理隔离；`file_io` 所有路径调用统一通过 `config` 解析
- **Embedding 功能开关**：新增 `EMBEDDING_ENABLED` 环境变量（缺省 true）；设为 false 时向量模型与 ChromaDB 完全不加载，搜索页降级展示提示，`app.py` 启动不触发索引
- **OOM 防御**：cloud 模式下若启用本地 Embedding 模型，启动时展示醒目警告
- **CI/CD 自动部署**：新增 `deploy.sh`（备份 → 拉代码 → 更新依赖 → 重启服务，含 7 天备份清理）；`.github/workflows/deploy.yml` 在 push main 时通过 SSH 触发；`infra/` 提供 systemd 服务单元模板与含 WebSocket 支持的 Nginx 配置模板
- **安全加固**：`.gitignore` 补全 `Assets/` `backups/` `.env` `*.db` 等条目，防止用户数据进入 Git 历史

---

## [v5.1.0] - 2026-05-12

### 远程访问支持

- **密码门**：在 `app.py` 顶部新增访问密码验证；通过 `.streamlit/secrets.toml` 配置密码，未配置时跳过验证（本地开发模式）；配置后外网访问须输入密码方可进入
- **Cloudflare Tunnel 准备**：`server.address` 绑定至 `127.0.0.1`，Streamlit 不再监听外网端口，所有外网流量须经 Cloudflare Tunnel 转发，提升安全性
- 新增 `.streamlit/secrets.toml.example` 作为密码配置模板；`secrets.toml` 已加入 `.gitignore`，不纳入版本控制

### 洞见模块（原「探索」）

- 顶层 Tab「🔍 探索」更名为「🪞 洞见」，内部拆为三个子页：检索 / 情绪趋势 / 洞察报告
- **情绪趋势热力矩阵**：基于 plotly 渲染情绪 × 时间周期的热力矩阵；每种情绪固定颜色，色深表示强度；支持周/月/年粒度切换；点击单元格或使用下钻选择器查看该时段对应记录
- **情绪强度评分**：新增 `EmotionScoringSkill`，支持快速（频次统计）和精准（LLM 逐条打分）两种模式，精准模式结果缓存至新增的 `emotion_scores` 表
- **洞察报告**：新增 `InsightReportSkill`，一键生成五个维度的个人分析段落（情绪画像 / 话题聚焦 / 行为规律 / 目标追踪 / 代表语录）；各段独立生成，支持局部重新生成；内容缓存于 session_state，切换时间范围自动失效

### 规划台优化

- 日历视图调为默认入口，年度规划移至第二子页
- 待办支持内联编辑（点击「编辑」展开与新建相同字段的表单）
- 事务记录支持开始/结束时间（30 分钟刻度下拉 + 自定义输入），填写后自动计算时长
- 完成待办后自动展开事务记录表单并预填描述，方便连续记录
- 过期未完成的单次待办在切换至当月时自动迁移，并累计 `postponed_months` 字段
- 今日事务列表和月历下方新增时长统计（今日分类汇总 + 月度折叠面板）
- 「记录此刻想法」入口收拢至事务列表底部，移除其他触发点

### 其他

- 上传页导引文字与当前 Tab 名称统一（移除「灵感墙」「记录舱」等旧称）
- 数据库新增 `emotion_scores` 表（第 19 张表）

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
