#!/bin/bash
# Wrap the SwiftPM executable in a .app so it gets a Dock icon, a real window
# and the TCC prompts a plain binary never receives.
set -euo pipefail
cd "$(dirname "$0")"

CONFIG="${1:-release}"
swift build -c "$CONFIG"
BIN="$(swift build -c "$CONFIG" --show-bin-path)/Workroom"
APP="build/Workroom.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Workroom"

ICNS="../assets/Workroom.icns"
[ -f "$ICNS" ] || python3 ../scripts/make_icon.py >/dev/null 2>&1 || true
[ -f "$ICNS" ] && cp "$ICNS" "$APP/Contents/Resources/Workroom.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Workroom</string>
  <key>CFBundleDisplayName</key><string>Workroom</string>
  <key>CFBundleIdentifier</key><string>dev.workroom.onboarding</string>
  <key>CFBundleExecutable</key><string>Workroom</string>
  <key>CFBundleIconFile</key><string>Workroom</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppleEventsUsageDescription</key>
  <string>Workroom opens Terminal to start the agent you just set up.</string>
</dict>
</plist>
PLIST

# Ad-hoc signature: enough for local runs and for TCC to remember the app.
codesign --force --sign - "$APP" 2>/dev/null || true
echo "$APP"
