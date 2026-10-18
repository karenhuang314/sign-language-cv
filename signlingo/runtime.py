"""Small shared lifecycle helpers for the OpenCV practice windows."""

from contextlib import contextmanager

import cv2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from signlingo import camera
from signlingo.paths import MODEL_PATH
from signlingo.settings_ui import window_is_open

WINDOW_NAME = "SignLingo"


def require_open_window():
    # ESC/Main Menu return to the launcher; the native close button quits it.
    if not window_is_open(WINDOW_NAME):
        raise SystemExit(0)


@contextmanager
def mode_camera():
    """Reuse the launcher's camera; release everything on close or failure.

    Returning to the menu keeps its camera/window alive for faster startup.
    Standalone modes own their camera and release it on normal exit, too.
    """
    reuse_camera = camera.is_open()
    keep_open = False
    landmarker = None
    try:
        landmarker = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
            )
        )
        cap = camera.open_camera()
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera. Check camera permissions and close other camera apps.")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # A hint; some camera backends ignore it.
        yield landmarker, cap
        keep_open = reuse_camera
    finally:
        try:
            if landmarker is not None:
                landmarker.close()
        except BaseException:
            keep_open = False
            raise
        finally:
            if not keep_open:
                try:
                    camera.close_camera()
                finally:
                    cv2.destroyAllWindows()
