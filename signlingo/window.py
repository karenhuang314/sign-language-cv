"""SignLingo's Qt interface. All widget updates happen on the UI thread."""

import time

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget,
)

from .features import MOTION_LETTERS
from .camera_worker import CameraWorker, FrameMailbox
from .practice import PracticeController

STYLE = """
QWidget { background: #101b2b; color: #eaf1fa; font-size: 14px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 30px; font-weight: 800; color: #63dfb3; }
QLabel#muted { color: #a9b9cc; }
QLabel#target { font-size: 100px; font-weight: 800; color: #63dfb3; }
QLabel#detected { font-size: 44px; font-weight: 700; }
QFrame#card { background: #19283d; border: 1px solid #2d405b; border-radius: 16px; }
QLabel#camera { background: #080f1a; border-radius: 12px; color: #a9b9cc; }
QPushButton, QComboBox, QSpinBox {
    background: #263a54; border: 1px solid #3a526f; border-radius: 7px;
    padding: 9px 12px; min-height: 20px;
}
QPushButton:hover { background: #334d6c; }
QPushButton#primary { background: #60dcb0; color: #0d241c; font-weight: 700; }
QPushButton:disabled { color: #7c8b9e; background: #1d2c40; }
QComboBox QAbstractItemView { background: #263a54; selection-background-color: #3a526f; }
QProgressBar { border: none; background: #0e1a2b; border-radius: 6px; min-height: 12px; }
QProgressBar::chunk { background: #60dcb0; border-radius: 6px; }
QCheckBox { spacing: 8px; }
"""


def caption(text):
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


