"""SignLingo's camera-first look: the game is drawn on the video (like
practice.py), and every setting lives in a sidebar opened with the gear button.

It reuses Etinosa's SignLingoWindow for all the behavior (camera thread,
practice rules, scores, saved settings, shortcuts) and only changes the layout
and drawing. Build the window with CameraWindow(examples).
"""

import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from .features import MOTION_LETTERS
from .window import STYLE, SignLingoWindow, caption

WHITE, GREEN, YELLOW = QColor("#ffffff"), QColor("#22c55e"), QColor("#ffd23f")
ORANGE, RED, GRAY = QColor("#ff8c1a"), QColor("#ff4d4f"), QColor("#9aa4b2")

CAMERA_STYLE = STYLE + """
QLabel#camera { background: #000000; border-radius: 0px; }
QFrame#sidebar { background: #101b2b; border-left: 1px solid #2d405b; }
QLabel#sideTitle { font-size: 20px; font-weight: 800; color: #63dfb3; }
QToolButton#gear { background: rgba(0, 0, 0, 140); color: white; border: none;
                   border-radius: 22px; font-size: 24px; }
QToolButton#gear:hover { background: rgba(0, 0, 0, 200); }
"""


class CameraCanvas(QLabel):
    """Shows the camera picture, then draws the game on top of it."""

    def __init__(self, text):
        super().__init__(text)
        self.overlay = []      # list of (kind, text, color) drawn top to bottom
        self.footer = []       # small lines drawn at the bottom-left
        self.correct = False   # big "Correct!" in the middle
        self.progress = None   # 0-100 for the green bar, None to hide it

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap() is None or self.pixmap().isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Draw inside the area the video actually covers
        pm = self.pixmap()
        x0 = (self.width() - pm.width()) / 2
        y0 = (self.height() - pm.height()) / 2
        scale = max(pm.height() / 480, 0.6)   # text grows with the video
        left = x0 + 20 * scale
        y = y0 + 20 * scale

        if self.correct:
            size = 90 * scale
            font = QFont("Helvetica", int(size), QFont.Weight.Black)
            path = QPainterPath()
            path.addText(0, 0, font, "Correct!")
            box = path.boundingRect()
            path.translate(x0 + (pm.width() - box.width()) / 2 - box.left(),
                           y0 + (pm.height() + box.height()) / 2 - box.bottom())
            self._outlined(painter, path, GREEN, 8 * scale)
        else:
            for kind, text, color in self.overlay:
                size = {"big": 54, "medium": 30, "small": 20}[kind] * scale
                y += size
                self._text(painter, text, left, y, size, color, kind != "small")
                y += 10 * scale
                if kind == "big" and self.progress is not None:
                    bar = QRectF(left, y, 300 * scale, 18 * scale)
                    painter.setPen(QPen(QColor("#dddddd"), 2 * scale))
                    painter.setBrush(QColor(0, 0, 0, 120))
                    painter.drawRoundedRect(bar, 9 * scale, 9 * scale)
                    if self.progress > 0:
                        fill = QRectF(bar.left(), bar.top(), bar.width() * self.progress / 100, bar.height())
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(GREEN)
                        painter.drawRoundedRect(fill, 9 * scale, 9 * scale)
                    y += 28 * scale

        fy = y0 + pm.height() - 16 * scale
        for line in reversed(self.footer):
            self._text(painter, line, left, fy, 17 * scale, WHITE, False)
            fy -= 26 * scale
        painter.end()

    def _text(self, painter, text, x, y, size, color, bold):
        font = QFont("Helvetica", max(int(size), 8), QFont.Weight.Black if bold else QFont.Weight.DemiBold)
        path = QPainterPath()
        path.addText(QPointF(x, y), font, text)
        self._outlined(painter, path, color, max(size / 7, 2))

    @staticmethod
    def _outlined(painter, path, color, outline):
        painter.setPen(QPen(QColor(0, 0, 0, 220), outline, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)


class CameraWindow(SignLingoWindow):
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root.setStyleSheet(CAMERA_STYLE)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # The camera fills the window
        self.camera_view = CameraCanvas("Your camera is off.")
        self.camera_view.setObjectName("camera")
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_view.setMinimumSize(400, 300)
        self.camera_view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.camera_view.setAccessibleName("Live camera preview with practice feedback")
        layout.addWidget(self.camera_view, 1)

        # Floating buttons on top of the camera
        self.gear = QToolButton(self.camera_view)
        self.gear.setObjectName("gear")
        self.gear.setText("⚙")
        self.gear.setToolTip("Settings")
        self.gear.setFixedSize(44, 44)
        self.big_start = QPushButton("Start camera", self.camera_view)
        self.big_start.setObjectName("primary")
        self.big_start.setStyleSheet("font-size: 20px; padding: 14px 28px;")
        self.big_start.adjustSize()

        # Sidebar with every setting (hidden until the gear is clicked)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(300)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(20, 18, 20, 18)
        side.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("SignLingo")
        title.setObjectName("sideTitle")
        close = QToolButton()
        close.setText("✕")
        close.clicked.connect(lambda: self.sidebar.setVisible(False))
        top.addWidget(title)
        top.addStretch()
        top.addWidget(close)
        side.addLayout(top)

        self.mode = QComboBox()
        self.mode.addItems(["Letter practice", "Live recognition"])
        self.mode.setAccessibleName("Practice mode")
        self.focus = QComboBox()
        self.focus.addItems(["Random"] + list(self.practice.letters))
        self.focus.setAccessibleName("Target letter")
        side.addWidget(caption("Mode"))
        side.addWidget(self.mode)
        side.addWidget(caption("Letter to practice"))
        side.addWidget(self.focus)

        buttons = QHBoxLayout()
        self.skip_button = QPushButton("Skip")
        self.reset_button = QPushButton("Reset")
        buttons.addWidget(self.skip_button)
        buttons.addWidget(self.reset_button)
        side.addLayout(buttons)

        side.addWidget(caption("Camera"))
        camera_row = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("primary")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.camera_index = QSpinBox()
        self.camera_index.setRange(0, 10)
        self.camera_index.setValue(self.settings.value("camera/index", 0, type=int))
        self.camera_index.setToolTip("0 is usually the built-in camera. Try 1 for an external camera.")
        camera_row.addWidget(self.start_button)
        camera_row.addWidget(self.stop_button)
        camera_row.addWidget(self.camera_index)
        side.addLayout(camera_row)

        self.mirror = QCheckBox("Selfie view")
        self.mirror.setChecked(self.settings.value("camera/mirror", True, type=bool))
        self.landmarks = QCheckBox("Hand dots")
        self.landmarks.setChecked(self.settings.value("camera/landmarks", True, type=bool))
        self.low_power = QCheckBox("Low-power mode")
        self.low_power.setChecked(self.settings.value("camera/low_power", False, type=bool))
        for control in (self.mirror, self.landmarks, self.low_power):
            side.addWidget(control)

        side.addWidget(caption("What the app sees"))
        self.detected = QLabel("—")
        self.detected.setObjectName("detected")
        side.addWidget(self.detected)
        self.details = caption("Show one hand clearly in the camera.")
        side.addWidget(self.details)
        self.status = caption("Camera off • nothing is being captured")
        side.addWidget(self.status)
        side.addStretch()
        side.addWidget(caption("Keys: letter = practice that letter, 0 = random, "
                               "Space = skip, Esc = stop camera"))
        about = QPushButton("About")
        about.clicked.connect(self._about)
        side.addWidget(about)
        self.sidebar.setVisible(False)
        layout.addWidget(self.sidebar)

        self.gear.clicked.connect(lambda: self.sidebar.setVisible(not self.sidebar.isVisible()))
        self.big_start.clicked.connect(self.start_camera)

    def _camera_error(self, message):
        super()._camera_error(message)
        self.sidebar.setVisible(True)   # the error message is shown in the sidebar

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        self._place_buttons()

    def _place_buttons(self):
        view = self.camera_view
        self.gear.move(view.width() - self.gear.width() - 16, 16)
        self.big_start.move((view.width() - self.big_start.width()) // 2,
                            (view.height() - self.big_start.height()) // 2)

    def keyPressEvent(self, event):
        # Like practice.py: a letter key practices that letter, 0 goes back to random
        text = event.text().upper()
        if text in self.practice.letters:
            self.mode.setCurrentText("Letter practice")
            self.focus.setCurrentText(text)
        elif text == "0":
            self.mode.setCurrentText("Letter practice")
            self.focus.setCurrentText("Random")
        else:
            super().keyPressEvent(event)

    def _render_practice(self, now):
        practicing = self.mode.currentText() == "Letter practice"
        self.focus.setEnabled(practicing)
        self.skip_button.setEnabled(practicing)
        camera_on = self.worker is not None
        self.big_start.setVisible(not camera_on and not self.closing)
        self._place_buttons()

        view = self.camera_view
        seen = self.detected.text()
        hand = seen != "—"
        view.correct = practicing and bool(self.practice.correct_until) and now < self.practice.correct_until
        view.progress = None
        if practicing:
            target = self.practice.target
            view.overlay = [("big", f"Make: {target}", WHITE),
                            ("medium", f"I see: {seen if hand else '?'}", YELLOW)]
            view.progress = self.practice.progress(now)
            if target in MOTION_LETTERS:
                tip = "draw a J with your pinky" if target == "J" else "draw a Z with your index finger"
                view.overlay.append(("small", f"Move: {tip}", ORANGE))
            if self.practice.release_needed and not view.correct:
                view.overlay.append(("small", "Relax your hand before the next one", GRAY))
            if not hand:
                view.overlay.append(("small", "Show your hand", RED))
            focus = self.practice.focus
            score = f"Score: {self.practice.score}   All-time: {self.total_correct}"
            if focus != "Random":
                score = f"Focus {focus}   " + score
            view.footer = [score]
        else:
            if hand:
                view.overlay = [("big", f"Sign: {seen}", GREEN)]
            else:
                view.overlay = [("medium", "Show your hand", RED)]
            view.footer = ["Live mode"]
        view.footer.append("⚙ settings   letter key = focus   0 = random   SPACE = skip")
        view.update()
