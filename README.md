# garmin-workout-generator

Create structured home workouts as Garmin `.fit` workout files from simple JSON definitions, then copy them to your watch over USB. No Garmin Connect account needed.

Built for circuits with a TRX, a mat and bodyweight exercises: reps or time per exercise, rest between exercises, and repeated rounds.

## Setup

Requires Python 3.11+.

```bash
git clone git@github.com:YOUR_USERNAME/garmin-workout-generator.git
cd garmin-workout-generator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

This installs the `make-workout` command inside the virtual environment.

## Usage

```bash
make-workout workouts/trx_full_body.json          # writes output/trx_full_body.fit
make-workout workouts/trx_full_body.json --check  # validate and preview only
make-workout workouts/trx_full_body.json -o my.fit
make-workout --exercises                          # list the exercise library
```

Build every workout at once:

```bash
for f in workouts/*.json; do make-workout "$f"; done
```

## Loading a workout onto the watch

1. Connect the watch via USB.
2. Copy the `.fit` file into `GARMIN/NewFiles`.
3. Safely eject the watch, then unplug it. The watch imports the file on disconnect.
4. On the watch, start an activity such as Strength and open **Training → Workouts**.

To replace a workout, delete the old one on the watch first.

## Workout file format

Each JSON file in `workouts/` is one workout:

```json
{
  "name": "TRX Full Body",
  "sport": "training",
  "steps": [
    { "type": "warmup", "duration": { "time": 300 }, "note": "Easy mobility" },
    { "type": "repeat", "rounds": 3, "steps": [
        { "type": "exercise", "exercise": "trx_row", "duration": { "reps": 12 } },
        { "type": "rest", "duration": { "time": 20 } },
        { "type": "exercise", "exercise": "trx_squat", "duration": { "time": 40 } },
        { "type": "rest", "duration": { "time": 60 } }
    ]},
    { "type": "cooldown", "duration": { "lap_button": true } }
  ]
}
```

| Field | Values |
|---|---|
| `name` | Shown in the watch's workout list. Keep it unique. |
| `sport` | `training` (strength, default) or `running` |
| `type` | `warmup`, `exercise`, `rest`, `cooldown`, `repeat` |
| `exercise` | Key from the exercise library, required for `exercise` steps |
| `duration` | Exactly one of `{"time": seconds}`, `{"reps": count}`, `{"lap_button": true}` |
| `target` | Optional pace range per km: `{"pace": {"fast": "5:30", "slow": "6:15"}}` |
| `note` | Optional text for the step |
| `rounds` | For `repeat` blocks: how many times to run the inner steps |

Repeat blocks cannot be nested. Invalid files are rejected with the exact location of the problem, for example `steps[1].steps[2].duration.time: must be a whole number of seconds >= 1`.

## Exercise library

Display names live in `src/garmin_workout_generator/exercises.json`:

```json
{ "trx_row": "TRX Row", "push_up": "Push-Up" }
```

Add your own exercises there. Keys not in the library still work; their name is generated from the key (`box_jump` → "Box Jump") and the CLI prints a note.

## How exercise names reach the watch

On strength workouts the watch ignores the step name field. Instead, each exercise step carries an exercise category and number, and the file contains one exercise title record per exercise with the text to display. This tool uses category "unknown" with its own numbers, so the watch shows your custom names rather than Garmin's built-in exercise list.

## Project structure

```
src/garmin_workout_generator/
├── cli.py            # make-workout command (argparse)
├── model.py          # dataclasses: Workout, Step, Repeat, Duration
├── loader.py         # read and validate workout JSON
├── writer.py         # flatten repeats, write the .fit file with fit-tool
├── exercises.py      # exercise library lookup
└── exercises.json    # exercise display names
tests/                # pytest tests
workouts/             # workout definitions (JSON)
output/               # generated .fit files (not committed)
```

## Development

```bash
pytest
```

## Roadmap

- Format helpers that expand EMOM, Tabata and AMRAP into steps
- Round-trip check that reads a generated `.fit` file back
- Running intervals with distance-based steps
- Map exercises to Garmin's built-in exercise categories
- Small web UI, packaged with Docker for a homelab server

## Built with

- [fit-tool](https://pypi.org/project/fit-tool/) for writing FIT files