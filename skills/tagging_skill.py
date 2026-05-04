"""自动打标 Skill：调用 LLM 为 session 推荐标签。"""
from __future__ import annotations

from core.db_manager import get_tags_registry
from core.llm_client import call
from core.prompts import TAGGING_SYSTEM, TAGGING_USER_TMPL
from .base_skill import BaseSkill, SkillResult


class TaggingSkill(BaseSkill):
    name        = "tagging"
    description = "基于 description / feeling 字段自动推荐标签"

    def run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult:
        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")

        description = str(session.get("description", "")).strip()
        feeling     = str(session.get("feeling", "")).strip()
        if not description and not feeling:
            return SkillResult(success=False, error="description 和 feeling 均为空")

        registry = get_tags_registry()
        user_msg = TAGGING_USER_TMPL.format(
            description=description or "（无）",
            feeling=feeling or "（无）",
            registry="、".join(registry) if registry else "（无预设标签）",
        )

        try:
            result = call(
                messages=[
                    {"role": "system", "content": TAGGING_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
                model_id=model_id,
                expect_json=True,
                skill_name=self.name,
                session_id=session.get("session_id", ""),
            )
            tags = result.get("tags", [])
            if not isinstance(tags, list):
                return SkillResult(success=False, error="返回格式错误：tags 不是列表")
            # 只返回注册表中存在的标签
            valid_tags = [t for t in tags if t in registry]
            return SkillResult(success=True, data={"tags": valid_tags})
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))


def auto_tag_session(session: dict, model_id: str = "") -> list[str]:
    """简化接口，供 UI 直接调用。"""
    if not model_id:
        return []
    result = TaggingSkill().run(session, model_id=model_id)
    return result.data.get("tags", []) if result.success else []
