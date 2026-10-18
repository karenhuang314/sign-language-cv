"""Small shared lifecycle helpers for the OpenCV practice windows."""

from contextlib import contextmanager

import cv2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from signlingo.paths import MODEL_PATH
from signlingo.settings_ui import window_is_open

WINDOW_NAME = "SignLingo"


def require_open_window():
    # ESC/Main Menu return to the launcher; the native close button quits it.
    if not window_is_open(WINDOW_NAME):
        raise SystemExit(0)


@contextmanager
def mode_camera():
    """Release both native resources even on window close or inference errors."""
    landmarker = cap = None
    try:
        landmarker = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
            )
        )
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Could not open the camera. Check camera permissions and close other camera apps.")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # A hint; some camera backends ignore it.
        yield landmarker, cap
    finally:
        try:
            if cap is not None:
                cap.release()
        finally:
            try:
                if landmarker is not None:
                    landmarker.close()
            finally:
                cv2.destroyAllWindows()
