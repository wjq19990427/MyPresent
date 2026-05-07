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
        """向后兼容接口，子类实现 execute() 时可将此方法委托过去。"""

    def execute(self, session_data: dict) -> SkillResult:
        """标准化调用接口：接收 session_data 字典，返回 SkillResult。
        子类直接覆盖此方法即可；默认实现委托给 run()。
        """
        return self.run(session_data)
