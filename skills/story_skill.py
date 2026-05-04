"""故事生成 Skill：单条摘要 + 时间段叙事。"""
from __future__ import annotations

from core.llm_client import call
from core.prompts import (
    STORY_SINGLE_SYSTEM, STORY_SINGLE_USER_TMPL,
    STORY_PERIOD_SYSTEM, STORY_PERIOD_USER_TMPL,
)
from .base_skill import BaseSkill, SkillResult


class StorySkill(BaseSkill):
    name        = "story"
    description = "生成单条记忆摘要或时间段回忆录"

    def run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult:
        """为单条 session 生成文学化摘要（150-250 字）。"""
        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")

        reason_section = ""
        reason = str(session.get("reason", "")).strip()
        if reason:
            reason_section = f"记录原因：{reason}\n"

        user_msg = STORY_SINGLE_USER_TMPL.format(
            content_time=str(session.get("content_time", "")).strip() or "未知时间",
            description=str(session.get("description", "")).strip() or "（无描述）",
            feeling=str(session.get("feeling", "")).strip() or "（无感受）",
            reason_section=reason_section,
        )

        try:
            text = call(
                messages=[
                    {"role": "system", "content": STORY_SINGLE_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
                model_id=model_id,
                skill_name=self.name,
                session_id=session.get("session_id", ""),
            )
            return SkillResult(success=True, data={"story": str(text).strip()})
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    def run_period(
        self,
        sessions: list[dict],
        period_label: str,
        model_id: str = "",
    ) -> SkillResult:
        """将多条 session 整合为时间段回忆录（300-500 字）。"""
        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")
        if not sessions:
            return SkillResult(success=False, error="没有可用的记忆片段")

        fragments = []
        for i, s in enumerate(sessions, 1):
            desc    = str(s.get("description", "")).strip()
            feeling = str(s.get("feeling", "")).strip()
            time    = str(s.get("content_time", "")).strip()
            if desc or feeling:
                fragments.append(
                    f"{i}. 【{time or '未知时间'}】{desc}"
                    + (f"\n   感受：{feeling}" if feeling else "")
                )

        if not fragments:
            return SkillResult(success=False, error="所选记忆均无有效内容")

        user_msg = STORY_PERIOD_USER_TMPL.format(
            period=period_label,
            memories="\n\n".join(fragments),
        )

        try:
            text = call(
                messages=[
                    {"role": "system", "content": STORY_PERIOD_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
                model_id=model_id,
                skill_name=self.name,
            )
            return SkillResult(success=True, data={"story": str(text).strip()})
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))
