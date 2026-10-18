"""
camera.py - the webcam, opened once and shared.

The menu opens the camera (to check permission) and leaves it open, so a
mode starts right away instead of waiting about a second for it to reopen.
"""

import cv2

_cap = None


def is_open():
    """Whether a caller (normally the launcher) already holds the webcam."""
    return _cap is not None and _cap.isOpened()


def open_camera():
    """The open webcam, opening it if needed."""
    global _cap
    if not is_open():
        close_camera()
        _cap = cv2.VideoCapture(0)
    return _cap


def close_camera():
    global _cap
    cap, _cap = _cap, None
    if cap is not None:
        cap.release()
