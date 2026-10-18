# SignLingo: ASL fingerspelling practice

A webcam app that recognizes American Sign Language fingerspelling letters
(A to Z, with J and Z recognized from movement) and a practice game that
asks you to make a letter and says "Correct!" when you do.

This is a **fingerspelling practice tool**, not an app that teaches ASL.

## How it works

1. **OpenCV** reads the webcam.
2. **MediaPipe** finds 21 points on your hand (`models/hand_landmarker.task`).
3. `signlingo/features.py` turns those points into 42 numbers that don't depend on
   where your hand is or how big it looks.
4. The app compares them with saved examples in `data/` and the 5 closest
   examples vote on the letter (k-nearest neighbours, no training step).
5. J and Z are recognized from the path your finger draws
   (`signlingo/motion_recognition.py`).

## Setup

Python 3.10 to 3.12.

```
pip install -r requirements.txt
```

## SignLingo desktop app (PySide6)

A standalone desktop interface is available alongside the existing website:

```bash
python -m pip install -r requirements-desktop.txt
python desktop_app.py
```

It offers local live recognition, letter practice, J/Z tracking, score/progress,
start/stop camera controls, and low-power mode. **No Gradio, browser, server, or
video upload is required.** Preferences and an all-time practice count are saved
per user; reference examples are not modified.

**Mac app:** `./packaging/macos/build_app.sh` (inside the desktop venv) builds
`dist/SignLingo.app` and `dist/SignLingo-<version>.dmg`, a standalone download
that needs no Python. See [Share the Mac app](docs/SIGNLINGO_DESKTOP.md#share-the-mac-app).
The same spec also builds a Windows folder on Windows. See
[desktop setup and packaging](docs/SIGNLINGO_DESKTOP.md).

## Run

Run everything from the repo root.

| Command | What it does |
|---|---|
| `python desktop_app.py` | **SignLingo desktop**: native Qt window with local recognition and practice. |
| `python -m web.app` | **Website** (Gradio): open the link it prints, allow the camera, press Record. Live tab shows the letter; Practice tab is the game with a letter picker. |
| `python -m tools.launcher` | Start menu for the OpenCV games: letter practice or Word Challenge. |
| `python -m tools.words` | Word Challenge: spell random words up to 5 letters. |
| `python -m tools.practice` | Practice game: make the letter shown, hold it, get "Correct!". SPACE skips, ESC quits. |
| `python -m tools.practice B` | Focus mode: practice only B (or press a letter key while running; `0` goes back to random). Shows how many times it worked and how long the last one took. |
| `python -m web.web_app` | Second Gradio website (Karen's): live letters and sentence building; records into the root `examples_karen.json`. |
| `python -m tools.camera` | Live classifier: shows the letter it sees. Press a letter key to record 20 examples (saved to `data/examples_camera.json`). ESC quits. |
| `python -m tools.collect_data yourname_left` | Record examples one key press at a time into `data/examples_yourname_left.json`. `1` undoes, ESC quits. |
| `python -m tools.examples_tool count` | How many examples each letter has. |
| `python -m unittest discover tests` | All tests, no webcam needed (the desktop tests need PySide6). |
| `./packaging/macos/build_app.sh` | Build the Mac app and the `.dmg` to share (checks the app before packaging it). |

## Files

```
desktop_app.py          SignLingo desktop entry point
signlingo/              the shared package
  features.py           hand -> 42 numbers, and the k-NN letter guesser
  motion_recognition.py J and Z from finger movement
  paths.py              where the model and data live (works from any folder)
  recognition.py        frame -> letter, used by the desktop app
  practice.py           practice game rules (desktop)
  camera_worker.py      camera thread (desktop)
  camera_window.py      camera-first desktop look with the gear sidebar
  window.py             original card-layout desktop window
  assets/               app icon
web/
  app.py                website version (Gradio): Live and Practice tabs
  web_app.py            second Gradio website, with sentence building
web-ui/                 React + Vite front end (starter template so far)
tools/                  OpenCV scripts
  camera.py             live classifier with recording
  launcher.py           start menu: letter practice or Word Challenge
  practice.py           practice game (the original demo)
  words.py              Word Challenge mode
  testcv.py             quick hand-model check
  collect_data.py       recorder, one file per person/hand
  examples_tool.py      count or remove saved examples
tests/                  camera-free tests (desktop + motion)
models/
  hand_landmarker.task  MediaPipe hand model
data/
  examples_karen.json   560 webcam examples, 24 still letters
  examples_dataset.json 726 examples made from the Kaggle ASL dataset
packaging/
  SignLingo.spec        PyInstaller recipe (Mac .app, or a Windows folder)
  macos/                Mac build script, app icon, first-open instructions
docs/                   desktop guide, and our mentor's step-by-step plan
requirements.txt          website + scripts (includes Gradio)
requirements-desktop.txt  desktop app only
requirements-build.txt    desktop app + PyInstaller
```

## Credits

- **Karen** (karenhuang314): live classifier (`tools/camera.py`): the
  42-number weighted recipe, k-NN voting, recording, drawing; recorded the
  webcam examples (`data/examples_karen.json`).
- **Etinosa** (EOgbeide1): J and Z motion recognition and its tests,
  the motion version of the camera app, the hand model file, and the Kaggle
  examples (`data/examples_dataset.json`).
- **Jeffrey** (JeffreySong08): first camera hand tracking, the
  practice game, the recorder and examples tool, and organizing the repo.
- Our mentor: Brandon Shin, the step-by-step guide in `docs/plan.md`.
- Hand photos for `data/examples_dataset.json` come from an ASL hand-sign
  dataset on Kaggle (add the dataset link and its license here).
- Built with help from Claude (Anthropic).

Full history of who wrote what is in `git log` (use `git log --follow <file>`
for files that were moved).
