"""Turn a Workout into a .fit workout file.

Two stages:
1. flatten()   - pure Python: turns nested repeat blocks into the flat list of
                 steps the FIT format uses. Easy to test, no fit-tool needed.
2. write_fit() - maps the flat steps onto fit-tool messages and saves the file.

How FIT stores a repeat block: the steps inside the block come first, followed
by one extra "repeat" step that says "jump back to step N, do this R times".
So [warmup, repeat 3x [A, B], cooldown] becomes:
    0 warmup
    1 A
    2 B
    3 repeat -> back to step 1, 3 times
    4 cooldown

How the watch shows exercise names: it ignores the step's own name field.
Instead each exercise step carries an (exercise_category, exercise_name) pair
of numbers, and the file contains one "exercise title" record per pair with
the text to display. We use category UNKNOWN plus our own numbers 0, 1, 2...
so the watch shows our names rather than Garmin's built-in exercise list.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from .exercises import label_for
from .model import Duration, Repeat, Step, StepType, Workout


@dataclass(frozen=True)
class FlatStep:
    """One FIT workout step. Either a normal step or a repeat marker."""

    step: Step | None = None          # set for normal steps
    repeat_from: int | None = None    # set for repeat markers: first step index
    rounds: int | None = None         # set for repeat markers

    @property
    def is_repeat(self) -> bool:
        return self.step is None


def flatten(workout: Workout) -> list[FlatStep]:
    flat: list[FlatStep] = []
    for item in workout.steps:
        if isinstance(item, Repeat):
            first_index = len(flat)
            flat.extend(FlatStep(step=s) for s in item.steps)
            flat.append(FlatStep(repeat_from=first_index, rounds=item.rounds))
        else:
            flat.append(FlatStep(step=item))
    return flat


def exercise_ids(flat: list[FlatStep]) -> dict[str, int]:
    """Number each distinct exercise in order of first appearance: {"trx_row": 0, ...}."""
    ids: dict[str, int] = {}
    for f in flat:
        if f.step is not None and f.step.exercise and f.step.exercise not in ids:
            ids[f.step.exercise] = len(ids)
    return ids


def step_label(step: Step) -> str:
    """Name shown for a step."""
    if step.exercise:
        return label_for(step.exercise)
    return {
        StepType.WARMUP: "Warm Up",
        StepType.EXERCISE: "Exercise",
        StepType.REST: "Rest",
        StepType.COOLDOWN: "Cool Down",
    }[step.type]


def write_fit(workout: Workout, out_path: str | Path) -> Path:
    # Imported here so the rest of the package (and the tests) work
    # even on a machine without fit-tool installed.
    from fit_tool.fit_file_builder import FitFileBuilder
    from fit_tool.profile.messages.exercise_title_message import ExerciseTitleMessage
    from fit_tool.profile.messages.file_id_message import FileIdMessage
    from fit_tool.profile.messages.workout_message import WorkoutMessage
    from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
    from fit_tool.profile.profile_type import (
        ExerciseCategory,
        FileType,
        Intensity,
        Manufacturer,
        Sport,
        SubSport,
        WorkoutStepDuration,
        WorkoutStepTarget,
    )

    intensity_for = {
        StepType.WARMUP: Intensity.WARMUP,
        StepType.EXERCISE: Intensity.ACTIVE,
        StepType.REST: Intensity.REST,
        StepType.COOLDOWN: Intensity.COOLDOWN,
    }
    sport_for = {
        "training": (Sport.TRAINING, SubSport.STRENGTH_TRAINING),
        "running": (Sport.RUNNING, SubSport.GENERIC),
    }

    file_id = FileIdMessage()
    file_id.type = FileType.WORKOUT
    file_id.manufacturer = Manufacturer.DEVELOPMENT.value
    file_id.product = 0
    file_id.serial_number = 0x12345678
    file_id.time_created = round(datetime.datetime.now().timestamp() * 1000)

    flat_steps = flatten(workout)
    ids = exercise_ids(flat_steps)

    fit_steps = []
    for index, flat in enumerate(flat_steps):
        msg = WorkoutStepMessage()
        msg.message_index = index
        if flat.is_repeat:
            msg.duration_type = WorkoutStepDuration.REPEAT_UNTIL_STEPS_CMPLT
            msg.duration_step = flat.repeat_from
            msg.target_repeat_steps = flat.rounds
        else:
            step = flat.step
            msg.workout_step_name = step_label(step)
            msg.intensity = intensity_for[step.type]
            _set_duration(msg, step.duration, WorkoutStepDuration)
            msg.target_type = WorkoutStepTarget.OPEN
            if step.exercise:
                _set(msg, "exercise_category", ExerciseCategory.UNKNOWN)
                _set(msg, "exercise_name", ids[step.exercise])
            if step.note:
                _set(msg, "notes", step.note)
        fit_steps.append(msg)

    titles = []
    for key, number in ids.items():
        title = ExerciseTitleMessage()
        _set(title, "message_index", number)
        _set(title, "exercise_category", ExerciseCategory.UNKNOWN)
        _set(title, "exercise_name", number)
        _set(title, "workout_step_name", label_for(key))
        titles.append(title)

    sport, sub_sport = sport_for[workout.sport]
    workout_msg = WorkoutMessage()
    workout_msg.workout_name = workout.name
    workout_msg.sport = sport
    workout_msg.sub_sport = sub_sport
    workout_msg.num_valid_steps = len(fit_steps)

    builder = FitFileBuilder(auto_define=True, min_string_size=50)
    builder.add(file_id)
    builder.add(workout_msg)
    builder.add_all(fit_steps)
    builder.add_all(titles)  # title records go after the steps

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    builder.build().to_file(str(out_path))
    return out_path


def _set(msg, field: str, value) -> None:
    """Set a field, failing loudly if this fit-tool version doesn't have it.

    Python happily lets you set any attribute on an object, so a typo in a
    field name would otherwise be silently ignored and never reach the file.
    """
    if not hasattr(type(msg), field):
        raise AttributeError(
            f"{type(msg).__name__} has no field '{field}' in this fit-tool version"
        )
    setattr(msg, field, value)


def _set_duration(msg, duration: Duration, WorkoutStepDuration) -> None:
    kind = duration.kind.value
    if kind == "time":
        msg.duration_type = WorkoutStepDuration.TIME
        msg.duration_time = float(duration.value)  # seconds
    elif kind == "reps":
        msg.duration_type = WorkoutStepDuration.REPS
        msg.duration_reps = duration.value
    else:  # lap_button
        msg.duration_type = WorkoutStepDuration.OPEN
