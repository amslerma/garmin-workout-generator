import json

import pytest

from garmin_workout_generator.loader import WorkoutConfigError, load_workout, parse_workout
from garmin_workout_generator.model import DurationKind, PaceTarget, Repeat, StepType
from garmin_workout_generator.writer import flatten, speed_range, step_label, write_fit


def minimal(**overrides):
    data = {
        "name": "Test",
        "steps": [{"type": "exercise", "exercise": "push_up", "duration": {"reps": 10}}],
    }
    data.update(overrides)
    return data


def test_example_file_loads(tmp_path):
    path = tmp_path / "w.json"
    path.write_text(json.dumps({
        "name": "TRX Full Body",
        "steps": [
            {"type": "warmup", "duration": {"time": 300}},
            {"type": "repeat", "rounds": 3, "steps": [
                {"type": "exercise", "exercise": "trx_row", "duration": {"reps": 12}},
                {"type": "rest", "duration": {"time": 20}},
            ]},
            {"type": "cooldown", "duration": {"lap_button": True}},
        ],
    }))
    w = load_workout(path)
    assert w.sport == "training"  # default
    assert isinstance(w.steps[1], Repeat)
    assert w.steps[2].duration.kind is DurationKind.LAP_BUTTON


def test_flatten_puts_repeat_marker_after_block():
    w = parse_workout(minimal(steps=[
        {"type": "warmup", "duration": {"time": 60}},
        {"type": "repeat", "rounds": 3, "steps": [
            {"type": "exercise", "exercise": "a", "duration": {"reps": 5}},
            {"type": "rest", "duration": {"time": 10}},
        ]},
        {"type": "cooldown", "duration": {"time": 60}},
    ]))
    flat = flatten(w)
    assert len(flat) == 5
    marker = flat[3]
    assert marker.is_repeat and marker.repeat_from == 1 and marker.rounds == 3
    assert flat[4].step.type is StepType.COOLDOWN


def test_step_label():
    w = parse_workout(minimal())
    assert step_label(w.steps[0]) == "Push-Up"


@pytest.mark.parametrize("bad, message", [
    (minimal(name=""), "name"),
    (minimal(sport="golf"), "sport"),
    (minimal(steps=[]), "at least one step"),
    (minimal(steps=[{"type": "jump", "duration": {"time": 5}}]), "steps[0].type"),
    (minimal(steps=[{"type": "exercise", "duration": {"reps": 5}}]), "steps[0].exercise"),
    (minimal(steps=[{"type": "rest", "duration": {"time": 5, "reps": 3}}]), "exactly one"),
    (minimal(steps=[{"type": "rest", "duration": {"time": -5}}]), "steps[0].duration.time"),
    (minimal(steps=[{"type": "repeat", "rounds": 0, "steps": []}]), "rounds"),
    (minimal(steps=[{"type": "repeat", "rounds": 2, "steps": [
        {"type": "repeat", "rounds": 2, "steps": []}]}]), "cannot be nested"),
])
def test_validation_errors(bad, message):
    with pytest.raises(WorkoutConfigError) as exc:
        parse_workout(bad)
    assert message in str(exc.value)


def run_step(target):
    return minimal(steps=[
        {"type": "exercise", "exercise": "run", "duration": {"lap_button": True}, "target": target},
    ])


def test_step_without_target_has_none():
    assert parse_workout(minimal()).steps[0].target is None


def test_pace_target_parsed_to_seconds_per_km():
    w = parse_workout(run_step({"pace": {"fast": "5:30", "slow": "6:15"}}))
    assert w.steps[0].target == PaceTarget(fast_sec_per_km=330, slow_sec_per_km=375)


@pytest.mark.parametrize("target, message", [
    ("5:30", "steps[0].target"),
    ({}, "steps[0].target"),
    ({"hr": 150}, "steps[0].target"),
    ({"pace": "5:30"}, "steps[0].target.pace"),
    ({"pace": {"fast": "5:30"}}, "steps[0].target.pace.slow"),
    ({"pace": {"fast": "5:30", "slow": "6:15", "avg": "6:00"}}, "steps[0].target.pace"),
    ({"pace": {"fast": "5:75", "slow": "6:15"}}, "steps[0].target.pace.fast"),
    ({"pace": {"fast": "0:00", "slow": "6:15"}}, "steps[0].target.pace.fast"),
    ({"pace": {"fast": 5.5, "slow": "6:15"}}, "steps[0].target.pace.fast"),
    ({"pace": {"fast": "6:15", "slow": "5:30"}}, "faster than"),
    ({"pace": {"fast": "5:30", "slow": "5:30"}}, "faster than"),
])
def test_invalid_pace_targets(target, message):
    with pytest.raises(WorkoutConfigError) as exc:
        parse_workout(run_step(target))
    assert message in str(exc.value)


def test_pace_converts_to_speed_with_slow_as_low():
    low, high = speed_range(PaceTarget(fast_sec_per_km=330, slow_sec_per_km=375))
    assert low == pytest.approx(1000 / 375)   # slow pace = low speed
    assert high == pytest.approx(1000 / 330)  # fast pace = high speed


def test_write_fit_stores_pace_as_speed_target(tmp_path):
    pytest.importorskip("fit_tool")
    from fit_tool.fit_file import FitFile
    from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
    from fit_tool.profile.profile_type import WorkoutStepTarget

    out = write_fit(parse_workout(run_step({"pace": {"fast": "5:30", "slow": "6:15"}})), tmp_path / "w.fit")

    records = FitFile.from_file(str(out)).records
    step = next(r.message for r in records if isinstance(r.message, WorkoutStepMessage))
    assert step.target_type == WorkoutStepTarget.SPEED.value
    assert step.target_value == 0  # 0 = custom range rather than a watch zone
    assert step.custom_target_speed_low == pytest.approx(1000 / 375, abs=0.001)
    assert step.custom_target_speed_high == pytest.approx(1000 / 330, abs=0.001)


def test_invalid_json_reports_line(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{\n  "name": "x",\n  "steps": [\n}')
    with pytest.raises(WorkoutConfigError, match="line 4"):
        load_workout(path)


def test_exercise_ids_numbered_by_first_appearance():
    w = parse_workout(minimal(steps=[
        {"type": "repeat", "rounds": 2, "steps": [
            {"type": "exercise", "exercise": "trx_row", "duration": {"reps": 5}},
            {"type": "rest", "duration": {"time": 10}},
            {"type": "exercise", "exercise": "push_up", "duration": {"reps": 5}},
        ]},
        {"type": "exercise", "exercise": "trx_row", "duration": {"reps": 5}},
    ]))
    from garmin_workout_generator.writer import exercise_ids
    assert exercise_ids(flatten(w)) == {"trx_row": 0, "push_up": 1}


def test_labels_from_library_and_fallback():
    from garmin_workout_generator.exercises import label_for
    assert label_for("trx_row") == "TRX Row"
    assert label_for("box_jump") == "Box Jump"
