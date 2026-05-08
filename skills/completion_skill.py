"""AI 自动补全感受与记录原因。"""
from __future__ import annotations

from .base_skill import BaseSkill, SkillResult
from core.prompts import COMPLETION_SYSTEM, COMPLETION_USER_TMPL
from core.llm_client import call_llm


class CompletionSkill(BaseSkill):
    name = "CompletionSkill"
    description = "根据描述自动补全感受与记录原因"

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