class SignLingoWindow(QMainWindow):
    def __init__(self, examples, settings=None, worker_factory=CameraWorker):
        super().__init__()
        self.setWindowTitle("SignLingo — Fingerspelling Practice")
        self.resize(1120, 790)
        self.setMinimumSize(940, 690)
        self.settings = settings if settings is not None else QSettings()
        self.examples = examples
        self.practice = PracticeController({e["letter"] for e in examples} | set(MOTION_LETTERS))
        self.worker_factory = worker_factory
        self.worker = None
        self.mailbox = FrameMailbox()
        self.closing = False
        self.ignore_before = 0.0
        self.last_result_time = None
        self.total_correct = self.settings.value("progress/total_correct", 0, type=int)
        self._build_ui()
        self._connect()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(33)
        self._render_practice(time.monotonic())

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root.setStyleSheet(STYLE)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 22, 26, 18)
        layout.setSpacing(16)
        header = QHBoxLayout()
        brand = QLabel("SignLingo")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(caption("LOCAL PROCESSING  •  NO ACCOUNT NEEDED"))
        layout.addLayout(header)
        layout.addWidget(caption("Find your flow. One letter at a time."))

        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Live recognition", "Letter practice"])
        self.mode.setAccessibleName("Practice mode")
        self.focus = QComboBox()
        self.focus.addItems(["Random"] + list(self.practice.letters))
        self.focus.setAccessibleName("Target letter")
        self.camera_index = QSpinBox()
        self.camera_index.setRange(0, 10)
        self.camera_index.setValue(self.settings.value("camera/index", 0, type=int))
        self.camera_index.setAccessibleName("Camera number")
        self.camera_index.setToolTip("0 is usually the built-in camera. Try 1 for an external camera.")
        self.start_button = QPushButton("Start camera")
        self.start_button.setObjectName("primary")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        controls.addWidget(self.mode)
        controls.addWidget(caption("Target"))
        controls.addWidget(self.focus)
        controls.addStretch()
        controls.addWidget(caption("Camera"))
        controls.addWidget(self.camera_index)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        content = QHBoxLayout()
        camera_card = QFrame()
        camera_card.setObjectName("card")
        camera_layout = QVBoxLayout(camera_card)
        camera_layout.setContentsMargins(14, 14, 14, 14)
        self.camera_view = QLabel("Your camera is off.\nClick Start camera when you are ready.")
        self.camera_view.setObjectName("camera")
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_view.setMinimumSize(400, 300)
        self.camera_view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.camera_view.setAccessibleName("Live camera preview with hand landmarks")
        camera_layout.addWidget(self.camera_view, 1)
        self.status = caption("Camera off • nothing is being captured")
        camera_layout.addWidget(self.status)
        content.addWidget(camera_card, 3)

        target_card = QFrame()
        target_card.setObjectName("card")
        target_card.setMinimumWidth(270)
        target_layout = QVBoxLayout(target_card)
        target_layout.setContentsMargins(24, 22, 24, 22)
        self.target_heading = caption("EXPLORE THE ALPHABET")
        self.target_label = QLabel("LIVE")
        self.target_label.setObjectName("target")
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hold_progress = QProgressBar()
        self.hold_progress.setRange(0, 100)
        self.hold_progress.setTextVisible(False)
        target_layout.addWidget(self.target_heading)
        target_layout.addStretch()
        target_layout.addWidget(self.target_label)
        target_layout.addWidget(self.instruction)
        target_layout.addWidget(self.hold_progress)
        target_layout.addStretch()
        self.score_label = caption("")
        target_layout.addWidget(self.score_label)
        content.addWidget(target_card, 2)
        layout.addLayout(content, 1)

        result_row = QHBoxLayout()
        result_row.addWidget(caption("DETECTED"))
        self.detected = QLabel("—")
        self.detected.setObjectName("detected")
        result_row.addWidget(self.detected)
        self.details = caption("Show one hand clearly in the camera.")
        result_row.addWidget(self.details, 1)
        self.skip_button = QPushButton("Skip · Space")
        self.reset_button = QPushButton("Reset session")
        result_row.addWidget(self.skip_button)
        result_row.addWidget(self.reset_button)
        layout.addLayout(result_row)

        preferences = QHBoxLayout()
        self.mirror = QCheckBox("Selfie view")
        self.mirror.setChecked(self.settings.value("camera/mirror", True, type=bool))
        self.landmarks = QCheckBox("Hand landmarks")
        self.landmarks.setChecked(self.settings.value("camera/landmarks", True, type=bool))
        self.low_power = QCheckBox("Low-power mode")
        self.low_power.setChecked(self.settings.value("camera/low_power", False, type=bool))
        for control in (self.mirror, self.landmarks, self.low_power):
            preferences.addWidget(control)
        preferences.addStretch()
        about = QPushButton("About")
        about.clicked.connect(self._about)
        preferences.addWidget(about)
        layout.addLayout(preferences)
        layout.addWidget(caption("Fingerspelling practice, not a complete ASL course. "
                                 "J/Z recognition is experimental. Video stays on this device."))

    def _connect(self):
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.mode.currentTextChanged.connect(self.reset_session)
        self.focus.currentTextChanged.connect(self.reset_session)
        self.skip_button.clicked.connect(self.skip_target)
        self.reset_button.clicked.connect(self.reset_session)
        for control in (self.mirror, self.landmarks, self.low_power):
            control.toggled.connect(self._options_changed)
        self._shortcuts = []
        for key, callback in (("Space", self.skip_target), ("Escape", self.stop_camera),
                              ("Ctrl+R", self.reset_session)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _options_changed(self):
        if self.worker is not None:
            self.worker.set_options(self.mirror.isChecked(), self.landmarks.isChecked(),
                                    self.low_power.isChecked())
        self._clear_tracking()

    def _clear_tracking(self):
        self.ignore_before = time.monotonic()
        self.practice.clear_evidence()
        self.mailbox.clear()
        if self.worker is not None:
            self.worker.reset_tracking()

    def start_camera(self):
        if self.worker is not None or self.closing:
            return
        self._clear_tracking()
        self.worker = self.worker_factory(self.examples, self.mailbox,
                                          self.camera_index.value(), self)
        self.worker.set_options(self.mirror.isChecked(), self.landmarks.isChecked(),
                                self.low_power.isChecked())
        self.worker.status.connect(self.status.setText)
        self.worker.failed.connect(self._camera_error)
        self.worker.finished.connect(self._camera_finished)
        self.start_button.setEnabled(False)
        self.camera_index.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status.setText("Starting local recognition…")
        self.worker.start()

    def stop_camera(self):
        self._clear_tracking()
        self.practice.correct_until = 0
        self.last_result_time = None
        self.detected.setText("—")
        if self.worker is not None:
            self.status.setText("Stopping camera safely…")
            self.stop_button.setEnabled(False)
            self.worker.stop()

    def _camera_error(self, message):
        self.status.setText(message)
        self.camera_view.setPixmap(QPixmap())
        self.camera_view.setText("Camera unavailable\nCheck the message below and try again.")
        self.detected.setText("—")

    def _camera_finished(self):
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        self.mailbox.clear()
        self.practice.clear_evidence()
        self.last_result_time = None
        self.camera_index.setEnabled(True)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.detected.setText("—")
        if self.status.text().startswith("Stopping"):
            self.status.setText("Camera off • nothing is being captured")
            self.camera_view.setPixmap(QPixmap())
            self.camera_view.setText("Your camera is off.\nClick Start camera when you are ready.")
        if self.closing:
            self.close()

    def reset_session(self, *_):
        self.practice.reset(self.focus.currentText())
        self._clear_tracking()
        self._render_practice(time.monotonic())

    def skip_target(self):
        if self.mode.currentText() != "Letter practice":
            return
        self.practice.skip()
        self._clear_tracking()
        self._render_practice(time.monotonic())

    def _poll(self):
        now = time.monotonic()
        old_target = self.practice.target
        self.practice.advance(now)
        if self.practice.target != old_target:
            self._clear_tracking()
        result = self.mailbox.take()
        if result is not None and result.timestamp >= self.ignore_before:
            self.last_result_time = result.timestamp
            image = QImage(result.rgb.data, result.rgb.shape[1], result.rgb.shape[0],
                           result.rgb.strides[0], QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(image).scaled(
                self.camera_view.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.camera_view.setPixmap(pixmap)
            self.detected.setText(result.letter or ("?" if result.hand_detected else "—"))
            if result.source == "motion":
                detail = "Movement detected • experimental J/Z matching"
            elif result.letter:
                detail = f"Neighbor agreement: {result.agreement:.0%} (not an accuracy probability)"
            else:
                detail = "No close match. Try again." if result.hand_detected else "Show your hand clearly."
            self.details.setText(detail)
            if self.mode.currentText() == "Letter practice":
                if now - result.timestamp <= .6:
                    if self.practice.observe(result.letter, result.motion_event, result.timestamp):
                        self.total_correct += 1
                        self.settings.setValue("progress/total_correct", self.total_correct)
                else:
                    self.practice.clear_evidence()
        elif self.last_result_time is not None and now - self.last_result_time > .8:
            self.practice.clear_evidence()
            self.detected.setText("—")
            self.details.setText("Waiting for fresh camera frames…")
        self._render_practice(now)

    def _render_practice(self, now):
        practicing = self.mode.currentText() == "Letter practice"
        self.focus.setEnabled(practicing)
        self.skip_button.setEnabled(practicing)
        self.hold_progress.setVisible(practicing)
        self.target_heading.setText("YOUR NEXT LETTER" if practicing else "EXPLORE THE ALPHABET")
        self.target_label.setText(self.practice.target if practicing else "LIVE")
        self.instruction.setText(self.practice.instruction(now) if practicing else
                                 "Make any supported letter.\nMove your pinky for J or index finger for Z.")
        self.hold_progress.setValue(self.practice.progress(now) if practicing else 0)
        self.score_label.setText(f"Session: {self.practice.score} correct\n"
                                 f"All-time practice: {self.total_correct} correct")

    def _about(self):
        QMessageBox.about(self, "About SignLingo",
            "<h2>SignLingo</h2><p>A local fingerspelling practice prototype.</p>"
            "<p>Recognition: OpenCV, MediaPipe, saved hand examples and experimental J/Z paths.</p>"
            "<p>Project contributors: Karen, Etinosa and Jeffrey. See README.md for credits.</p>"
            "<p>No account, server, video recording or automatic training-data upload. "
            "Preferences and an all-time correct counter are stored on this device.</p>"
            "<p>This is not a complete ASL course or an assessment of signing proficiency.</p>")

    def closeEvent(self, event):
        if self.worker is not None:
            self.closing = True
            self.stop_camera()
            self.status.setText("Stopping camera safely before closing…")
            event.ignore()  # Never destroy a QThread while native camera/model code is running.
            return
        self.timer.stop()
        for key, value in (("index", self.camera_index.value()),
                           ("mirror", self.mirror.isChecked()),
                           ("landmarks", self.landmarks.isChecked()),
                           ("low_power", self.low_power.isChecked())):
            self.settings.setValue(f"camera/{key}", value)
        self.settings.sync()
        event.accept()
