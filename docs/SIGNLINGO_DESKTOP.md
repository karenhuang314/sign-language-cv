# SignLingo desktop app

SignLingo is a **PySide6 desktop application**, not a Gradio wrapper. It needs no
browser, local web server, account, or frame upload. The existing website and
OpenCV scripts are unchanged.

## Run from source

Use a virtual environment. Python 3.12 is a conservative starting choice; actual
wheel availability depends on operating system and processor. The current Windows
build was tested on Python 3.14.6 with PySide6 6.12.0, MediaPipe 1.1.1, OpenCV
5.0.0, and PyInstaller 6.22.3. That does not establish Mac compatibility.

```bash
python -m venv .venv-desktop
```

Activate it:

```text
Windows PowerShell: .venv-desktop\Scripts\Activate.ps1
Windows cmd:        .venv-desktop\Scripts\activate.bat
macOS:              source .venv-desktop/bin/activate
```

Then:

```bash
python -m pip install -r requirements-desktop.txt
python desktop_app.py
```

If PowerShell blocks activation, invoke `.venv-desktop\Scripts\python.exe`
directly instead. A local development environment has already been created on
this Windows machine; its installed dependencies are sufficient to run the app.

The app uses `hand_landmarker.task` and `data/examples_*.json` relative to the
application resources, not the terminal's current folder. Do not remove these
files from a source checkout or edit files inside a packaged build.

## Using the app

The camera fills the window and the game is drawn on the video: **Make: B**,
the green hold bar, **I see: B**, and a big green **Correct!** Every control
below is in the sidebar that opens with the gear button (top right). Keyboard:
a letter key practices that letter, **0** goes back to random.
(`signlingo/camera_window.py` is this look; the original card layout is still
in `signlingo/window.py`.)

1. Choose **Live recognition** or **Letter practice**.
2. Choose a practice target or **Random**. Only static letters with saved
   examples, plus experimental J/Z, are offered.
3. Click **Start camera**. Nothing captures video before this action.
4. Static targets require about 0.6 seconds of matching evidence and at least
   three samples. Missing/wrong predictions and long gaps reset the hold.
5. A completed J/Z movement counts once. Perform it over roughly 1–2 seconds.
6. After a success, relax/lower your hand or change the pose before another
   acceptance. This prevents holding a focus letter from repeatedly scoring.
7. **Skip** advances without points. **Reset session** clears the session score,
   not the all-time count.
8. **Stop** releases the camera and model. Closing the window requests the same
   safe shutdown and waits asynchronously for the worker to finish.

Controls:

- **Selfie view:** mirrors actual input pixels before detection.
- **Hand landmarks:** toggles dots and skeleton.
- **Low-power mode:** caps the processing loop at approximately 12 FPS rather
  than 24; actual performance depends on the camera and device.
- **Camera number:** start with 0; stop capture and try 1 for another device.
- **Space:** skip a target; **Escape:** stop the camera; **Ctrl+R:** reset session.

Reference sign images and word practice are not included in this initial desktop
version. Do not claim that nearest-neighbor agreement is a calibrated probability
or that this prototype validates ASL correctness.

## Privacy and persistence

- Capture, hand detection, classification, and movement tracking are local.
- No video recording, network upload, or new training examples are implemented.
- Camera preferences and the all-time correct counter use Qt's per-user
  `QSettings` storage (Windows user registry / macOS preferences).
- Rolling diagnostic logs go to Qt's per-user local application-data directory,
  in `signlingo.log`. No frames or landmark vectors are written to the log.
- Packaged model and examples are treated as read-only resources. If recording
  is added later, save it in a per-user data directory, not the installed app.

## Architecture

```text
OpenCV camera → QThread worker → MediaPipe + shared features.py + motion tracker
                                 ↓
                        Latest-result mailbox (one slot)
                                 ↓
                       Qt UI timer → preview + practice
```

