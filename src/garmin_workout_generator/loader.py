"""Read a workout JSON file and turn it into model objects.

Every check raises WorkoutConfigError with a location such as
"steps[1].steps[2].duration", so a typo in a long file is easy to find.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .model import Duration, DurationKind, PaceTarget, Repeat, Step, StepType, Workout

SUPPORTED_SPORTS = {"training", "running"}
PACE_PATTERN = re.compile(r"(\d{1,2}):([0-5]\d)")


class WorkoutConfigError(ValueError):
    """Raised when the JSON file is not a valid workout."""


def load_workout(path: str | Path) -> Workout:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise WorkoutConfigError(f"File not found: {path}") from None
    except json.JSONDecodeError as e:
        raise WorkoutConfigError(
            f"{path}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}"
        ) from None
    return parse_workout(data)


def parse_workout(data: Any) -> Workout:
    _require_type(data, dict, "workout")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WorkoutConfigError("name: must be a non-empty string")

    sport = data.get("sport", "training")
    if sport not in SUPPORTED_SPORTS:
        raise WorkoutConfigError(
            f"sport: '{sport}' is not supported (use one of: {', '.join(sorted(SUPPORTED_SPORTS))})"
        )

    raw_steps = data.get("steps")
    _require_type(raw_steps, list, "steps")
    if not raw_steps:
        raise WorkoutConfigError("steps: the workout needs at least one step")

    steps = [_parse_item(item, f"steps[{i}]") for i, item in enumerate(raw_steps)]
    return Workout(name=name.strip(), sport=sport, steps=steps)


def _parse_item(item: Any, where: str) -> Step | Repeat:
    _require_type(item, dict, where)
    if item.get("type") == "repeat":
        return _parse_repeat(item, where)
    return _parse_step(item, where)


def _parse_repeat(item: dict, where: str) -> Repeat:
    rounds = item.get("rounds")
    if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1:
        raise WorkoutConfigError(f"{where}.rounds: must be a whole number >= 1")

    raw_steps = item.get("steps")
    _require_type(raw_steps, list, f"{where}.steps")
    if not raw_steps:
        raise WorkoutConfigError(f"{where}.steps: a repeat block needs at least one step")

    steps = []
    for i, child in enumerate(raw_steps):
        child_where = f"{where}.steps[{i}]"
        _require_type(child, dict, child_where)
        if child.get("type") == "repeat":
            # FIT allows nesting, but many watches handle it badly. Keep it simple.
            raise WorkoutConfigError(f"{child_where}: repeat blocks cannot be nested")
        steps.append(_parse_step(child, child_where))
    return Repeat(rounds=rounds, steps=steps)


def _parse_step(item: dict, where: str) -> Step:
    raw_type = item.get("type")
    valid = [t.value for t in StepType]
    if raw_type not in valid:
        raise WorkoutConfigError(
            f"{where}.type: '{raw_type}' is not valid (use one of: {', '.join(valid + ['repeat'])})"
        )
    step_type = StepType(raw_type)

    exercise = item.get("exercise")
    if exercise is not None and (not isinstance(exercise, str) or not exercise.strip()):
        raise WorkoutConfigError(f"{where}.exercise: must be a non-empty string")
    if step_type is StepType.EXERCISE and exercise is None:
        raise WorkoutConfigError(f"{where}.exercise: required for exercise steps")

    note = item.get("note")
    if note is not None and not isinstance(note, str):
        raise WorkoutConfigError(f"{where}.note: must be a string")

    duration = _parse_duration(item.get("duration"), f"{where}.duration")
    target = _parse_target(item["target"], f"{where}.target") if "target" in item else None
    return Step(type=step_type, duration=duration, exercise=exercise, note=note, target=target)


def _parse_duration(raw: Any, where: str) -> Duration:
    _require_type(raw, dict, where)
    if len(raw) != 1:
        raise WorkoutConfigError(
            f"{where}: give exactly one of 'time', 'reps' or 'lap_button' (got {sorted(raw) or 'nothing'})"
        )
    key, value = next(iter(raw.items()))

    if key == "lap_button":
        if value is not True:
            raise WorkoutConfigError(f"{where}.lap_button: must be true")
        return Duration(DurationKind.LAP_BUTTON)

    if key in ("time", "reps"):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            unit = "seconds" if key == "time" else "repetitions"
            raise WorkoutConfigError(f"{where}.{key}: must be a whole number of {unit} >= 1")
        return Duration(DurationKind(key), value)

    raise WorkoutConfigError(f"{where}: unknown duration '{key}' (use 'time', 'reps' or 'lap_button')")


def _parse_target(raw: Any, where: str) -> PaceTarget:
    _require_type(raw, dict, where)
    if set(raw) != {"pace"}:
        raise WorkoutConfigError(f"{where}: must contain only 'pace' (got {sorted(raw) or 'nothing'})")

    pace = raw["pace"]
    pace_where = f"{where}.pace"
    _require_type(pace, dict, pace_where)
    unknown = set(pace) - {"fast", "slow"}
    if unknown:
        raise WorkoutConfigError(f"{pace_where}: unknown keys {sorted(unknown)} (use 'fast' and 'slow')")

    fast = _parse_pace(pace.get("fast"), f"{pace_where}.fast")
    slow = _parse_pace(pace.get("slow"), f"{pace_where}.slow")
    if fast >= slow:
        raise WorkoutConfigError(f"{pace_where}: 'fast' must be faster than 'slow' (a lower time per km)")
    return PaceTarget(fast_sec_per_km=fast, slow_sec_per_km=slow)


def _parse_pace(raw: Any, where: str) -> int:
    """Turn a pace such as "5:30" (min:sec per km) into seconds per km."""
    match = PACE_PATTERN.fullmatch(raw) if isinstance(raw, str) else None
    seconds = int(match[1]) * 60 + int(match[2]) if match else 0
    if seconds == 0:
        raise WorkoutConfigError(f"{where}: must be a pace per km like \"5:30\" (got {raw!r})")
    return seconds


def _require_type(value: Any, expected: type, where: str) -> None:
    if not isinstance(value, expected):
        names = {dict: "an object { }", list: "a list [ ]"}
        raise WorkoutConfigError(f"{where}: must be {names.get(expected, expected.__name__)}")
