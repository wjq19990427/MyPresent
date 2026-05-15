"""自动打标 Skill：评估四维结构化标签适配度，并按需生成新标签。"""
from __future__ import annotations

from core.db_manager import get_label_registry
from core.llm_client import call_llm, LLMJsonParseError
from core.prompts import TAGGING_SYSTEM, TAGGING_USER_TMPL
from .base_skill import BaseSkill, SkillResult


_FIELDS = ("domains", "attributes", "topics", "emotion_tags")
_LABEL_TYPES = {
    "domains": "domain",
    "attributes": "attribute",
    "topics": "topic",
    "emotion_tags": "emotion",
}


class TaggingSkill(BaseSkill):
    name        = "tagging"
    description = "评估四维结构化标签适配度，并按需生成新标签"

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
            "suggested":  {"domains": [], "attributes": [], "topics": [], "emotion_tags": []},
            "new_labels": {"domains": [], "attributes": [], "topics": [], "emotion_tags": []},
            "reasoning":  "...",
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

        registries = _label_registries()
        parts = []
        if text_content:
            parts.append(f"描述：{text_content}")
        if feeling:
            parts.append(f"感受：{feeling}")
        user_prompt = TAGGING_USER_TMPL.format(
            domains=_format_labels(registries["domains"]),
            attributes=_format_labels(registries["attributes"]),
            topics=_format_labels(registries["topics"]),
            emotion_tags=_format_labels(registries["emotion_tags"]),
            content="\n".join(parts),
        )

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
        suggested_raw = result.get("suggested", {})
        new_raw = result.get("new_labels", {})
        reasoning = result.get("reasoning", "")

        if not isinstance(suggested_raw, dict) or not isinstance(new_raw, dict):
            return SkillResult(success=False, error="返回格式错误：标签字段不是对象")

        suggested = _empty_tag_map()
        new_labels = _empty_tag_map()
        for field in _FIELDS:
            raw_suggested = suggested_raw.get(field, [])
            raw_new = new_raw.get(field, [])
            if not isinstance(raw_suggested, list) or not isinstance(raw_new, list):
                return SkillResult(success=False, error="返回格式错误：维度字段不是列表")
            registry = set(registries[field])
            suggested[field] = [
                item for item in _clean_tags(raw_suggested) if item in registry
            ][:3]
            new_labels[field] = _clean_tags(raw_new)[:1]

        return SkillResult(
            success=True,
            data={
                "suggested": suggested,
                "new_labels": new_labels,
                "reasoning": str(reasoning),
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
    """供 UI 层直接调用。返回四维标签建议结构。"""
    if not model_id:
        return _empty_result()
    result = TaggingSkill(model_id=model_id).execute(session)
    if result.success:
        return result.data
    data = _empty_result()
    data["reasoning"] = result.error
    return data


def _label_registries() -> dict[str, list[str]]:
    return {
        field: [item["name"] for item in get_label_registry(label_type)]
        for field, label_type in _LABEL_TYPES.items()
    }


def _format_labels(labels: list[str]) -> str:
    return "、".join(labels) if labels else "（暂无）"


def _empty_tag_map() -> dict[str, list[str]]:
    return {field: [] for field in _FIELDS}


def _empty_result() -> dict:
    return {"suggested": _empty_tag_map(), "new_labels": _empty_tag_map(), "reasoning": ""}


def _clean_tags(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [
        str(item).strip()
        for item in items
        if item is not None and str(item).strip()
    ]


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
        print(f"✅ 推荐已有标签：{result.data['suggested']}")
        print(f"✨ AI 新生成标签：{result.data['new_labels']}")
        print(f"💬 推荐理由：{result.data['reasoning']}")
    else:
        print(f"❌ 打标失败：{result.error}")
