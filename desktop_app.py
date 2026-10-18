"""SignLingo desktop entry point. Run: python desktop_app.py"""

import argparse
import logging
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

    QCoreApplication.setOrganizationName('SignLingo')
    QCoreApplication.setApplicationName('SignLingo')
    QCoreApplication.setApplicationVersion('0.1.0')
    app = QApplication(sys.argv[:1])
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'signlingo.log'
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format='%(asctime)s %(levelname)s %(message)s')

    try:
        from signlingo.recognition import RESOURCE_ROOT, RecognitionEngine, load_examples
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
        app.setWindowIcon(QIcon(str(RESOURCE_ROOT / 'signlingo' / 'assets' / 'signlingo.svg')))
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
