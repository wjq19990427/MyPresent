"""情绪强度评分 Skill：快速统计 + LLM 精准评分。"""
from __future__ import annotations

import json

from core.db_manager import (
    get_emotion_scores,
    get_uncached_session_ids,
    upsert_emotion_scores,
)
from core.llm_client import call_llm
from core.prompts import EMOTION_SCORING_SYSTEM, EMOTION_SCORING_USER_TMPL

from .base_skill import BaseSkill, SkillResult


class EmotionScoringSkill(BaseSkill):
    name = "emotion_scoring"
    description = "生成记录的情绪强度评分"

    def score_quick(self, sessions: list[dict]) -> dict[str, dict[str, float]]:
        emotions = _collect_emotions(sessions)
        result: dict[str, dict[str, float]] = {}

        for session in sessions:
            session_id = _session_id(session)
            if not session_id:
                continue
            tags = set(_emotion_tags(session))
            scores = {emotion: 1.0 for emotion in emotions if emotion in tags}
            result[session_id] = scores
            upsert_emotion_scores(session_id, scores, "quick")

        return result

    def score_precise(
        self,
        sessions: list[dict],
        model_id: str,
    ) -> dict[str, dict[str, float]]:
        session_by_id = {
            session_id: session
            for session in sessions
            if (session_id := _session_id(session))
        }
        session_ids = list(session_by_id)
        if not session_ids:
            return {}

        result = get_emotion_scores(session_ids, "precise")
        emotions = _collect_emotions(sessions)
        if not model_id or not emotions:
            return {session_id: result.get(session_id, {}) for session_id in session_ids}

        uncached_ids = get_uncached_session_ids(session_ids, "precise")
        for session_id in uncached_ids:
            session = session_by_id[session_id]
            content = _build_content(session)
            if not content:
                result.setdefault(session_id, {})
                continue

            user_prompt = EMOTION_SCORING_USER_TMPL.format(
                emotions=json.dumps(emotions, ensure_ascii=False),
                content=content,
            )
            try:
                raw_scores = call_llm(
                    EMOTION_SCORING_SYSTEM,
                    user_prompt,
                    model_id=model_id,
                    expect_json=True,
                    skill_name=self.name,
                    session_id=session_id,
                )
            except Exception:
                result.setdefault(session_id, {})
                continue

            scores = _sanitize_scores(raw_scores, emotions)
            upsert_emotion_scores(session_id, scores, "precise", model_id=model_id)
            result[session_id] = scores

        return {session_id: result.get(session_id, {}) for session_id in session_ids}

    def run(self, session: dict, model_id: str = "", **kwargs) -> SkillResult:
        mode = kwargs.get("mode", "quick")
        try:
            if mode == "quick":
                scores = self.score_quick([session])
            elif mode == "precise":
                scores = self.score_precise([session], model_id)
            else:
                return SkillResult(success=False, error="mode 必须为 quick 或 precise")
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

        session_id = _session_id(session)
        return SkillResult(success=True, data=scores.get(session_id, {}))


def _session_id(session: dict) -> str:
    return str(session.get("session_id") or session.get("id") or "").strip()


def _emotion_tags(session: dict) -> list[str]:
    tags = session.get("emotion_tags", [])
    if not isinstance(tags, list):
        return []
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def _collect_emotions(sessions: list[dict]) -> list[str]:
    emotions = []
    seen = set()
    for session in sessions:
        for emotion in _emotion_tags(session):
            if emotion in seen:
                continue
            seen.add(emotion)
            emotions.append(emotion)
    return emotions


def _build_content(session: dict) -> str:
    parts = []
    for label, key in [
        ("感受", "feeling"),
        ("情绪说明", "emotion_note"),
        ("描述", "description"),
    ]:
        value = str(session.get(key, "")).strip()
        if value:
            parts.append(f"{label}：{value}")
    return "\n".join(parts)


def _sanitize_scores(result, emotions: list[str]) -> dict[str, float]:
    if not isinstance(result, dict):
        return {}

    allowed = set(emotions)
    scores: dict[str, float] = {}
    for emotion, value in result.items():
        emotion = str(emotion).strip()
        if emotion not in allowed:
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        scores[emotion] = max(0.0, min(1.0, score))
    return scores
