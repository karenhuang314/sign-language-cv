"""SignLingo desktop entry point. Run: python desktop_app.py"""

import argparse
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true',
                        help='Open the UI briefly without starting the camera, then exit')
    parser.add_argument('--self-test', action='store_true',
                        help='Check bundled data and real MediaPipe inference without a camera')
    args = parser.parse_args()

    from PySide6.QtCore import QCoreApplication, QStandardPaths, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox
    from signlingo import __version__

    QCoreApplication.setOrganizationName('SignLingo')
    QCoreApplication.setApplicationName('SignLingo')
    QCoreApplication.setApplicationVersion(__version__)
    app = QApplication(sys.argv[:1])
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'signlingo.log'
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format='%(asctime)s %(levelname)s %(message)s')

    if getattr(sys, 'frozen', False):
        # MediaPipe pulls in matplotlib, and PyInstaller gives matplotlib a new
        # temp folder each launch, so it re-scans every font (~3 s). Keep its
        # cache instead, one per app location in case the app is moved.
        import hashlib
        cache = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
        key = hashlib.sha1(sys._MEIPASS.encode()).hexdigest()[:12]
        os.environ['MPLCONFIGDIR'] = str(cache / f'matplotlib-{key}')
        Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)

    try:
        from signlingo.paths import ASSETS_DIR
        from signlingo.recognition import RecognitionEngine, load_examples
        examples = load_examples()
        logging.info('Loaded %d reference vectors (includes mirrors)', len(examples))
        if args.self_test:
            import numpy as np
            engine = RecognitionEngine(examples)
            try:
                result = engine.process(np.zeros((480, 640, 3), dtype=np.uint8), 1.0)
                if result.hand_detected:
                    raise RuntimeError('Unexpected hand detection in blank-frame check')
            finally:
                engine.close()
            message = f'SignLingo self-test passed: {len(examples)} vectors; real model inference OK.'
            logging.info(message)
            if sys.stdout is not None:
                print(message)
            return 0

        from signlingo.camera_window import CameraWindow
        app.setWindowIcon(QIcon(str(ASSETS_DIR / 'signlingo.svg')))
        window = CameraWindow(examples)
        window.show()
        if args.smoke_test:
            QTimer.singleShot(500, window.close)
        return app.exec()
    except Exception as error:
        logging.exception('SignLingo startup failed')
        if args.self_test or args.smoke_test:
            if sys.stderr is not None:
                print(f'SignLingo failed: {error}\nLog: {log_path}', file=sys.stderr)
        else:
            QMessageBox.critical(None, 'SignLingo could not start', f'{error}\n\nDetails: {log_path}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
