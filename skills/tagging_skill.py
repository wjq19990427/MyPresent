"""自动打标 Skill：评估现有标签适配度，并生成新的情感标签。"""
from __future__ import annotations

from core.db_manager import get_tags_registry
from core.llm_client import call_llm, LLMJsonParseError
from core.prompts import TAGGING_SYSTEM, TAGGING_USER_TMPL
from .base_skill import BaseSkill, SkillResult


class TaggingSkill(BaseSkill):
    name        = "tagging"
    description = "评估现有标签适配度，并生成新的情感标签"

    def __init__(self, model_id: str = "") -> None:
        self.model_id = model_id

    # ── 主入口（新式接口） ──────────────────────────────────────────────────────

    def execute(self, session_data: dict) -> SkillResult:
        """标准化调用接口。

        session_data 可包含：
          - text_content / description：记录正文（至少一项非空）
          - feeling：感受描述（选填）
          - model_id：覆盖实例级 model_id（选填）
          - session_id：用于 llm_logs（选填）

        返回的 SkillResult.data 结构：
          {
            "suggested_tags": [...],   # 来自注册表，已过滤
            "new_tags":       [...],   # LLM 新生成的情感标签
            "reasoning":      "...",
          }
        """
        model_id = session_data.get("model_id") or self.model_id
        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")

        # 提取文本内容
        text_content = (
            str(session_data.get("text_content") or session_data.get("description", ""))
        ).strip()
        feeling = str(session_data.get("feeling", "")).strip()

        if not text_content and not feeling:
            return SkillResult(success=False, error="记录内容为空，无法进行打标")

        # 组装 content 字符串传入模板
        registry = get_tags_registry()
        parts = []
        if text_content:
            parts.append(f"描述：{text_content}")
        if feeling:
            parts.append(f"感受：{feeling}")
        parts.append(
            f"可用标签列表：{'、'.join(registry) if registry else '（暂无预设标签）'}"
        )
        user_prompt = TAGGING_USER_TMPL.format(content="\n".join(parts))

        # 调用 LLM
        try:
            result = call_llm(
                TAGGING_SYSTEM,
                user_prompt,
                model_id=model_id,
                expect_json=True,
                skill_name=self.name,
                session_id=session_data.get("session_id", ""),
            )
        except LLMJsonParseError as exc:
            return SkillResult(success=False, error=f"JSON 解析失败：{exc}")
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

        # 解析与校验
        suggested = result.get("suggested_tags", [])
        new_tags  = result.get("new_tags", [])
        reasoning = result.get("reasoning", "")

        if not isinstance(suggested, list) or not isinstance(new_tags, list):
            return SkillResult(success=False, error="返回格式错误：字段不是列表")

        # suggested_tags 只保留注册表中存在的条目
        valid_suggested = [t for t in suggested if t in registry]

        return SkillResult(
            success=True,
            data={
                "suggested_tags": valid_suggested,
                "new_tags":       [str(t).strip() for t in new_tags if str(t).strip()],
                "reasoning":      str(reasoning),
            },
        )

    # ── 向后兼容接口 ────────────────────────────────────────────────────────────

    def run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult:
        """兼容旧调用方式，内部委托给 execute()。"""
        data = dict(session)
        if model_id:
            data["model_id"] = model_id
        return self.execute(data)


# ── 简化的 UI 调用接口 ──────────────────────────────────────────────────────────

def auto_tag_session(session: dict, model_id: str = "") -> dict:
    """供 UI 层直接调用。返回 {suggested_tags, new_tags, reasoning}。"""
    if not model_id:
        return {"suggested_tags": [], "new_tags": [], "reasoning": ""}
    result = TaggingSkill(model_id=model_id).execute(session)
    if result.success:
        return result.data
    return {"suggested_tags": [], "new_tags": [], "reasoning": result.error}


# ── 本地测试 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import sys

    model_id = os.environ.get("TEST_MODEL_ID", "")
    if not model_id:
        print("请先设置环境变量 TEST_MODEL_ID，例如：")
        print("  PowerShell: $env:TEST_MODEL_ID = 'your-model-id'")
        print("  bash:       export TEST_MODEL_ID='your-model-id'")
        sys.exit(1)

    test_data = {
        "text_content": (
            "今天骑车去了郊外，路过一片金黄的麦田。风吹过来，有一种莫名的安心感。"
            "突然想起小时候外婆家的夏天，那时候总是无忧无虑的。"
            "不知道从什么时候开始，我开始害怕失去那些美好的时刻。"
        ),
        "feeling":    "平静中带着一点淡淡的忧郁",
        "model_id":   model_id,
        "session_id": "test_001",
    }

    print("=" * 60)
    print("输入内容：")
    print(f"  描述：{test_data['text_content']}")
    print(f"  感受：{test_data['feeling']}")
    print("=" * 60)

    skill  = TaggingSkill(model_id=model_id)
    result = skill.execute(test_data)

    if result.success:
        print(f"✅ 推荐已有标签：{result.data['suggested_tags']}")
        print(f"✨ AI 新生成标签：{result.data['new_tags']}")
        print(f"💬 推荐理由：{result.data['reasoning']}")
    else:
        print(f"❌ 打标失败：{result.error}")
