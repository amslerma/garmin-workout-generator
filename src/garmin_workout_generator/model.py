"""Data model for a workout.

These classes describe a workout in plain Python, independent of JSON and of
the FIT format. The loader builds them from JSON; the writer turns them into
FIT messages. Keeping this layer separate means either side can change
(e.g. YAML input, or a web form later) without touching the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StepType(str, Enum):
    WARMUP = "warmup"
    EXERCISE = "exercise"
    REST = "rest"
    COOLDOWN = "cooldown"


class DurationKind(str, Enum):
    TIME = "time"            # value = seconds
    REPS = "reps"            # value = repetitions
    LAP_BUTTON = "lap_button"  # open-ended, press lap to continue


@dataclass(frozen=True)
class Duration:
    kind: DurationKind
    value: int | None = None  # None only for LAP_BUTTON


@dataclass(frozen=True)
class PaceTarget:
    fast_sec_per_km: int
    slow_sec_per_km: int


@dataclass
class Step:
    type: StepType
    duration: Duration
    exercise: str | None = None  # e.g. "trx_row"; shown as the step name
    note: str | None = None
    target: PaceTarget | None = None


@dataclass
class Repeat:
    rounds: int
    steps: list[Step] = field(default_factory=list)


@dataclass
class Workout:
    name: str
    sport: str
    steps: list[Step | Repeat] = field(default_factory=list)
