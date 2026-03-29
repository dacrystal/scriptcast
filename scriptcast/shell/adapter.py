# scriptcast/shell/adapter.py
from abc import ABC, abstractmethod

class ShellAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def tracing_preamble(self, trace_prefix: str) -> str:
        """Return shell code to enable tracing with the given prefix."""
        ...
