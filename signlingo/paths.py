"""Where the bundled files live, so every script works from any folder.

ROOT is the project folder in a source checkout, and the unpacked bundle
folder in a PyInstaller build (the spec copies files to the same layout).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"                              # all examples_*.json files live here
MODEL_PATH = ROOT / "models" / "hand_landmarker.task"  # MediaPipe hand model
ASSETS_DIR = ROOT / "signlingo" / "assets"
