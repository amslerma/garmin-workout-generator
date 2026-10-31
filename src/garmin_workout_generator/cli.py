"""Command-line entry point: make-workout workouts/trx_full_body.json"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .exercises import is_known, load_library
from .loader import WorkoutConfigError, load_workout
from .writer import flatten, step_label


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make-workout",
        description="Generate a Garmin .fit workout file from a JSON definition.",
    )
    parser.add_argument("config", type=Path, nargs="?", help="path to the workout JSON file")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="output .fit path (default: output/<config name>.fit)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="only validate the file and print the steps, don't write a .fit",
    )
    parser.add_argument(
        "--exercises", action="store_true",
        help="list the exercise library and exit",
    )
    args = parser.parse_args(argv)

    if args.exercises:
        for key, label in sorted(load_library().items()):
            print(f"  {key:<24} {label}")
        return 0
    if args.config is None:
        parser.error("give a workout JSON file (or use --exercises)")

    try:
        workout = load_workout(args.config)
    except WorkoutConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print_summary(workout)
    if args.check:
        return 0

    from .writer import write_fit  # needs fit-tool

    out = args.output or Path("output") / f"{args.config.stem}.fit"
    path = write_fit(workout, out)
    print(f"\nWrote {path}")
    return 0


def print_summary(workout) -> None:
    print(f"{workout.name} ({workout.sport})")
    unknown = set()
    for i, flat in enumerate(flatten(workout)):
        if flat.is_repeat:
            print(f"  {i:2}  repeat steps {flat.repeat_from}-{i - 1} x{flat.rounds}")
            continue
        step = flat.step
        d = step.duration
        amount = {"time": f"{d.value}s", "reps": f"{d.value} reps",
                  "lap_button": "until lap"}[d.kind.value]
        print(f"  {i:2}  {step_label(step):<20} {amount}")
        if step.exercise and not is_known(step.exercise):
            unknown.add(step.exercise)
    if unknown:
        print(f"\nNote: not in the exercise library, name generated from key: "
              f"{', '.join(sorted(unknown))}")


if __name__ == "__main__":
    sys.exit(main())
