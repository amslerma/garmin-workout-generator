import json

import pytest

from garmin_workout_generator.loader import WorkoutConfigError, load_workout, parse_workout
from garmin_workout_generator.model import DurationKind, Repeat, StepType
from garmin_workout_generator.writer import flatten, step_label


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
