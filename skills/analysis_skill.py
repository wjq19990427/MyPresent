"""结构化分析 Skill：一次 LLM 调用返回记录的结构化字段。"""
from __future__ import annotations

import json

from core.db_manager import get_label_registry, get_session
from core.llm_client import LLMJsonParseError, call_llm
from core.prompts import ANALYSIS_SYSTEM, ANALYSIS_USER_TMPL

from .base_skill import BaseSkill, SkillResult


_ALLOWED_FIELDS = {
    "title",
    "summary",
    "domains",
    "attributes",
    "topics",
    "emotion_tags",
    "emotion_note",
    "feeling",
    "reason",
}
_ALL_FIELDS = [
    "title",
    "summary",
    "domains",
    "attributes",
    "topics",
    "emotion_tags",
    "emotion_note",
    "feeling",
    "reason",
]
_LIST_FIELDS = {"domains", "attributes", "topics", "new_topics", "emotion_tags"}
_REGISTRY_BY_FIELD = {
    "domains": ("domain", "领域标签"),
    "attributes": ("attribute", "视角属性"),
    "topics": ("topic", "主题标签"),
    "emotion_tags": ("emotion", "情绪标签"),
}
_REGISTRY_PROMPT_LIMIT = 20


class AnalysisSkill(BaseSkill):
    name = "analysis"
    description = "分析记录并返回标题、摘要、结构化标签、感受与记录原因"

    def execute(
        self,
        session_id: str,
        model_id: str,
        *,
        fields: str | list[str] = "all",
        hint: str = "",
    ) -> SkillResult:
        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")

        requested, error = _normalize_fields(fields)
        if error:
            return SkillResult(success=False, error=error)

        session = get_session(session_id)
        if not session:
            return SkillResult(success=False, error="记录不存在")

        content = _build_content(session)
        if not content:
            return SkillResult(success=False, error="记录内容为空，无法分析")

        user_prompt = _build_user_prompt(content, requested, hint)

        try:
            result = call_llm(
                ANALYSIS_SYSTEM,
                user_prompt,
                model_id=model_id,
                expect_json=True,
                skill_name=self.name,
                session_id=session_id,
            )
        except LLMJsonParseError as exc:
            return SkillResult(success=False, error=f"JSON 解析失败：{exc}")
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

        if not isinstance(result, dict):
            return SkillResult(success=False, error="返回格式错误")

        return SkillResult(success=True, data=_sanitize_result(result, requested))

    def execute_draft(
        self,
        draft: dict,
        model_id: str,
        *,
        fields: str | list[str] = "all",
        hint: str = "",
    ) -> SkillResult:
        if not model_id:
            return SkillResult(success=False, error="未指定 model_id")
        if not str(draft.get("description", "")).strip() and not _file_names(draft):
            return SkillResult(success=False, error="描述为空，无法分析")

        requested, error = _normalize_fields(fields)
        if error:
            return SkillResult(success=False, error=error)

        content = _build_content(draft)
        if not content:
            return SkillResult(success=False, error="记录内容为空，无法分析")

        user_prompt = _build_user_prompt(content, requested, hint)
        try:
            result = call_llm(
                ANALYSIS_SYSTEM,
                user_prompt,
                model_id=model_id,
                expect_json=True,
                skill_name=self.name,
            )
        except LLMJsonParseError as exc:
            return SkillResult(success=False, error=f"JSON 解析失败：{exc}")
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

        if not isinstance(result, dict):
            return SkillResult(success=False, error="返回格式错误")

        return SkillResult(success=True, data=_sanitize_result(result, requested))

    def run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult:
        session_id = str(session.get("session_id") or session.get("id") or "").strip()
        if not session_id:
            return SkillResult(success=False, error="缺少 session_id")
        return self.execute(
            session_id,
            model_id,
            fields=kwargs.get("fields", "all"),
            hint=kwargs.get("hint", ""),
        )


def _normalize_fields(fields: str | list[str]) -> tuple[list[str], str]:
    if fields == "all":
        return list(_ALL_FIELDS), ""
    if not isinstance(fields, list):
        return [], "fields 必须为 'all' 或字段名列表"

    requested = []
    invalid = []
    for field in fields:
        key = str(field).strip()
        if key not in _ALLOWED_FIELDS:
            invalid.append(key)
            continue
        if key not in requested:
            requested.append(key)

    if invalid:
        return [], f"不支持的字段：{', '.join(invalid)}"
    if not requested:
        return [], "fields 不能为空"
    return requested, ""


def _build_content(session: dict) -> str:
    lines = []
    for label, key in [
        ("标题", "title"),
        ("摘要", "summary"),
        ("内容时间", "content_time"),
        ("描述", "description"),
        ("感受", "feeling"),
        ("记录原因", "reason"),
        ("情绪说明", "emotion_note"),
    ]:
        value = str(session.get(key, "")).strip()
        if value:
            lines.append(f"{label}：{value}")
    if not lines:
        names = _file_names(session)
        if names:
            lines.append("文件名：" + "、".join(names))
    return "\n".join(lines)


def _build_user_prompt(content: str, requested: list[str], hint: str = "") -> str:
    output_fields = list(requested)
    if "topics" in requested and "new_topics" not in output_fields:
        output_fields.append("new_topics")

    registry_section = _build_registry_section(requested)
    hint = hint.strip()
    hint_section = f"\n调整提示：{hint}\n" if hint else ""

    return ANALYSIS_USER_TMPL.format(
        content=content,
        fields=json.dumps(output_fields, ensure_ascii=False),
        registry_section=registry_section,
        hint_section=hint_section,
    )


def _build_registry_section(requested: list[str]) -> str:
    parts = []
    for field in requested:
        config = _REGISTRY_BY_FIELD.get(field)
        if not config:
            continue
        _, label = config
        names = _registry_names_for_field(field)[:_REGISTRY_PROMPT_LIMIT]
        parts.append(f"- {field}（{label}）：{_format_names(names)}")
    return "\n".join(parts) if parts else "（本次请求字段不依赖标签候选）"


def _registry_names_for_field(field: str) -> list[str]:
    config = _REGISTRY_BY_FIELD.get(field)
    if not config:
        return []
    label_type, _ = config
    return [item["name"] for item in get_label_registry(label_type)]


def _format_names(names: list[str]) -> str:
    return "、".join(names) if names else "（暂无候选）"


def _sanitize_result(result: dict, requested: list[str]) -> dict:
    data = {}
    for field in requested:
        value = result.get(field, [] if field in _LIST_FIELDS else "")
        if field in _REGISTRY_BY_FIELD:
            allowed = set(_registry_names_for_field(field))
            data[field] = [item for item in _as_list(value) if item in allowed]
        elif field in _LIST_FIELDS:
            data[field] = _as_list(value)
        else:
            data[field] = str(value).strip()

    if "topics" in requested:
        data["new_topics"] = _as_list(result.get("new_topics", []))

    return data


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]


def _file_names(session: dict) -> list[str]:
    files = session.get("files", [])
    if not isinstance(files, list):
        return []
    names = []
    for file_info in files:
        if not isinstance(file_info, dict):
            continue
        name = str(
            file_info.get("original_name") or file_info.get("filename") or ""
        ).strip()
        if name:
            names.append(name)
    return names
