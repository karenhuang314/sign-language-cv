"""Local frame recognition; no Qt, web server, or camera capture side effects."""

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .features import FINGERTIPS, guess_letter, hand_to_numbers, load_all_examples
from .motion_recognition import MotionRecognizer
from .paths import DATA_DIR, MODEL_PATH

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
    (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


def load_examples():
    examples = load_all_examples(verbose=False, data_dir=str(DATA_DIR))
    if not examples:
        raise RuntimeError("No compatible examples found in the bundled data folder.")
    return examples


@dataclass
class FrameResult:
    rgb: np.ndarray
    letter: str | None
    agreement: float
    hand_detected: bool
    motion_event: bool
    source: str
    timestamp: float


class RecognitionEngine:
    """Create, use, and close this object in the camera worker's thread."""

    def __init__(self, examples, detector_factory=None):
        self.examples = examples
        self.motion = MotionRecognizer()
        self.last_motion = None
        self.last_timestamp = -1
        self.last_frame_time = None
        self.last_mirror = None
        self.detector = (detector_factory or self._create_detector)()

    @staticmethod
    def _create_detector():
        model = MODEL_PATH
        if not model.is_file():
            raise FileNotFoundError(f"Hand model missing: {model}")
        return vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(model)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
            )
        )

    def reset_motion(self):
        self.motion = MotionRecognizer()
        self.last_motion = None

    def close(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None

    def process(self, bgr, now, mirror=True, show_landmarks=True):
        if self.detector is None:
            raise RuntimeError("The recognition engine has been closed.")
        if (self.last_frame_time is not None and now - self.last_frame_time > 0.6
                or self.last_mirror is not None and mirror != self.last_mirror):
            self.reset_motion()
        self.last_frame_time = now
        self.last_mirror = mirror
        height, width = bgr.shape[:2]
        scale = min(1.0, 640 / width, 480 / height)
        if scale < 1:
            bgr = cv2.resize(bgr, (round(width * scale), round(height * scale)))
        if mirror:
            bgr = cv2.flip(bgr, 1)
        rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        height, width = rgb.shape[:2]
        timestamp_ms = max(self.last_timestamp + 1, int(now * 1000))
        self.last_timestamp = timestamp_ms
        result = self.detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms
        )
        hand = result.hand_landmarks[0] if result.hand_landmarks else None
        letter, agreement = (None, 0.0)
        if hand is not None:
            letter, agreement = guess_letter(hand_to_numbers(hand), self.examples)
        motion = self.motion.update(hand, now, width / height)
        motion_event = motion is not None and motion != self.last_motion
        self.last_motion = motion
        source = "motion" if motion else "static" if letter else "none"
        if motion:
            letter, agreement = motion, 0.0
        if hand is not None and show_landmarks:
            points = [(int(p.x * width), int(p.y * height)) for p in hand]
            for start, end in HAND_CONNECTIONS:
                cv2.line(rgb, points[start], points[end], (170, 208, 212), 2)
            for index, point in enumerate(points):
                color = (255, 190, 95) if index in FINGERTIPS else (65, 220, 170)
                cv2.circle(rgb, point, 4, color, -1)
        return FrameResult(rgb, letter, agreement, hand is not None,
                           motion_event, source, now)
