# AI 协同开发 SOP — 新项目引导

## 角色模型

```
用户（PM）
  ├─ 提需求 / 测试 / 最终合并
Claude（架构师）
  ├─ 诊断问题 / 写任务卡 / 做 Review
  └─ 维护 STATUS.md / L2 契约文档
Codex（实现工手）
  ├─ 在独立 worktree 实现任务卡
  └─ 完成后反馈，不 push main
```

## 快速启动步骤

### 1. 复制文件到新项目根目录

```
template/CLAUDE.md       → CLAUDE.md
template/AGENTS.md       → AGENTS.md
template/docs/STATUS.md  → docs/STATUS.md
template/docs/ARCHITECTURE.md → docs/ARCHITECTURE.md
template/docs/tasks/_template.md → docs/tasks/_template.md
```

### 2. 按项目实际情况修改

- `CLAUDE.md`：调整层命名（如 `core/skills/components` 改为你的包结构）
- `AGENTS.md`：调整语言/框架相关的 smoke test 命令
- `docs/STATUS.md`：填写当前版本和核心架构
- `docs/ARCHITECTURE.md`：填写模块表和依赖关系
- `docs/api/`：为每个代码层新建 `{layer}.md` 并填写 L2 契约

### 3. 提交基线

```bash
git add CLAUDE.md AGENTS.md docs/
git commit -m "docs: AI协同开发SOP基建"
```

### 4. 开始工作流

每次新任务：
1. Claude 诊断 → 写 `docs/tasks/task-N.md`
2. Codex `git worktree add ../project-task-N -b codex/task-N` → 实现
3. 完成后 Claude review → 用户确认 → 合并

## 文档层级速查

| 层级 | 文件 | 用途 | 更新时机 |
|------|------|------|---------|
| L0 | `CLAUDE.md` / `AGENTS.md` | 角色规则，自动注入 | 工作流变化时 |
| L1 | `docs/STATUS.md` `docs/ARCHITECTURE.md` | 项目快照 / 模块索引 | 每次任务完成后 |
| L2 | `docs/api/*.md` | 模块公开 API 契约 | 改公开签名/语义时 |
| L3 | 源代码 | 实现细节 | 随代码变化 |

**原则**：改代码前先读 L2；改了公开签名就同步更新 L2；README 只写顶层和协作流程，不重复 L2 内容。
