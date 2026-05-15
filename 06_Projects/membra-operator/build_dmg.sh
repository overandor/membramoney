#!/usr/bin/env zsh
# Build MEMBRA Operator macOS DMG
set -e

cd "$(dirname "$0")"
APP_NAME="MEMBRA Operator"
BUNDLE="dist/${APP_NAME}.app"
DMG_NAME="MEMBRA-Operator-0.1.0.dmg"
VOL_NAME="MEMBRA Operator Install"

echo "[1/4] Installing deps..."
pip install -r requirements.txt --quiet

echo "[2/4] Building app with py2app..."
python setup.py py2app --quiet

echo "[3/4] Verifying bundle..."
if [ ! -d "$BUNDLE" ]; then
    echo "ERROR: Bundle not found at $BUNDLE"
    exit 1
fi

echo "[4/4] Creating DMG..."
# Clean old
rm -f "dist/$DMG_NAME"

# Create temporary mount folder
TMP_DMG="dist/temp_membra_operator.dmg"
SIZE="80m"

hdiutil create -size "$SIZE" -volname "$VOL_NAME" -srcfolder "$BUNDLE" -ov -format UDZO "$TMP_DMG"
mv "$TMP_DMG" "dist/$DMG_NAME"

echo ""
echo "✅ Build complete: dist/$DMG_NAME"
echo "Install by dragging ${APP_NAME}.app to /Applications"
ls -lh "dist/$DMG_NAME"
