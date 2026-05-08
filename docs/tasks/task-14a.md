# Task #14a — AI 自动补全：Prompt + CompletionSkill

## 目标

新建 `skills/completion_skill.py`，实现基于描述文本生成「感受」和「记录原因」的 AI 自动补全能力。新增对应 Prompt 到 `core/prompts.py`。

此任务是 task-14b（UI 集成）的前置依赖，本任务**不涉及任何 UI**。

## 必读契约

- `docs/api/skills.md`（`BaseSkill` / `SkillResult` 设计，`execute` 接口约定）
- `docs/api/core.md` # `prompts.py` 节（Prompt 格式约定，使用 `{变量}` 占位）
- `docs/api/core.md` # `llm_client.py` 节（`call_llm` 调用方式）

## 改动范围

- **修改**：`core/prompts.py`（追加两个常量）
- **新建**：`skills/completion_skill.py`
- **更新**：`docs/api/skills.md`（追加 `completion_skill.py` 节）
- **不许碰**：其他任何文件

## 实现要点

### 1. `core/prompts.py` 追加

```python
COMPLETION_SYSTEM = """你是一个感性、细腻的私人记录助手。
用户会提供一段记录的描述，你需要根据描述内容推断：
1. feeling：用户当时可能的内心感受（50-120字，第一人称，情感真实自然）
2. reason：用户记录这段内容的可能原因（30-80字，第一人称，简洁直接）

严格返回 JSON，格式：{"feeling": "...", "reason": "..."}
不要输出任何其他内容。"""

COMPLETION_USER_TMPL = "记录描述：\n{description}"
```

### 2. `skills/completion_skill.py`

```python
"""AI 自动补全感受与记录原因。"""
from __future__ import annotations
from .base_skill import BaseSkill, SkillResult
from core.prompts import COMPLETION_SYSTEM, COMPLETION_USER_TMPL
from core.llm_client import call_llm


class CompletionSkill(BaseSkill):

    def execute(self, session_data: dict) -> SkillResult:
        model_id    = session_data.get("model_id", "")
        description = (session_data.get("description") or "").strip()

        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")
        if not description:
            return SkillResult(success=False, error="描述为空，无法生成补全")

        user_prompt = COMPLETION_USER_TMPL.format(description=description[:800])
        try:
            result = call_llm(
                system_prompt=COMPLETION_SYSTEM,
                user_prompt=user_prompt,
                model_id=model_id,
                expect_json=True,
                skill_name="CompletionSkill",
            )
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

        if not isinstance(result, dict):
            return SkillResult(success=False, error="返回格式错误")
        feeling = result.get("feeling", "")
        reason  = result.get("reason", "")
        if not feeling:
            return SkillResult(success=False, error="feeling 字段缺失")

        return SkillResult(success=True, data={"feeling": feeling, "reason": reason})

    def run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult:
        return self.execute({**session, "model_id": model_id})
```

### 3. `docs/api/skills.md` 追加节

在文件末尾追加 `completion_skill.py` 的完整 L2 契约段（参照现有 tagging_skill.py 节的格式）：
- `execute(session_data)` 入参：`description`（必须非空）、`model_id`（必须非空）
- 返回 `SkillResult.data = {feeling: str, reason: str}`
- `feeling` 为空时返回失败

## 不要做

- 不要修改 `BaseSkill` 或 `SkillResult`
- description 截断上限 800 字（避免超出 context，已在 TMPL 格式化时截断）
- 不要添加 `auto_complete_session` 便捷函数（task-14b 直接用 `CompletionSkill().execute()`）

## 验收清单

- [ ] `python -c "from skills.completion_skill import CompletionSkill; print('OK')"` 通过
- [ ] `python -c "import app, core, skills, components"` 通过
- [ ] `docs/api/skills.md` 已追加 `completion_skill.py` 节
- [ ] commit 符合规范（建议 `feat(skills): CompletionSkill AI 感受+原因补全 · 关联 #14a`）
- [ ] 在 worktree 分支提交，未 push main
