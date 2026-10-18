"""Small OpenCV settings popup shared by the menu and both practice modes."""

import math
import time

import cv2

from signlingo.settings import get_settings


ROWS = (
    ("low_power", "Low-power mode", "Limit processing to about 12 FPS"),
    ("show_landmarks", "Show hand landmarks", "Off hides dots, not recognition"),
    ("selfie", "Selfie view", "Mirror the camera image"),
)


def window_is_open(name="SignLingo"):
    """A closed HighGUI window must not be recreated by the next imshow()."""
    try:
        return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


def limit_frame_rate(started, low_power):
    if low_power:
        time.sleep(max(0, 1 / 12 - (time.monotonic() - started)))


class SettingsPanel:
    def __init__(self, store=None):
        self.store = store if store is not None else get_settings()
        self.is_open = False
        self.revision = 0  # Opening/closing also invalidates pending sign evidence.
        self.gear_rect = None
        self.close_rect = None
        self.row_rects = []
        self.gear_hover = False

    @staticmethod
    def _inside(rect, x, y):
        return rect is not None and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def toggle_open(self):
        self.is_open = not self.is_open
        self.revision += 1

    def handle_key(self, key):
        if key == ord(","):
            self.toggle_open()
            return True
        if not self.is_open:
            return False
        if key == 27:
            self.toggle_open()
        elif key in (ord("1"), ord("2"), ord("3")):
            self.store.toggle(ROWS[key - ord("1")][0])
            self.revision += 1
        return True  # Modal: keys must not select a mode or focus behind the popup.

    def on_mouse(self, event, x, y, flags=0, param=None):
        self.gear_hover = self._inside(self.gear_rect, x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.gear_hover:
                self.toggle_open()
                return True
            if self.is_open:
                if self._inside(self.close_rect, x, y):
                    self.toggle_open()
                else:
                    for key, rect in self.row_rects:
                        if self._inside(rect, x, y):
                            self.store.toggle(key)
                            self.revision += 1
                            break
                return True
        return self.is_open or self.gear_hover

    def draw(self, frame):
        h, w = frame.shape[:2]
        self.gear_rect = (w - 54, 14, w - 14, 54)
        x1, y1, x2, y2 = self.gear_rect
        cv2.rectangle(frame, (x1, y1), (x2, y2), (63, 63, 70) if self.gear_hover else (39, 39, 42), -1)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        color = (255, 255, 255) if self.gear_hover else (190, 190, 200)
        for angle in range(0, 360, 45):
            a = math.radians(angle)
            cv2.line(frame, (int(cx + 10 * math.cos(a)), int(cy + 10 * math.sin(a))),
                     (int(cx + 14 * math.cos(a)), int(cy + 14 * math.sin(a))), color, 3, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 10, color, 2, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 4, color, 1, cv2.LINE_AA)
        if not self.is_open:
            return frame
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, .55, frame, .45, 0, frame)
        panel_w, panel_h = min(440, w - 24), 300
        left, top = (w - panel_w) // 2, max(8, (h - panel_h) // 2)
        right, bottom = left + panel_w, top + panel_h
        cv2.rectangle(frame, (left, top), (right, bottom), (24, 24, 27), -1)
        cv2.rectangle(frame, (left, top), (right, bottom), (90, 90, 100), 1)
        cv2.putText(frame, "SETTINGS", (left + 18, top + 31), cv2.FONT_HERSHEY_SIMPLEX,
                    .65, (255, 255, 255), 2, cv2.LINE_AA)
        self.close_rect = (right - 42, top + 8, right - 8, top + 40)
        cv2.putText(frame, "X", (right - 32, top + 31), cv2.FONT_HERSHEY_SIMPLEX,
                    .6, (190, 190, 200), 1, cv2.LINE_AA)
        self.row_rects = []
        for index, (key, label, description) in enumerate(ROWS):
            y = top + 53 + index * 65
            self.row_rects.append((key, (left + 10, y, right - 10, y + 59)))
            cv2.rectangle(frame, (left + 10, y), (right - 10, y + 59), (39, 39, 42), -1)
            cv2.putText(frame, f"[{index + 1}] {label}", (left + 20, y + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, description, (left + 20, y + 43), cv2.FONT_HERSHEY_SIMPLEX,
                        .37, (161, 161, 170), 1, cv2.LINE_AA)
            enabled = getattr(self.store.values, key)
            cv2.putText(frame, "ON" if enabled else "OFF", (right - 60, y + 29),
                        cv2.FONT_HERSHEY_SIMPLEX, .5,
                        (34, 197, 94) if enabled else (161, 161, 170), 2, cv2.LINE_AA)
        footer = self.store.error or "Click a row to toggle | ESC to close"
        cv2.putText(frame, footer, (left + 16, bottom - 17), cv2.FONT_HERSHEY_SIMPLEX,
                    .4, (161, 161, 170), 1, cv2.LINE_AA)
        return frame
