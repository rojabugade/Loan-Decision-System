from abc import ABC, abstractmethod
from typing import Any

from app.schemas.common import AgentResult


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def run(self, state: dict[str, Any]) -> AgentResult:
        raise NotImplementedError
