"""洞察报告 Skill：基于 UI 预计算数据分段生成报告。"""
from __future__ import annotations

import json
import random
from collections.abc import Iterable

from core.llm_client import LLMJsonParseError, call_llm
from core.prompts import (
    INSIGHT_EMOTIONS_TMPL,
    INSIGHT_GOALS_TMPL,
    INSIGHT_PATTERNS_TMPL,
    INSIGHT_QUOTES_TMPL,
    INSIGHT_REPORT_SYSTEM,
    INSIGHT_TOPICS_TMPL,
)

from .base_skill import BaseSkill, SkillResult


_ALL_SECTIONS = ["emotions", "topics", "patterns", "goals", "quotes"]
_TEXT_SECTIONS = {"emotions", "topics", "patterns", "goals"}


class InsightReportSkill(BaseSkill):
    name = "insight_report"
    description = "分段生成个人洞察报告"

    def execute(
        self,
        sessions: list[dict],
        stats: dict,
        period_label: str,
        model_id: str,
        *,
        sections: list[str] | str = "all",
    ) -> SkillResult:
        if not model_id:
            return SkillResult(success=False, data=_empty_data(), error="未指定 model_id")

        requested, error = _normalize_sections(sections)
        if error:
            return SkillResult(success=False, data=_empty_data(), error=error)
        if not sessions:
            return SkillResult(success=False, data=_empty_data(), error="没有可用于生成报告的记录")

        data = _empty_data()
        attempted = 0
        failed = 0

        for section in requested:
            if section == "goals" and not _has_goal_data(stats):
                data["goals"] = None
                continue

            attempted += 1
            try:
                if section == "quotes":
                    quote_candidates = _sample_quote_candidates(sessions, 15)
                    raw = call_llm(
                        INSIGHT_REPORT_SYSTEM,
                        _quotes_prompt(quote_candidates, period_label),
                        model_id=model_id,
                        expect_json=True,
                        skill_name=self.name,
                        session_id="",
                    )
                    quotes = _sanitize_quotes(raw, quote_candidates)
                    if not quotes:
                        raise ValueError("代表语录为空")
                    data["quotes"] = quotes
                else:
                    prompt = _section_prompt(section, sessions, stats, period_label)
                    text = call_llm(
                        INSIGHT_REPORT_SYSTEM,
                        prompt,
                        model_id=model_id,
                        expect_json=False,
                        skill_name=self.name,
                        session_id="",
                    )
                    text = str(text).strip()
                    if not text:
                        raise ValueError("报告段落为空")
                    data[section] = text
            except (LLMJsonParseError, Exception):
                failed += 1
                if section == "quotes":
                    data["quotes"] = []
                elif section in _TEXT_SECTIONS:
                    data[section] = None

        if attempted and failed >= attempted:
            return SkillResult(success=False, data=data, error="洞察报告生成失败")
        return SkillResult(success=True, data=data)

    def run(self, session: dict, **kwargs) -> SkillResult:
        return SkillResult(
            success=False,
            data=_empty_data(),
            error="InsightReportSkill 请使用 execute(sessions, stats, period_label, model_id, sections=...) 调用",
        )


def _empty_data() -> dict:
    return {
        "emotions": None,
        "topics": None,
        "patterns": None,
        "goals": None,
        "quotes": [],
    }


def _normalize_sections(sections: list[str] | str) -> tuple[list[str], str]:
    if sections == "all":
        return list(_ALL_SECTIONS), ""
    if not isinstance(sections, list):
        return [], "sections 必须为 'all' 或字段名列表"

    requested = []
    invalid = []
    for section in sections:
        key = str(section).strip()
        if key not in _ALL_SECTIONS:
            invalid.append(key)
            continue
        if key not in requested:
            requested.append(key)

    if invalid:
        return [], f"不支持的报告段：{', '.join(invalid)}"
    if not requested:
        return [], "sections 不能为空"
    return requested, ""


