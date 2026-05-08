from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

CommandType = Literal["query_one", "query_self", "query_batch", "select", "export", "unknown"]

_TIME_KEYWORDS = re.compile(r"[月季QqQ]|\d{4}[-年]")


@dataclass
class ParsedCommand:
    type: CommandType
    names: list[str] = field(default_factory=list)
    time_text: str = ""


def _looks_like_time(text: str) -> bool:
    return bool(_TIME_KEYWORDS.search(text))


def parse_command(text: str) -> ParsedCommand:
    text = text.strip()

    if text.startswith("查我"):
        time_text = text[len("查我"):].strip()
        return ParsedCommand(type="query_self", names=[], time_text=time_text)

    if text.startswith("批量查"):
        rest = text[len("批量查"):].strip()
        parts = rest.split(None, 1)
        if not parts:
            return ParsedCommand(type="query_batch", names=[], time_text="")
        names_part = parts[0]
        time_text = parts[1].strip() if len(parts) > 1 else ""
        names_part = names_part.replace("，", ",")
        names = [n.strip() for n in names_part.split(",") if n.strip()]
        return ParsedCommand(type="query_batch", names=names, time_text=time_text)

    if text.startswith("查"):
        rest = text[len("查"):].strip()
        parts = rest.split(None, 1)
        if not parts:
            return ParsedCommand(type="query_one", names=[], time_text="")
        if len(parts) == 1:
            word = parts[0]
            if _looks_like_time(word):
                return ParsedCommand(type="query_one", names=[], time_text=word)
            else:
                return ParsedCommand(type="query_one", names=[word], time_text="")
        name = parts[0]
        time_text = parts[1].strip()
        return ParsedCommand(type="query_one", names=[name], time_text=time_text)

    if re.fullmatch(r"\d{1,2}", text):
        return ParsedCommand(type="select", names=[text], time_text="")

    if text == "导出":
        return ParsedCommand(type="export", names=[], time_text="")

    return ParsedCommand(type="unknown", names=[], time_text="")
