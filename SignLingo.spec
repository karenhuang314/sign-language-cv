# Build on the target OS: python -m PyInstaller --noconfirm SignLingo.spec
# Folder distribution first: easier to inspect and validate native dependencies.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
mp_data, mp_binaries, mp_imports = collect_all('mediapipe')
assets = [(str(root / 'hand_landmarker.task'), '.')]
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
        bundle_identifier='org.signlingo.desktop',
        info_plist={
            'CFBundleDisplayName': 'SignLingo',
            'CFBundleShortVersionString': '0.1.0',
            'NSCameraUsageDescription': 'SignLingo uses your camera for local fingerspelling practice. Video is not uploaded.',
            'NSHighResolutionCapable': True,
        },
    )