def _section_prompt(section: str, sessions: list[dict], stats: dict, period_label: str) -> str:
    if section == "emotions":
        return INSIGHT_EMOTIONS_TMPL.format(
            period_label=period_label,
            emotion_freq=_format_mapping(_top_items(stats.get("emotion_freq", {}), 5)),
            emotion_timeline=_format_emotion_timeline(stats.get("emotion_scores", {})),
        )
    if section == "topics":
        return INSIGHT_TOPICS_TMPL.format(
            period_label=period_label,
            topic_freq=_format_mapping(_top_items(stats.get("topic_freq", {}), 5)),
            domain_freq=_format_mapping(_top_items(stats.get("domain_freq", {}), 5)),
            snippets=_format_lines(_sample_snippets(sessions, 5)),
        )
    if section == "patterns":
        return INSIGHT_PATTERNS_TMPL.format(
            period_label=period_label,
            record_count=len(stats.get("record_dates", [])),
            weekday_freq=_format_mapping(stats.get("weekday_freq", {})),
            time_bucket_freq=_format_mapping(stats.get("time_bucket_freq", {})),
        )
    if section == "goals":
        return INSIGHT_GOALS_TMPL.format(
            period_label=period_label,
            goal_summary=_format_goal_summary(stats),
        )
    raise ValueError(f"不支持的报告段：{section}")


def _quotes_prompt(quote_candidates: list[str], period_label: str) -> str:
    return INSIGHT_QUOTES_TMPL.format(
        period_label=period_label,
        quote_candidates=json.dumps(quote_candidates, ensure_ascii=False),
    )


def _has_goal_data(stats: dict) -> bool:
    return bool(stats.get("linked_goal_summary") or stats.get("linked_goal_ids"))


def _format_goal_summary(stats: dict) -> str:
    summary = stats.get("linked_goal_summary")
    if isinstance(summary, list) and summary:
        lines = []
        for item in summary:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("content") or item.get("goal") or "").strip()
            count = item.get("count", 0)
            status = str(item.get("status") or "").strip()
            deadline = str(item.get("deadline") or "").strip()
            meta = "，".join(part for part in [f"{count} 条记录", status, deadline] if part)
            if title:
                lines.append(f"- {title}（{meta}）" if meta else f"- {title}")
        if lines:
            return "\n".join(lines)

    goal_ids = [str(item).strip() for item in stats.get("linked_goal_ids", []) if str(item).strip()]
    return "\n".join(f"- {goal_id}" for goal_id in goal_ids) if goal_ids else "（无关联目标）"


def _format_emotion_timeline(scores: dict) -> str:
    if not isinstance(scores, dict) or not scores:
        return "（暂无情绪强度数据）"

    rows = []
    for session_id, item in scores.items():
        if not isinstance(item, dict) or not item:
            continue
        top = _top_items(item, 3)
        rows.append(f"{session_id}: " + "、".join(f"{name} {value:.2f}" for name, value in top))
    return "\n".join(rows[:20]) if rows else "（暂无情绪强度数据）"


def _top_items(mapping, limit: int | None = None) -> list[tuple[str, float]]:
    if not isinstance(mapping, dict):
        return []

    items = []
    for key, value in mapping.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        items.append((name, num))
    items.sort(key=lambda item: (-item[1], item[0]))
    return items[:limit] if limit else items


def _format_mapping(items) -> str:
    if isinstance(items, dict):
        items = _top_items(items)
    pairs = list(items)
    if not pairs:
        return "（暂无数据）"
    return "、".join(f"{name}：{_format_number(value)}" for name, value in pairs)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def _format_lines(lines: Iterable[str]) -> str:
    values = [str(line).strip() for line in lines if str(line).strip()]
    if not values:
        return "（暂无片段）"
    return "\n".join(f"- {line}" for line in values)


def _sample_snippets(sessions: list[dict], limit: int) -> list[str]:
    candidates = []
    for session in sessions:
        date = str(session.get("content_time", "")).strip()
        description = str(session.get("description", "")).strip()
        if description:
            prefix = f"{date}：" if date else ""
            candidates.append(prefix + _clip(description, 120))
    return _sample(candidates, limit)


def _sample_quote_candidates(sessions: list[dict], limit: int) -> list[str]:
    candidates = []
    seen = set()
    for session in sessions:
        for key in ("feeling", "description"):
            value = str(session.get(key, "")).strip()
            if not value:
                continue
            value = _clip(value, 160)
            if value in seen:
                continue
            seen.add(value)
            candidates.append(value)
    return _sample(candidates, limit)


def _sample(values: list[str], limit: int) -> list[str]:
    if len(values) <= limit:
        return values
    return random.sample(values, limit)


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _sanitize_quotes(value, candidates: list[str]) -> list[str]:
    if isinstance(value, dict):
        raw_items = value.get("quotes", [])
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []

    allowed = set(candidates)
    quotes = []
    seen = set()
    for item in raw_items:
        quote = str(item).strip()
        if not quote or quote not in allowed or quote in seen:
            continue
        seen.add(quote)
        quotes.append(quote)
        if len(quotes) >= 3:
            break
    return quotes
