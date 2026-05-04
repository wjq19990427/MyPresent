"""Skills 插件基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SkillResult:
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class BaseSkill(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, session: dict, **kwargs) -> SkillResult:
        """执行 Skill，返回 SkillResult。"""
