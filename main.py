"""
main.py - starts SignLingo, the downloadable app.

Opens a modern start menu to choose between:
  [1] Letter practice  (practice.py)
  [2] Word challenge   (words.py)
All screens share one look from ui_style.py (see DESIGN.md).

Run from code:    python main.py
Build the app:    ./build_app.sh   (makes dist/SignLingo.app on macOS)

When opened from Finder, all logs and errors are written to 
SignLingo-log.txt in your home folder.
"""

import os
import runpy
import subprocess
import sys
import time
import traceback
import cv2
import numpy as np
import ui_style as ui

PACKAGED = hasattr(sys, "_MEIPASS")

if PACKAGED:
    log = open(os.path.join(os.path.expanduser("~"), "SignLingo-log.txt"), "w", buffering=1)
    sys.stdout = sys.stderr = log
    sys.argv = sys.argv[:1]   # macOS can add its own arguments; ignore them


def show_message(text):
    """A pop-up box on macOS and Windows; printed output elsewhere."""
    print(text)
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display alert "SignLingo" message "{text}"'])
    elif sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "SignLingo", 0)


def wait_for_camera(seconds=30):
    """Wait until macOS camera permission is granted."""
    end = time.time() + seconds
    while time.time() < end:
        cap = cv2.VideoCapture(0)
        ok = cap.isOpened() and cap.read()[0]
        cap.release()
        if ok:
            return True
        time.sleep(1)
    return False


MODES = [("1", "Letter practice", "practice"), ("2", "Word challenge", "words")]


def choose_mode():
    """Shows the start menu (same look as the games, from ui_style.py)."""
    canvas = np.zeros((480, 640, 3), dtype=np.uint8)
    ui.draw_menu(canvas, "SignLingo", [(key, label) for key, label, _ in MODES],
                 "press a number to start   ESC = quit")
    cv2.imshow(ui.WINDOW, canvas)
    while True:
        key = cv2.waitKey(0) & 0xFF
        for number, _, module in MODES:
            if key == ord(number):
                return module
        if key == 27:
            cv2.destroyAllWindows()
            sys.exit(0)


# In the packaged app, files are unpacked into a temporary folder (_MEIPASS).
base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
os.chdir(base)

try:
    if not wait_for_camera():
        show_message("SignLingo can't use the camera. Allow it in System Settings, "
                     "Privacy & Security, Camera, then open SignLingo again.")
        sys.exit(1)

    while True:   # ESC in a game comes back here; ESC in the menu quits
        runpy.run_module(choose_mode(), run_name="__main__")
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    show_message("SignLingo hit an error. Details are in SignLingo-log.txt in your home folder.")
    sys.exit(1)