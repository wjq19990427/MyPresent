# MyPresent 🎁

> "只要一直在记录思考和当下的状态，以及一些生活琐碎，就是在好好生活。"

**MyPresent** 是一个专注于生活化记录、思考归档与智能辅助的个人 Agent。它不仅是一个代码仓库，更是一种生活理念的数字载体，旨在帮助我们更好地梳理自我，并传递有价值的经验。

### 💡 为什么叫 MyPresent？

"Present" 在这个项目中蕴含着三层递进的含义：

* **记录当下 (The Present):** 捕捉当下的状态与闪动的思绪。从个人角度而言，记录的意义在完成的那一刻便已基本达成——在这个过程中，我们系统地整理了大脑中的碎片，完成了一次深度的自我总结与反思。
* **珍惜馈赠 (The Gift of Today):** 告诫自己活在当下，珍惜今日，因为此时此刻的经历本身就是上天最好的馈赠。
* **赠予他人 (The Present for You):** 记录的进阶意义在于"利他"。我希望将自己在这些经历中的思考、成长与避坑经验，作为一份礼物，赠予所有需要帮助的人。

### 🚀 项目愿景

在快节奏的生活中，我们留下了无数零散的随笔、备忘录、照片和视频。MyPresent 致力于通过自动化的数据清洗和人工智能技术，将这些非结构化的生活碎片进行标签化、结构化管理，构建一个完全私有化的语义知识库。

它不仅是一个存放记忆的"数据库"，更是一个能读懂你情绪、帮你串联回忆的"第二大脑"。

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

**首次运行 / 数据迁移（从旧版本升级）**

```bash
# 如果你有旧版本的 pending_db.json / mypresent_config.json / Assets/，先执行迁移：
python migrate.py
```

迁移脚本会自动将数据导入 SQLite、文件复制到 `data/`，并将旧 JSON 重命名为 `.bak` 备份。全新安装可跳过此步骤。

**启动应用**

```bash
streamlit run app.py
```

浏览器访问 `http://localhost:8501`。

**环境要求**

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| Streamlit | 1.33+ |
| opencv-python | 4.x |
| Pillow | 10.x+ |
| chromadb | 0.5+ |
| sentence-transformers | 3.0+ |
| openai | 1.x+ |

**配置 LLM（AI 功能）**

在应用的「📊 运行看板」Tab 中，通过「管理 LLM 配置」面板添加 Provider（API 地址 + Key）和 Model，无需修改配置文件或环境变量。添加后即可使用「✨ AI 推荐标签」、「✨ AI 摘要」、「✨ 生成阶段回忆录」等功能。

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
| **Phase 4 · 当前** | ✅ 完成 | AI 全面协同：AI 打标 / 感受补全 / 摘要；软删除回收站；批量管理；文件夹导入优化；操作审计日志 |
| **Phase 5** | 🔜 规划中 | **个人规划与目标管理**：目标制定 / 追踪 / 阶段复盘；规划表模板；与记录库深度关联（以过去的记录为基础生成个人 OKR 建议） |
| **Phase 6** | 🔜 规划中 | **LLM 能力深化 & 数据分析**：Prompt 精调与多模型评测；情绪 / 主题趋势分析；个人洞察报告生成；数据采集流程自动化 |

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
