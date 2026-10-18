# Build on the target OS, from the repo root: python -m PyInstaller --noconfirm packaging/SignLingo.spec
# Folder distribution first: easier to inspect and validate native dependencies.
from pathlib import Path
import re
import sys
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent  # this spec lives in packaging/
# One version number for the app and the window: signlingo/__init__.py
version = re.search(r'__version__ = "(.+?)"', (root / 'signlingo' / '__init__.py').read_text()).group(1)
mp_data, mp_binaries, mp_imports = collect_all('mediapipe')
assets = [(str(root / 'models' / 'hand_landmarker.task'), 'models')]
assets += [(str(path), 'data') for path in sorted((root / 'data').glob('examples_*.json'))]
assets += [(str(root / 'signlingo' / 'assets'), 'signlingo/assets')]

a = Analysis(
    [str(root / 'desktop_app.py')],
    pathex=[str(root)],
    binaries=mp_binaries,
    datas=assets + mp_data,
    hiddenimports=mp_imports,
    hookspath=[],
    excludes=['gradio', 'PyQt5', 'PyQt6', 'PySide2', 'tkinter',
              'torch', 'tensorflow', 'IPython', 'notebook', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='SignLingo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SignLingo')
if sys.platform == 'darwin':
    app = BUNDLE(
        collection,
        name='SignLingo.app',
        icon=str(root / 'packaging' / 'macos' / 'SignLingo.icns'),
        bundle_identifier='org.signlingo.desktop',
        info_plist={
            'CFBundleDisplayName': 'SignLingo',
            'CFBundleShortVersionString': version,
            'CFBundleVersion': version,
            # The bundled numpy and Qt wheels are built for macOS 14 (Sonoma) and newer.
            'LSMinimumSystemVersion': '14.0',
            'NSCameraUsageDescription': 'SignLingo uses your camera for local fingerspelling practice. Video is not uploaded.',
            'NSHighResolutionCapable': True,
        },
    )
