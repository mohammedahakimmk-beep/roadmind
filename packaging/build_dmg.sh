#!/bin/bash
# Build RoadMind.app with PyInstaller and wrap it in a DMG.
#   VERSION=... ROADMIND_SKIP_BUILD=1 ROADMIND_SIGN=... ./packaging/build_dmg.sh
# VERSION:      release version used in the DMG filename (default 0.1.0)
# ROADMIND_SIGN: Developer ID to real-sign with (default: ad-hoc)
# ROADMIND_SKIP_BUILD: set to 1 to skip PyInstaller (already-built on CI)
set -euo pipefail
cd "$(dirname "$0")/.."

NAME=RoadMind
VERSION="${VERSION:-${1:-0.1.0}}"
OUT=dist/${NAME}.app
ENT=packaging/entitlements.plist

if [ "${ROADMIND_SKIP_BUILD:-0}" != "1" ]; then
  echo "[1/5] PyInstaller build..."
  .venv/bin/pyinstaller --noconfirm packaging/${NAME}.spec
else
  echo "[1/5] Skipping PyInstaller build (ROADMIND_SKIP_BUILD=1)"
  [ -d "$OUT" ] || { echo "ERROR: $OUT missing - run pyinstaller first" >&2; exit 1; }
fi

SIGN="${ROADMIND_SIGN:-}"

if [ -n "$SIGN" ]; then
  echo "[2/5] Signing with Developer ID: $SIGN"
  find "$OUT" -type f -print0 | while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q Mach-O; then
      codesign --force --options runtime --timestamp --entitlements "$ENT" --sign "$SIGN" "$f" 2>/dev/null || true
    fi
  done
  codesign --force --options runtime --timestamp --entitlements "$ENT" --sign "$SIGN" "$OUT"
else
  echo "[2/5] Ad-hoc signing"
  codesign --force --sign - "$OUT"
fi

echo "[3/5] Staging DMG..."
STAGE=packaging/_stage
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$OUT" "$STAGE/"
hdiutil create -volname "$NAME" -srcfolder "$STAGE" -ov \
  -format UDZO "dist/${NAME}-${VERSION}.dmg"
rm -rf "$STAGE"

echo "[4/5] Signing DMG..."
if [ -n "$SIGN" ]; then
  codesign --force --sign "$SIGN" "dist/${NAME}-${VERSION}.dmg"
fi

echo "[5/5] Done -> dist/${NAME}-${VERSION}.dmg"
spctl --assess --type execute -vv "$OUT" 2>&1 || true