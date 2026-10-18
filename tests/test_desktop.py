"""Camera-free tests. Use the desktop environment: python -m unittest discover tests"""

import importlib.util
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from signlingo.practice import PracticeController

HAS_QT = importlib.util.find_spec('PySide6') is not None
if HAS_QT:
    import numpy as np
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from signlingo.camera_worker import CameraWorker, FrameMailbox
    from signlingo.recognition import FrameResult, RecognitionEngine, load_examples
    from signlingo.window import SignLingoWindow
    from signlingo.camera_window import CameraWindow


class PracticeTests(unittest.TestCase):
    def setUp(self):
        self.game = PracticeController(('B', 'J', 'L', 'Z'))
        self.game.reset('B')

    def test_hold_requires_time_and_samples(self):
        self.assertFalse(self.game.observe('B', False, 0))
        self.assertFalse(self.game.observe('B', False, .3))
        self.assertTrue(self.game.observe('B', False, .65))
        self.assertEqual(self.game.score, 1)

    def test_gaps_and_wrong_letters_reset_hold(self):
        self.game.observe('B', False, 0)
        self.assertFalse(self.game.observe('B', False, 1))
        self.game.observe('L', False, 1.1)
        self.assertFalse(self.game.observe('B', False, 1.2))
        self.assertEqual(self.game.progress(2), 0)

    def test_held_letter_counts_only_once_until_release(self):
        for now in (0, .3, .65, .9, 2.3, 2.6, 3):
            self.game.observe('B', False, now)
        self.assertEqual(self.game.score, 1)
        self.game.observe(None, False, 3.1)
        for now in (3.2, 3.5, 3.85):
            self.game.observe('B', False, now)
        self.assertEqual(self.game.score, 2)

    def test_motion_requires_new_completion(self):
        self.game.reset('J')
        self.assertFalse(self.game.observe('J', False, 0))
        self.assertTrue(self.game.observe('J', True, .1))
        self.assertFalse(self.game.observe('J', True, .2))
        self.assertEqual(self.game.score, 1)

    def test_skip_focus_random_and_invalid_target(self):
        self.game.skip()
        self.assertEqual(self.game.target, 'B')
        self.game.reset()
        target = self.game.target
        self.game.skip()
        self.assertNotEqual(target, self.game.target)
        with self.assertRaises(ValueError):
            self.game.reset('BAD')
        with self.assertRaises(ValueError):
            PracticeController(())


class FakeDetector:
    def __init__(self):
        self.closed = False
        self.timestamps = []
        self.hand = None

    def detect_for_video(self, image, timestamp):
        self.timestamps.append(timestamp)
        return SimpleNamespace(hand_landmarks=[self.hand] if self.hand else [])

    def close(self):
        self.closed = True


