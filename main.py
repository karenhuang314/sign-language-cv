"""
main.py - starts SignLingo, the downloadable app.

Opens a modern start menu to choose between:
  [1] Single Letter Practice (signlingo/practice.py)
  [2] Word Challenge Mode   (signlingo/words.py)

Run from code:    python main.py
Build the app:    ./packaging/build_app.sh   (makes dist/SignLingo.app on macOS)

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

from signlingo import camera, ui
from signlingo.settings_ui import SettingsPanel, window_is_open

PACKAGED = hasattr(sys, "_MEIPASS")


def show_message(text):
    """A pop-up box on macOS; printed output elsewhere."""
    print(text)
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display alert "SignLingo" message "{text}"'])


def wait_for_camera(seconds=30):
    """Wait for camera permission, keeping the camera open for the mode."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        cap = camera.open_camera()
        if cap.isOpened() and cap.read()[0]:
            return True
        camera.close_camera()
        time.sleep(1)
    return False


def choose_mode():
    """Start menu, in the same window and style as the practice screens."""
    w, h = ui.screen_size()
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    canvas[:] = ui.BACKGROUND

    mid = h // 2
    ui.centered(canvas, "SignLingo", mid - 160, 3.0, ui.WHITE, 7)
    ui.centered(canvas, "ASL fingerspelling practice", mid - 100, 1.0, ui.GREY, 2)

    # Keep the updated menu's style, with hit boxes matching its text.
    mode_rects = []
    for y, key, name, module in (
        (mid + 40, "1", "Single Letter Practice", "signlingo.practice"),
        (mid + 130, "2", "Word Challenge", "signlingo.words"),
    ):
        label_width = ui.text_width(f"{key}   {name}", 1.5, 4)
        x = (w - label_width) // 2
        ui.text(canvas, key, (x, y), 1.5, ui.YELLOW, 4)
        ui.text(canvas, name, (x + ui.text_width(f"{key}   ", 1.5, 4), y), 1.5, ui.WHITE, 4)
        mode_rects.append(((x - 16, y - 48, x + label_width + 16, y + 18), module))

    ui.help_line(canvas, "1 or 2 = start   ESC = quit")
    settings_panel = SettingsPanel()
    selected = {"mode": None}

    def on_mouse(event, x, y, flags, param):
        if settings_panel.on_mouse(event, x, y, flags, param):
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            for (x1, y1, x2, y2), module in mode_rects:
                if x1 <= x <= x2 and y1 <= y <= y2:
                    selected["mode"] = module
                    break

    ui.open_window()
    cv2.setMouseCallback(ui.WINDOW, on_mouse)
    switching_modes = False
    preloaded = False
    try:
        while True:
            ui.show(settings_panel.draw(canvas.copy()))
            # Poll instead of blocking: notice the native close button, too.
            key = cv2.waitKey(30) & 0xFF
            if not window_is_open(ui.WINDOW):
                return None
            if not preloaded:
                # Warm up tracking after the first menu frame is visible.
                # Keep the key above, so input during startup is not lost.
                import mediapipe  # noqa: F401
                from mediapipe.tasks.python import vision  # noqa: F401
                preloaded = True
            if settings_panel.handle_key(key):
                continue
            if key == ord("1"):
                selected["mode"] = "signlingo.practice"
            elif key == ord("2"):
                selected["mode"] = "signlingo.words"
            elif key == 27:
                return None
            if selected["mode"] is not None:
                switching_modes = True
                return selected["mode"]
    finally:
        # Carry the same full-screen window into the chosen mode.
        if not switching_modes:
            cv2.destroyAllWindows()


def main():
    if PACKAGED:
        log = open(os.path.join(os.path.expanduser("~"), "SignLingo-log.txt"), "w", buffering=1)
        sys.stdout = sys.stderr = log
        sys.argv = sys.argv[:1]  # macOS can add its own arguments; ignore them.
        # Keep the font cache across launches instead of rescanning every font.
        import hashlib
        mpl_cache = os.path.join(
            os.path.expanduser("~"), "Library", "Caches", "SignLingo",
            "matplotlib-" + hashlib.sha1(sys._MEIPASS.encode()).hexdigest()[:12],
        )
        os.makedirs(mpl_cache, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = mpl_cache
    # Preserve the existing packaged OpenCV path behavior (no sys.path edits).
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base)
    try:
        # Menu/settings do not need camera access. Ask only after a mode is chosen.
        while True:
            selected_mode = choose_mode()
            if selected_mode is None:
                return 0
            if not wait_for_camera():
                show_message("SignLingo can't use the camera. Allow camera access in your system "
                             "privacy settings and close other camera apps, then try again.")
                continue
            runpy.run_module(selected_mode, run_name="__main__")
    except SystemExit:
        raise  # Native close in a mode quits the app; do not reopen the menu.
    except Exception:
        traceback.print_exc()
        show_message("SignLingo hit an error. Details are in SignLingo-log.txt in your home folder.")
        return 1
    finally:
        try:
            camera.close_camera()
        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
