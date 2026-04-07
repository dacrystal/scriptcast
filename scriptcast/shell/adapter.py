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

    def unescape_xtrace(self, text: str) -> str:
        """Decode shell-specific quoting in a directive text from xtrace output.
        Default implementation is identity (correct for bash).
        """
        return text
