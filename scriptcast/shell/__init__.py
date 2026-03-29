# scriptcast/shell/__init__.py
from .adapter import ShellAdapter
from .bash import BashAdapter
from .zsh import ZshAdapter

_ADAPTERS: dict[str, ShellAdapter] = {
    "bash": BashAdapter(),
    "zsh": ZshAdapter(),
}

def get_adapter(shell: str) -> ShellAdapter:
    """Return adapter for shell name or full path (e.g. '/bin/bash' → BashAdapter).
    Raises ValueError for unsupported shells.
    """
    name = shell.split("/")[-1]
    if name not in _ADAPTERS:
        raise ValueError(
            f"Unsupported shell: {shell!r}. Supported: {list(_ADAPTERS)}"
        )
    return _ADAPTERS[name]
