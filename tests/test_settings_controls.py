"""Settings, both modes, and window-close behavior without using a webcam."""

from contextlib import ExitStack
import importlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

import main as launcher
from signlingo import camera, menu_button, runtime, ui
from signlingo.settings import SettingsStore
from signlingo.settings_ui import SettingsPanel, limit_frame_rate, window_is_open


class SettingsTests(unittest.TestCase):
    def test_defaults_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            store = SettingsStore(path)
            self.assertFalse(store.values.low_power)
            self.assertTrue(store.values.show_landmarks)
            self.assertTrue(store.values.selfie)
            for key in ('low_power', 'show_landmarks', 'selfie'):
                store.toggle(key)
            restored = SettingsStore(path)
            self.assertTrue(restored.values.low_power)
            self.assertFalse(restored.values.show_landmarks)
            self.assertFalse(restored.values.selfie)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_invalid_values_do_not_enable_options(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text(json.dumps({'low_power': 'false', 'selfie': False, 'show_landmarks': 0}))
            store = SettingsStore(path)
            self.assertFalse(store.values.low_power)
            self.assertFalse(store.values.selfie)
            self.assertTrue(store.values.show_landmarks)
            with self.assertRaises(ValueError):
                store.toggle('invalid')

    def test_save_failure_keeps_session_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / 'settings.json')
            with patch.object(Path, 'mkdir', side_effect=PermissionError), self.assertLogs(level='ERROR'):
                store.toggle('low_power')
            self.assertTrue(store.values.low_power)
            self.assertTrue(store.error)

    def test_keyboard_and_mouse_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / 'settings.json')
            panel = SettingsPanel(store)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            panel.draw(frame)
            x1, y1, x2, y2 = panel.gear_rect
            panel.on_mouse(cv2.EVENT_LBUTTONDOWN, (x1+x2)//2, (y1+y2)//2)
            self.assertTrue(panel.is_open)
            panel.draw(frame)
            key, rect = panel.row_rects[0]
            panel.on_mouse(cv2.EVENT_LBUTTONDOWN, rect[0]+4, rect[1]+4)
            self.assertTrue(store.values.low_power)
            self.assertTrue(panel.handle_key(ord('2')))
            self.assertFalse(store.values.show_landmarks)
            self.assertTrue(panel.handle_key(ord('3')))
            self.assertFalse(store.values.selfie)
            self.assertTrue(panel.handle_key(27))
            self.assertFalse(panel.is_open)
            self.assertFalse(panel.handle_key(ord('1')))

    def test_popup_consumes_main_menu_clicks(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = SettingsPanel(SettingsStore(Path(directory) / 'settings.json'))
            panel.is_open = True
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            with patch.object(cv2, 'namedWindow'), patch.object(cv2, 'setMouseCallback'):
                menu_button.install('SignLingo', panel)
            menu_button.draw_menu_button(frame)
            panel.draw(frame)
            x1, y1, _, _ = menu_button.MENU_BUTTON['rect']
            menu_button.on_mouse(cv2.EVENT_LBUTTONDOWN, x1+5, y1+5, 0, None)
            self.assertFalse(menu_button.MENU_BUTTON['clicked'])

    def test_main_menu_and_gear_have_separate_hit_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            for width, height in ((640, 480), (1280, 720)):
                with self.subTest(size=(width, height)):
                    panel = SettingsPanel(SettingsStore(Path(directory) / 'settings.json'))
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                    with patch.object(cv2, 'setMouseCallback'):
                        menu_button.install(settings_panel=panel)
                    menu_button.draw_menu_button(frame)
                    panel.draw(frame)
                    mx1, my1, mx2, my2 = menu_button.MENU_BUTTON['rect']
                    gx1, gy1, gx2, gy2 = panel.gear_rect
                    self.assertLess(mx2, gx1)
                    menu_button.on_mouse(cv2.EVENT_LBUTTONDOWN, (gx1+gx2)//2, (gy1+gy2)//2, 0, None)
                    self.assertTrue(panel.is_open)
                    self.assertFalse(menu_button.MENU_BUTTON['clicked'])
                    panel.toggle_open()
                    menu_button.on_mouse(cv2.EVENT_LBUTTONDOWN, (mx1+mx2)//2, (my1+my2)//2, 0, None)
                    self.assertTrue(menu_button.MENU_BUTTON['clicked'])

    def test_frame_rate_limiter(self):
        with patch('signlingo.settings_ui.time.monotonic', return_value=10.04), \
                patch('signlingo.settings_ui.time.sleep') as sleep:
            limit_frame_rate(10, False)
            sleep.assert_not_called()
            limit_frame_rate(10, True)
            self.assertAlmostEqual(sleep.call_args.args[0], 1/12-.04)


class LifecycleTests(unittest.TestCase):
    def test_closed_and_destroyed_windows_are_detected(self):
        with patch.object(cv2, 'getWindowProperty', return_value=0):
            self.assertFalse(window_is_open())
            with self.assertRaises(SystemExit) as stopped:
                runtime.require_open_window()
            self.assertEqual(stopped.exception.code, 0)
        with patch.object(cv2, 'getWindowProperty', side_effect=cv2.error('window gone')):
            self.assertFalse(window_is_open())

    def test_menu_close_does_not_wait_for_a_key(self):
        with patch.object(cv2, 'namedWindow'), patch.object(cv2, 'setWindowProperty'), \
                patch.object(cv2, 'setMouseCallback'), patch.object(cv2, 'imshow'), \
                patch.object(cv2, 'destroyAllWindows') as destroy, \
                patch.object(cv2, 'waitKey', return_value=255) as wait, \
                patch.object(cv2, 'getWindowProperty', return_value=0):
            self.assertIsNone(launcher.choose_mode())
            wait.assert_called_with(30)
            destroy.assert_called_once()

    def test_settings_keys_cannot_accidentally_start_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = SettingsPanel(SettingsStore(Path(directory) / 'settings.json'))
            with patch.object(launcher, 'SettingsPanel', return_value=panel), \
                    patch.object(cv2, 'namedWindow'), patch.object(cv2, 'setWindowProperty'), \
                    patch.object(cv2, 'setMouseCallback'), patch.object(cv2, 'imshow'), \
                    patch.object(cv2, 'destroyAllWindows'), \
                    patch.object(cv2, 'waitKey', side_effect=[ord(','), ord('1'), 27, ord('2')]), \
                    patch.object(cv2, 'getWindowProperty', return_value=1):
                self.assertEqual(launcher.choose_mode(), 'signlingo.words')
                self.assertTrue(panel.store.values.low_power)

    def test_menu_click_targets_follow_full_screen_layout(self):
        for size in ((640, 480), (1280, 720)):
            for offset, expected in ((20, 'signlingo.practice'), (110, 'signlingo.words')):
                with self.subTest(size=size, mode=expected), \
                        patch.object(ui, 'screen_size', return_value=size), \
                        patch.object(cv2, 'namedWindow'), \
                        patch.object(cv2, 'setWindowProperty') as fullscreen, \
                        patch.object(cv2, 'setMouseCallback') as mouse, \
                        patch.object(cv2, 'imshow'), \
                        patch.object(cv2, 'getWindowProperty', return_value=1), \
                        patch.object(cv2, 'destroyAllWindows') as destroy:
                    def click_mode(_delay):
                        mouse.call_args.args[1](cv2.EVENT_LBUTTONDOWN, size[0]//2,
                                                size[1]//2 + offset, 0, None)
                        return 255
                    with patch.object(cv2, 'waitKey', side_effect=click_mode):
                        self.assertEqual(launcher.choose_mode(), expected)
                    fullscreen.assert_called_once_with(ui.WINDOW, cv2.WND_PROP_FULLSCREEN,
                                                       cv2.WINDOW_FULLSCREEN)
                    destroy.assert_not_called()  # The window carries into the mode.

    def test_closing_menu_never_opens_camera(self):
        with patch.object(launcher, 'choose_mode', return_value=None), \
                patch.object(launcher, 'wait_for_camera') as camera, \
                patch.object(cv2, 'destroyAllWindows'):
            self.assertEqual(launcher.main(), 0)
            camera.assert_not_called()

    def test_native_mode_close_quits_instead_of_reopening_menu(self):
        with patch.object(launcher, 'choose_mode', return_value='signlingo.words') as menu, \
                patch.object(launcher, 'wait_for_camera', return_value=True), \
                patch.object(launcher.runpy, 'run_module', side_effect=SystemExit(0)), \
                patch.object(cv2, 'destroyAllWindows'):
            with self.assertRaises(SystemExit):
                launcher.main()
            menu.assert_called_once()

    def test_resources_are_closed_when_a_mode_exits(self):
        cap, detector = Mock(), Mock()
        cap.isOpened.return_value = True
        with patch.object(cv2, 'VideoCapture', return_value=cap), \
                patch.object(runtime.vision.HandLandmarker, 'create_from_options', return_value=detector), \
                patch.object(cv2, 'destroyAllWindows') as destroy:
            with self.assertRaises(SystemExit):
                with runtime.mode_camera():
                    raise SystemExit(0)
            cap.release.assert_called_once()
            detector.close.assert_called_once()
            destroy.assert_called_once()

    def test_modes_reuse_launchers_camera_until_app_exit(self):
        cap = Mock()
        cap.isOpened.return_value = True
        detectors = [Mock(), Mock()]
        with patch.object(cv2, 'VideoCapture', return_value=cap) as capture, \
                patch.object(runtime.vision.HandLandmarker, 'create_from_options', side_effect=detectors), \
                patch.object(cv2, 'destroyAllWindows') as destroy:
            try:
                self.assertIs(camera.open_camera(), cap)  # Launcher permission check.
                for detector in detectors:
                    with runtime.mode_camera() as (actual_detector, actual_cap):
                        self.assertIs(actual_cap, cap)
                        self.assertIs(actual_detector, detector)
                    detector.close.assert_called_once()
                    cap.release.assert_not_called()
                capture.assert_called_once_with(0)
                destroy.assert_not_called()
                with patch.object(launcher, 'choose_mode', return_value=None):
                    self.assertEqual(launcher.main(), 0)
                cap.release.assert_called_once()
                self.assertFalse(camera.is_open())
                destroy.assert_called_once()
            finally:
                camera.close_camera()

    def test_native_close_or_error_releases_shared_camera(self):
        for error in (SystemExit(0), RuntimeError('inference failed')):
            with self.subTest(error=type(error).__name__):
                cap, detector = Mock(), Mock()
                cap.isOpened.return_value = True
                with patch.object(cv2, 'VideoCapture', return_value=cap), \
                        patch.object(runtime.vision.HandLandmarker, 'create_from_options', return_value=detector), \
                        patch.object(cv2, 'destroyAllWindows') as destroy:
                    camera.open_camera()
                    with self.assertRaises(type(error)):
                        with runtime.mode_camera():
                            raise error
                    cap.release.assert_called_once()
                    detector.close.assert_called_once()
                    destroy.assert_called_once()
                    self.assertFalse(camera.is_open())

    def test_model_initialization_failure_releases_shared_camera(self):
        cap = Mock()
        cap.isOpened.return_value = True
        with patch.object(cv2, 'VideoCapture', return_value=cap), \
                patch.object(runtime.vision.HandLandmarker, 'create_from_options',
                             side_effect=RuntimeError('model failed')), \
                patch.object(cv2, 'destroyAllWindows') as destroy:
            camera.open_camera()
            with self.assertRaises(RuntimeError):
                with runtime.mode_camera():
                    self.fail('A failed model must not enter the mode')
            cap.release.assert_called_once()
            destroy.assert_called_once()
            self.assertFalse(camera.is_open())

    def test_model_cleanup_failure_still_releases_shared_camera(self):
        cap, detector = Mock(), Mock()
        cap.isOpened.return_value = True
        detector.close.side_effect = RuntimeError('cleanup failed')
        with patch.object(cv2, 'VideoCapture', return_value=cap), \
                patch.object(runtime.vision.HandLandmarker, 'create_from_options', return_value=detector), \
                patch.object(cv2, 'destroyAllWindows') as destroy:
            camera.open_camera()
            with self.assertRaises(RuntimeError):
                with runtime.mode_camera():
                    pass
            cap.release.assert_called_once()
            destroy.assert_called_once()
            self.assertFalse(camera.is_open())


class ModeIntegrationTests(unittest.TestCase):
    def run_one_frame(self, mode, store, close=False):
        module = importlib.import_module('signlingo.' + mode)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, 0] = [0, 0, 255]
        hand = [SimpleNamespace(x=.01*i, y=.02*i) for i in range(21)]
        detector = Mock()
        detector.detect_for_video.return_value = SimpleNamespace(hand_landmarks=[hand])
        cap = Mock()
        cap.isOpened.return_value = True
        cap.read.return_value = (True, frame.copy())
        with ExitStack() as stack:
            stack.enter_context(patch.object(module, 'get_settings', return_value=store))
            stack.enter_context(patch.object(ui, 'screen_size', return_value=(640, 480)))
            fit = stack.enter_context(patch.object(ui, 'fit', wraps=ui.fit))
            sign_card = stack.enter_context(patch.object(ui, 'sign_card', wraps=ui.sign_card))
            stack.enter_context(patch.object(module.sys if mode == 'practice' else launcher.sys, 'argv', ['main.py']))
            stack.enter_context(patch.object(cv2, 'VideoCapture', return_value=cap))
            stack.enter_context(patch.object(runtime.vision.HandLandmarker, 'create_from_options', return_value=detector))
            for method in ('namedWindow', 'setWindowProperty', 'setMouseCallback', 'imshow', 'destroyAllWindows'):
                stack.enter_context(patch.object(cv2, method))
            stack.enter_context(patch.object(cv2, 'waitKey', return_value=255 if close else 27))
            stack.enter_context(patch.object(cv2, 'getWindowProperty', side_effect=[1, 1, 0] if close else None,
                                            return_value=1))
            guess = stack.enter_context(patch.object(module, 'guess_letter', return_value=('B', .8)))
            circles = stack.enter_context(patch.object(cv2, 'circle', wraps=cv2.circle))
            if close:
                with self.assertRaises(SystemExit) as stopped:
                    getattr(module, 'run_' + mode + '_mode')()
                self.assertEqual(stopped.exception.code, 0)
            else:
                getattr(module, 'run_' + mode + '_mode')()
            guess.assert_called_once()
            fit.assert_called_once()
            if mode == 'practice':
                sign_card.assert_called_once()  # Keep main's reference pictures.
            # Two circles for the gear; main's style uses one dot per landmark.
            self.assertEqual(circles.call_count, 2 + (21 if store.values.show_landmarks else 0))
            rgb = detector.detect_for_video.call_args.args[0].numpy_view()
            column = -1 if store.values.selfie else 0
            np.testing.assert_array_equal(rgb[0, column], [255, 0, 0])
        cap.release.assert_called_once()
        detector.close.assert_called_once()

    def test_options_and_native_close_work_in_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / 'settings.json')
            for mode in ('practice', 'words'):
                for enabled in (False, True):
                    with self.subTest(mode=mode, landmarks=enabled, selfie=enabled):
                        store.values.show_landmarks = enabled
                        store.values.selfie = enabled
                        self.run_one_frame(mode, store)
                with self.subTest(mode=mode, close=True):
                    self.run_one_frame(mode, store, close=True)


if __name__ == '__main__':
    unittest.main()
