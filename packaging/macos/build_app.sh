#!/bin/bash
# Builds SignLingo.app and a SignLingo-<version>.dmg to share.
# Run inside the desktop venv, on a Mac:  ./packaging/macos/build_app.sh
set -euo pipefail
cd "$(dirname "$0")/../.."   # repo root, so build/ and dist/ land there

if [ "$(uname)" != "Darwin" ]; then
    echo "This script builds the Mac app; run it on a Mac." >&2
    exit 1
fi

python -m pip install -q -r requirements-build.txt   # pinned PyInstaller + app dependencies
python -m PyInstaller --noconfirm --clean packaging/SignLingo.spec

APP=dist/SignLingo.app
VERSION=$(python -c "import signlingo; print(signlingo.__version__)")
DMG="dist/SignLingo-$VERSION.dmg"

# Check the finished app before sharing it: the signature must be intact
# (a broken one makes macOS call the app "damaged"), and the bundled model
# and examples must load without a camera.
codesign --verify --deep --strict "$APP"
"$APP/Contents/MacOS/SignLingo" --self-test

# The disk image people download: the app, a shortcut to Applications to
# drag it onto, and the first-open instructions.
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
ditto "$APP" "$STAGE/SignLingo.app"
ln -s /Applications "$STAGE/Applications"
cp "packaging/macos/How to open SignLingo.txt" "$STAGE/"
rm -f "$DMG"
hdiutil create -quiet -volname SignLingo -srcfolder "$STAGE" -format UDZO "$DMG"

echo "Done: $APP and $DMG ($(du -h "$DMG" | cut -f1))"
