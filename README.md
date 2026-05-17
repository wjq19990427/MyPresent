# MyPresent 🎁

> "只要一直在记录思考和当下的状态，以及一些生活琐碎，就是在好好生活。"

**MyPresent** 是一个为个人而生的生命记录与自我对话工具。
它要解决的，是一件听起来简单但其实很难的事——**如何让你在多年之后，依然能清晰地看见你自己**。

我们每天都在产生大量的"碎片"：随手写下的几句话、拍过的照片、闪过的念头、深夜里翻涌的情绪。这些碎片散落在手机、笔记本、聊天记录里，绝大多数最终被遗忘。但其中藏着真正的你——你怎样思考、为什么样的事情动容、走过怎样的破碎与重组。

MyPresent 想做的，是为这些碎片提供一个温柔的容器，让积累变得可以持续，并在合适的时候，帮你重新看见你自己。

### 💡 为什么是 "Present"

这个词藏着三层意思——一层比一层走得远。

**当下的捕捉（The Present）**
你坐下来写一段文字、拍一张照片、记一段心情的那个瞬间。**记录的意义，从你打下第一行字的那一刻就已经开始兑现**——你正在把混沌的情绪和念头落到纸上，让它变得可被看见、可被理解。这本身就是一次温柔的自我整理。

**时间的馈赠（The Gift of Time）**
当你坚持了一个月、一年、三年，那些散落的记录会慢慢累积成你独有的精神地形图。某一天你回头去看，会发现自己早已不是从前的那个人——你经历过怎样的事、说过怎样的话、为什么样的人停留过。**那些你以为已经忘记的，其实都还在**。这是时间送给坚持记录的人的礼物。

**献给未来自己的礼物（A Present to Future You）**
当 AI 读完你所有的记录、再回过头告诉你——你是怎样的人、走过怎样的路、身上有哪些自己都没注意到的光——**那一刻，所有过去的记录都化作一份你写给未来自己的情书**。这是 MyPresent 最想守护的瞬间：让你被自己看见。

### 🌱 项目理念

每个人都值得被认真看待，包括被自己。

MyPresent 不替你思考，只让你看清你思考过什么。
它不替你生活，只让那些被你认真活过的瞬间——**留得下、找得到、说得出**。

如果它能在某个深夜里，让一个被生活的忙碌冲散注意力的人，重新认识一下自己，那就是这个项目最大的价值。

---

## 目录

- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [协作工作流](#协作工作流)
- [给开发者](#给开发者)
- [Roadmap](#roadmap)

---

## 快速开始

**安装依赖**

```bash
pip install -r requirements.txt
# 国内镜像加速：
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**首次运行 / 旧版本数据迁移（v3 及更早 → v4+）**

```bash
# 如果你有旧版本的 pending_db.json / mypresent_config.json / Assets/，先执行：
python migrate.py
```

迁移脚本会自动将数据导入 SQLite、文件复制到 `data/`，并将旧 JSON 重命名为 `.bak` 备份。全新安装或 v4+ 升级可跳过此步骤。

**版本升级（v4 / v5 用户）**

数据库 Schema 变更已内置于启动流程，直接运行应用即可自动完成迁移。如需手动执行或验证，可使用对应的补丁脚本：

```bash
# 查看可用补丁
ls patches/

# 示例：从 v5.0.0 升级到 v5.1.0
python patches/patch_v5.1.0.py
```

详见 [`patches/README.md`](patches/README.md)。

**启动应用**

```bash
# 本地访问
python -m streamlit run app.py

# 远程访问（需已配置 Cloudflare Tunnel）
start.bat
```

浏览器访问 `http://localhost:8501`（本地）或你的自定义域名（远程）。

**环境要求**

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| Streamlit | 1.33+ |
| plotly | 5.20+ |
| opencv-python | 4.x |
| Pillow | 10.x+ |
| chromadb | 0.5+ |
| sentence-transformers | 3.0+ |
| openai | 1.x+ |

**配置 LLM（AI 功能）**

在应用的「⚙️ 系统」Tab 中，通过「管理 LLM 配置」面板添加 Provider（API 地址 + Key）和 Model，无需修改配置文件或环境变量。

**配置远程访问密码（可选）**

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 编辑 secrets.toml，填入访问密码
```

未配置时本地直接访问，配置后外网访问须输入密码。配合 Cloudflare Tunnel 实现远程访问，详见 [`patches/README.md`](patches/README.md) 中的部署说明。

---

## 项目结构

```
MyPresent/
├── CLAUDE.md                # 架构师（Claude）员工手册
├── AGENTS.md                # 实现工（Codex）员工手册
├── app.py                   # 薄启动入口
├── core/                    # 基础设施（DB / LLM / 向量库 / IO / 媒体 / 状态 / 常量）
├── skills/                  # LLM 能力插件（BaseSkill + 各 Skill）
├── components/              # Streamlit UI 层
├── data/                    # SQLite 主库 + 媒体文件（gitignored）
├── vector_db/               # ChromaDB 持久化（gitignored）
├── docs/
│   ├── STATUS.md            # 项目当前状态（每次开工先读，≤ 50 行）
│   ├── ARCHITECTURE.md      # L1 架构索引
│   ├── api/                 # L2 模块契约（按需加载）
│   │   ├── core.md
│   │   ├── skills.md
│   │   ├── components.md
│   │   ├── database.md
│   │   └── _TEMPLATE.md     # API 契约填写模板
│   ├── tasks/
│   │   └── _template.md     # 任务卡模板
│   └── CHANGELOG_ARCHIVE.md # v3.0.0 及更早历史
├── migrate.py               # 一次性迁移脚本（旧版 JSON → SQLite）
├── CHANGELOG.md
└── requirements.txt
```

**分层依赖**：`components/` → `skills/` → `core/`，反向即架构违规。完整依赖图见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 协作工作流

本项目采用 **AI 双员制** 开发，三方分工：

| 角色 | 工具 | 职责 | 配置 |
|------|------|------|------|
| **架构师** | Claude (Claude Code) | 设计、规划、Code Review、维护 L2 契约 | [`CLAUDE.md`](CLAUDE.md) |
| **实现工** | Codex (Codex CLI) | 按任务卡实现代码、跑烟测、提交分支 | [`AGENTS.md`](AGENTS.md) |
| **项目经理** | 你 | 给目标、决策、审 merge、用 git 控权 | — |

### 流程

```
你 给目标
  ↓
架构师 读 STATUS + 相关 L2 契约 → 写任务卡 docs/tasks/task-N.md
  ↓
你 把任务卡路径交给实现工
  ↓
实现工 在 git worktree 分支实现 → push 分支
  ↓
架构师 对照 L2 契约做 Code Review
  ↓
通过 → 你 merge；不过 → 架构师写补充任务卡返工
```

### 关键约定

- **L2 先行**：改 `core/` `skills/` `components/` 任何文件前必读 `docs/api/{layer}.md`（CLAUDE.md 规则 5 / AGENTS.md 上岗前必读 5）
- **契约同步**：公开 API 变化必须在同一提交同步更新对应 `docs/api/*.md`
- **Worktree 隔离**：实现工在独立 worktree 工作，禁止 push main
- **状态快照**：`docs/STATUS.md` 由架构师按任务进展维护，单文件 ≤ 50 行
- **并行执行设计**：架构师输出一批任务卡时，须附 Wave 并行执行指南，标注哪些任务可同时开 worktree（核心文件集不重叠）、哪些必须串行；指南格式见 `CLAUDE.md`

任务卡填写见 [`docs/tasks/_template.md`](docs/tasks/_template.md)。

---

## 给开发者

详细开发文档已分层组织，按需读：

| 想做什么 | 读哪里 |
|----------|--------|
| 了解项目当前状态、焦点、技术债 | [`docs/STATUS.md`](docs/STATUS.md) |
| 看分层架构与依赖方向 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 找某个函数 / Skill / 组件的契约 | [`docs/api/`](docs/api/) |
| SQLite 表结构（12 张表） | [`docs/api/database.md`](docs/api/database.md) |
| 新增字段 / 新增 Skill / 替换向量库 | 对应 `docs/api/*.md` 的「扩展规则」节 |
| 历史版本（v1-v3） | [`docs/CHANGELOG_ARCHIVE.md`](docs/CHANGELOG_ARCHIVE.md) |

### 速记

**新增 Skill**（详见 [`docs/api/skills.md`](docs/api/skills.md)）：

1. 在 `core/prompts.py` 加 prompt 常量
2. 在 `skills/` 下继承 `BaseSkill`，实现 `run()` / `execute()`
3. 在 `components/` 调用，结果缓存到 `st.session_state`

**新增 `FIELD_SCHEMA` 字段**（详见 [`docs/api/core.md`](docs/api/core.md) 的 `constants.py` 节）：

⚠️ 不止改 `FIELD_SCHEMA`——SQLite schema、`db_manager` 的字段抽取共有 5 处需改，是当前架构最大紧耦合点。

---

## Roadmap

| Phase | 状态 | 核心交付 |
|-------|------|---------|
| **Phase 1** | ✅ 完成 | 基础上传（文件 / 文字 / 文件夹）、归档、灵感墙、评论区、编辑历史 |
| **Phase 2** | ✅ 完成 | ChromaDB 向量库、日期过滤、语义检索、智能问答、标签 / 分组管理 |
| **Phase 3** | ✅ 完成 | SQLite 重构（12 张规范化表）、Skills 插件体系、统一 LLM 调用层、评估看板 |
| **Phase 4** | ✅ 完成 | AI 全面协同：AI 打标 / 感受补全 / 摘要；软删除回收站；批量管理；文件夹导入优化；操作审计日志 |
| **Phase 5** | ✅ 完成 | **个人规划与目标管理 + AI 分析重构 + 洞见模块**（v5.0–v5.1）：年度目标 / 日历待办 / 今日事务；L-A-T 结构化标签；AnalysisSkill 统一分析；情绪热力矩阵；个人洞察报告；UI 全面升级；Cloudflare Tunnel 远程访问 |
| **Phase 6 · 当前** | 🔜 规划中 | **LLM 能力深化 & 数据分析**：Prompt 精调与多模型评测；情绪主题趋势深化；个人洞察报告增强；数据采集流程自动化 |

### Phase 5 展开：个人规划与目标管理

> 目标是让 MyPresent 从"记录工具"进化为"成长引擎"——用过去的记录推导未来的方向。

- **目标制定**：创建目标卡（短期 / 中期 / 长期），关联标签与分组
- **规划表**：周计划 / 月计划模板，可拆解为可勾选的行动项
- **进度追踪**：目标完成度可视化，支持里程碑节点
- **AI 辅助**：基于已有记录分析个人习惯，给出目标制定建议；阶段结束后自动生成复盘摘要
- **记录关联**：将具体记录"绑定"到目标，形成成长轨迹

### Phase 6 展开：LLM 能力深化 & 数据分析

> 让 AI 从"辅助工具"升级为"真正读懂你的伙伴"。

- **多模型对比**：同一任务多模型并行调用，评分与偏好记录
- **Prompt 优化**：A/B 测试不同 Prompt 策略，沉淀最优配置
- **情绪趋势分析**：以时间轴展示情绪变化曲线，识别高频主题
- **个人洞察报告**：按周 / 月 / 年自动生成文字报告（"这段时间你最常感到……"）
- **数据采集自动化**：接入外部数据源（日历、健身记录等），丰富上下文
