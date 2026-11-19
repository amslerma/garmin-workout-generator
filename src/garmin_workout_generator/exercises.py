"""Exercise library: maps short keys used in workout files to display names.

The library lives in exercises.json next to this file. Add your own exercises
there as "key": "Display Name". Keys that aren't in the library still work;
their name is generated from the key ("box_jump" -> "Box Jump").
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def load_library() -> dict[str, str]:
    text = resources.files(__package__).joinpath("exercises.json").read_text(encoding="utf-8")
    return json.loads(text)

def _entry(key: str):
    return load_library().get(key)

def label_for(key: str) -> str:
    entry = _entry(key)
    if isinstance(entry, dict):
        return entry.get("name") or key.replace("_", " ").title()
    return entry or key.replace("_", " ").title()

def description_for(key: str) -> str | None:
    entry = _entry(key)
    return entry.get("description") if isinstance(entry, dict) else None

def is_known(key: str) -> bool:
    return key in load_library()