@unittest.skipUnless(HAS_QT, 'Install requirements-desktop.txt for desktop integration tests')
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('SignLingoTests')
        cls.app.setApplicationName('SignLingoTests')

    def result(self, letter=None, event=False):
        return FrameResult(np.zeros((48, 64, 3), dtype=np.uint8), letter, 0,
                           letter is not None, event, 'motion' if letter else 'none', time.monotonic())

    def test_mailbox_keeps_latest_without_losing_motion_completion(self):
        box = FrameMailbox()
        box.publish(self.result('J', True))
        box.publish(self.result('J', False))
        result = box.take()
        self.assertTrue(result.motion_event)
        self.assertIsNone(box.take())
        box.publish(self.result('J', True))
        box.publish(self.result())
        self.assertIsNone(box.take().letter)

    def test_engine_colors_mirror_timestamps_and_close(self):
        detector = FakeDetector()
        engine = RecognitionEngine([], lambda: detector)
        try:
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            frame[:, 0] = [0, 0, 255]  # BGR red → RGB red, right side after mirroring.
            result = engine.process(frame, 1)
            np.testing.assert_array_equal(result.rgb[0, -1], [255, 0, 0])
            self.assertFalse(result.hand_detected)
            engine.process(frame, 1)
            self.assertEqual(detector.timestamps, [1000, 1001])
            with patch.object(engine, 'reset_motion', wraps=engine.reset_motion) as reset:
                engine.process(frame, 3)
                reset.assert_called_once()
        finally:
            engine.close()
        self.assertTrue(detector.closed)

    def test_static_and_motion_override(self):
        detector = FakeDetector()
        detector.hand = [SimpleNamespace(x=i*.01, y=i*.02) for i in range(21)]
        engine = RecognitionEngine([], lambda: detector)
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        try:
            with patch('signlingo.recognition.guess_letter', return_value=('B', .8)):
                self.assertEqual(engine.process(frame, 1).letter, 'B')
                with patch.object(engine.motion, 'update', return_value='J'):
                    self.assertTrue(engine.process(frame, 1.1).motion_event)
                    self.assertFalse(engine.process(frame, 1.2).motion_event)
        finally:
            engine.close()

    def test_camera_failure_releases_model_and_capture(self):
        detector = FakeDetector()
        capture = SimpleNamespace(isOpened=lambda: False, release=lambda: setattr(detector, 'released', True))
        errors = []
        worker = CameraWorker([], FrameMailbox(), capture_factory=lambda _: capture,
                              engine_factory=lambda _: SimpleNamespace(close=detector.close))
        worker.failed.connect(errors.append)
        with self.assertLogs(level='ERROR'):
            worker.run()
        self.assertTrue(errors)
        self.assertTrue(detector.closed)
        self.assertTrue(detector.released)

    def test_worker_cleans_up_after_successful_stop(self):
        marker = SimpleNamespace(released=False, closed=False)
        box = FrameMailbox()
        def process(*args):
            worker.stop()
            return self.result()
        engine = SimpleNamespace(process=process, close=lambda: setattr(marker, 'closed', True))
        capture = SimpleNamespace(isOpened=lambda: True, set=lambda *args: True,
                                  read=lambda: (True, np.zeros((48, 64, 3), dtype=np.uint8)),
                                  release=lambda: setattr(marker, 'released', True))
        worker = CameraWorker([], box, capture_factory=lambda _: capture, engine_factory=lambda _: engine)
        worker.run()
        self.assertTrue(marker.closed and marker.released)
        self.assertIsNotNone(box.take())

    def test_ui_idle_practice_and_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.Format.IniFormat)
            window = SignLingoWindow([{'letter': 'B', 'numbers': [0]*42}], settings=settings)
            try:
                window.show()
                self.app.processEvents()
                self.assertIn('SignLingo', window.windowTitle())
                self.assertIsNone(window.worker)  # Never silently open a webcam.
                window.mode.setCurrentText('Letter practice')
                window.focus.setCurrentText('B')
                self.assertEqual(window.practice.target, 'B')
                window.mailbox.publish(self.result('B'))
                window._poll()
                self.assertEqual(window.detected.text(), 'B')
                window.low_power.setChecked(True)
            finally:
                window.close()
                self.app.processEvents()
            self.assertTrue(settings.value('camera/low_power', False, type=bool))

    def test_camera_window_overlay_and_sidebar(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.Format.IniFormat)
            window = CameraWindow([{'letter': 'B', 'numbers': [0]*42}], settings=settings)
            try:
                window.show()
                self.app.processEvents()
                self.assertIsNone(window.worker)  # Never silently open a webcam.
                self.assertFalse(window.sidebar.isVisible())
                self.assertTrue(window.big_start.isVisible())
                window.gear.click()
                self.assertTrue(window.sidebar.isVisible())
                window.focus.setCurrentText('B')
                window.mailbox.publish(self.result('B'))
                window._poll()
                self.assertEqual(window.detected.text(), 'B')
                self.assertIn(('big', 'Make: B'), [(k, t) for k, t, _ in window.camera_view.overlay])
                window.mode.setCurrentText('Live recognition')
                window._poll()
                self.assertNotIn('Make: B', [t for _, t, _ in window.camera_view.overlay])
            finally:
                window.close()
                self.app.processEvents()

    def test_data_loads_outside_project_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertGreater(len(load_examples()), 0)
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
