"""Rebuild SignLingo.icns from signlingo/assets/signlingo.svg.

Run after changing the SVG:  python packaging/macos/make_icon.py
(needs PySide6, so use the desktop venv; iconutil comes with macOS)
"""

from pathlib import Path
import subprocess
import sys
import tempfile

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

HERE = Path(__file__).resolve().parent
SVG = HERE.parent.parent / "signlingo" / "assets" / "signlingo.svg"
ICNS = HERE / "SignLingo.icns"
# Mac app icons leave a margin around the artwork: 824 of 1024 pixels.
ARTWORK_SHARE = 824 / 1024


def render(renderer, size):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    margin = size * (1 - ARTWORK_SHARE) / 2
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    painter.end()
    return image


def main():
    app = QGuiApplication(sys.argv[:1])  # Qt needs this before drawing
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise SystemExit(f"Can't read {SVG}")
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "SignLingo.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            render(renderer, points).save(str(iconset / f"icon_{points}x{points}.png"))
            render(renderer, points * 2).save(str(iconset / f"icon_{points}x{points}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS)], check=True)
    del app
    print(f"Wrote {ICNS}")


if __name__ == "__main__":
    main()