The worker creates and closes its own detector and camera. Widget access stays
on the main thread. The mailbox replaces old frames rather than building a queue;
it preserves an unconsumed motion-completion flag while the same result is held.
Settings are synchronized on exit. The camera driver can still delay shutdown if
its native read call blocks; the app does not forcibly terminate native code.

## Tests without a camera

```bash
python -m unittest test_desktop test_motion_recognition
python desktop_app.py --self-test
python desktop_app.py --smoke-test
```

`--self-test` loads real bundled examples and runs the real model on a blank
frame, then exits. `--smoke-test` briefly opens the UI, never opens the webcam,
and exits. For headless test environments, set `QT_QPA_PLATFORM=offscreen`.
Offscreen Windows rendering can lack system fonts; use the normal Windows Qt
platform for visual inspection.

The automatic tests cover practice timing, release/repeat handling, J/Z events,
mailbox behavior, worker cleanup/failure, RGB conversion, mirroring, monotonic
model timestamps, resource lookup, and UI controls/settings. Physical webcam
behavior and recognition accuracy still require manual testing.

## Package on Windows or Mac

Install packaging dependencies in a clean environment for the target OS:

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm SignLingo.spec
```

The spec bundles the hand model, only `examples_*.json` (not the dataset ZIP),
UI assets, and MediaPipe's native resources. Gradio is not bundled. Builds and
virtual environments are ignored by Git.

- **Windows:** run `dist/SignLingo/SignLingo.exe`. Distribute the **whole
  `dist/SignLingo` folder**, not the executable alone. Zip that folder or add an
  installer later. The first tested build is about 496 MiB before compression.
- **macOS:** build on a Mac; the spec creates `dist/SignLingo.app` with
  `NSCameraUsageDescription` and a bundle identifier. Distribute the app bundle;
  DMG creation is a separate step.

The same source code is used on both OSes, but the binaries are **not**
interchangeable. PyInstaller is not a general cross-compiler. Use a Windows
machine/runner for Windows and a Mac machine/runner for Mac. Intel and Apple
Silicon need matching Python/native dependencies and usually separate builds;
do not promise universal/Intel support before confirming MediaPipe wheel
availability and testing the resulting app.

Validate packages on a clean computer without Python. On Windows the current
build passed both commands below, including from a directory outside the repo:

```text
dist\SignLingo\SignLingo.exe --self-test
dist\SignLingo\SignLingo.exe --smoke-test
```

For a Mac build:

```bash
dist/SignLingo.app/Contents/MacOS/SignLingo --self-test
```

### Before distributing publicly

- Test actual camera permission prompts and safe start/stop on each target OS.
- Sign Windows releases as appropriate; unsigned builds may show trust warnings.
- Sign/notarize Mac releases using your own Apple credentials. This spec does
  not perform production signing or notarization. Sandboxed distribution may
  need additional entitlements; the Mac App Store is a separate workflow.
- Review PySide6/Qt licensing and redistribution obligations, plus OpenCV,
  MediaPipe/model, and dataset licenses. Complete the dataset source/license
  placeholder in README.md before distributing imported examples.
- Add release metadata, application/installer icons, and installer/update flows
  as needed. The application window uses the included SignLingo SVG; platform
  executable/installer icons are not customized by the initial spec.

## Troubleshooting

- **Camera unavailable:** close Zoom/Teams/FaceTime, check OS camera privacy
  settings, and try another camera number.
- **Mac camera denial:** enable permission for the terminal/Python when running
  source, or SignLingo when running the packaged app. Verify the app's Info.plist
  includes the camera description. Do not disable OS security globally.
- **Missing model/data:** rebuild with `SignLingo.spec`; retain the complete build.
- **Dependency install failure:** use a Python/processor combination supported
  by PySide6 and MediaPipe. Recheck Intel Mac availability in particular.
- **Slow movement recognition:** use better lighting and slower gestures. Static
  practice can remain usable even if J/Z sampling is unreliable.
