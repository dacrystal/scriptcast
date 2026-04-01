# scriptcast/shell/bash.py
from .adapter import ShellAdapter


class BashAdapter(ShellAdapter):
    @property
    def name(self) -> str:
        return "bash"

    def tracing_preamble(self, trace_prefix: str) -> str:
        return f'PS4="{trace_prefix} "\nset -x\n'
