"""Camera capture in a QThread, with a latest-frame mailbox (no UI backlog)."""

import logging
import sys
import threading
import time

import cv2
from PySide6.QtCore import QThread, Signal

from .recognition import RecognitionEngine


class FrameMailbox:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = None

    def publish(self, result):
        with self._lock:
            # Preserve a one-shot completion while the same motion result is
            # held, even if the UI skips an intermediate frame. No event queue.
            if (self._latest is not None and self._latest.motion_event
                    and result.source == "motion" and result.letter == self._latest.letter):
                result.motion_event = True
            self._latest = result

    def take(self):
        with self._lock:
            result, self._latest = self._latest, None
            return result

    def clear(self):
        self.take()


class CameraWorker(QThread):
    status = Signal(str)
    failed = Signal(str)
    # The first time on a Mac, opening the camera fails while the "allow
    # camera?" prompt is up. Keep trying this long for the person to answer.
    PERMISSION_WAIT_SECONDS = 60 if sys.platform == "darwin" else 0
    PERMISSION_POLL_SECONDS = 1

    def __init__(self, examples, mailbox, camera_index=0, parent=None,
                 capture_factory=None, engine_factory=None):
        super().__init__(parent)
        self.examples = examples
        self.mailbox = mailbox
        self.camera_index = camera_index
        self.capture_factory = capture_factory or cv2.VideoCapture
        self.engine_factory = engine_factory or RecognitionEngine
        self._halt = threading.Event()
        self._reset = threading.Event()
        self._options_lock = threading.Lock()
        self._mirror = True
        self._landmarks = True
        self._low_power = False

    def set_options(self, mirror, landmarks, low_power):
        with self._options_lock:
            self._mirror, self._landmarks, self._low_power = mirror, landmarks, low_power

    def reset_tracking(self):
        self._reset.set()
        self.mailbox.clear()

    def stop(self):
        self._halt.set()
        self.requestInterruption()

    def _open_camera(self):
        """An open camera, or None if Stop was pressed while waiting."""
        deadline = time.monotonic() + self.PERMISSION_WAIT_SECONDS
        while True:
            camera = self.capture_factory(self.camera_index)
            if camera.isOpened():
                return camera
            camera.release()
            if self._halt.is_set():
                return None
            if time.monotonic() >= deadline:
                where = (" Allow it in System Settings > Privacy & Security > Camera,"
                         if sys.platform == "darwin" else " Check camera permissions,")
                raise RuntimeError(f"Could not open the camera.{where} close Zoom/Teams, "
                                   "or try another camera number.")
            self.status.emit("Waiting for camera access… click Allow if asked")
            self._halt.wait(self.PERMISSION_POLL_SECONDS)

    def run(self):
        camera = engine = None
        try:
            self.status.emit("Loading local hand model…")
            engine = self.engine_factory(self.examples)
            if self._halt.is_set():
                return
            self.status.emit("Opening camera…")
            camera = self._open_camera()
            if camera is None:
                return
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Backend may ignore this hint.
            self.status.emit("Camera ready • processing on this device")
            failures = 0
            while not self._halt.is_set():
                started = time.monotonic()
                ok, frame = camera.read()
                if not ok:
                    failures += 1
                    if failures >= 3:
                        raise RuntimeError("Camera stopped sending frames. Reconnect it and try again.")
                    self._halt.wait(.1)
                    continue
                failures = 0
                if self._halt.is_set():
                    break
                if self._reset.is_set():
                    self._reset.clear()
                    engine.reset_motion()
                with self._options_lock:
                    mirror, landmarks, low_power = self._mirror, self._landmarks, self._low_power
                result = engine.process(frame, time.monotonic(), mirror, landmarks)
                self.mailbox.publish(result)
                # Limit processing without accumulating capture or display requests.
                self._halt.wait(max(0, 1 / (12 if low_power else 24) - (time.monotonic() - started)))
        except Exception as error:
            logging.exception("SignLingo camera worker failed")
            self.failed.emit(str(error))
        finally:
            try:
                if camera is not None:
                    camera.release()
            finally:
                if engine is not None:
                    engine.close()
