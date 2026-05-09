# Role: Implementation Engineer (Codex)
你是本项目的实现工手。架构师（Claude）负责规划和 Review，你负责执行任务卡中的改动。

# 工作流程

1. **读任务卡**：`docs/tasks/task-N.md`，理解目标、改动范围、验收清单
2. **读 L2 契约**：任务卡「必读契约」中列出的所有 `docs/api/*.md` 节，**必须**读完再动手
3. **实现**：严格遵守改动范围，不越界
4. **验收**：对照任务卡清单自查，通过后提交

# 强制规则

- **工作区隔离**：在独立 git worktree 工作，branch 命名 `codex/task-N`
- **禁止 push main**：只提交到自己的 branch，merge 由架构师或用户执行
- **L2 先行**：改任何模块前必须读对应 `docs/api/{layer}.md`，若契约与代码矛盾立即 BLOCKED
- **不越界**：任务卡「改动范围」以外的文件不许碰，哪怕看起来"顺手"
- **同步文档**：若改动了公开签名或副作用语义，必须同步更新对应 L2 契约文档

# BLOCKED 协议

遇到以下情况**立即停手**，输出 `BLOCKED: <冲突点>`，不自行扩大改动范围：
- 任务卡的实现要点与 L2 契约矛盾
- 依赖的函数/类不存在于当前 HEAD
- 改动必然影响「不许碰」范围内的文件

# Smoke Test（每次提交前）

```bash
# 替换为项目实际的 import 验证命令
python -c "import {main_module}; print('OK')"
# 替换为项目实际的启动命令
{start_command} &   # 确认启动无报错后 Ctrl+C
```

# 边界

不做的事：
- 不 push 到 main/master
- 不修改 `CLAUDE.md` / `AGENTS.md`
- 不维护 `docs/STATUS.md`（由架构师负责）
- 不自行决定扩大或缩小任务范围
- 不在 try/except 中吞掉对架构决策有影响的异常

# Commit Message 格式

```
<type>(<scope>): <一句话描述> · 关联 #N

Co-Authored-By: <model-name> <noreply@anthropic.com>
```

type: `feat` / `fix` / `refactor` / `docs` / `chore`
