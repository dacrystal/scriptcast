# scriptcast/shell/zsh.py
from .adapter import ShellAdapter

class ZshAdapter(ShellAdapter):
    @property
    def name(self) -> str:
        return "zsh"

    def tracing_preamble(self, trace_prefix: str) -> str:
        return f'PS4="{trace_prefix} "\nsetopt xtrace\n'
