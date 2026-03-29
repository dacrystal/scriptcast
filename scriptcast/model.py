# scriptcast/model.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union

@dataclass
class SceneStart:
    name: str

@dataclass
class CommandTrace:
    text: str  # command text without PS4 prefix

@dataclass
class OutputLine:
    text: str

@dataclass
class InputLine:
    text: str = ""  # reserved for future use; currently empty

@dataclass
class Directive:
    name: str
    args: list[str] = field(default_factory=list)

@dataclass
class PauseBlock:
    events: list[ScriptEvent] = field(default_factory=list)

ScriptEvent = Union[SceneStart, CommandTrace, OutputLine, InputLine, Directive, PauseBlock]
