#!/bin/sh
# Renders every SVG in docs/diagrams/ to PNG (at 1.5x) with headless Google Chrome (macOS path).
# Run from the repo root:  sh docs/diagrams/src/make_png.sh
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
cd "$(dirname "$0")/.." || exit 1
for svg in *.svg; do
  w=$(sed -n 's/.*<svg[^>]* width="\([0-9]*\)".*/\1/p' "$svg" | head -1)
  h=$(sed -n 's/.*<svg[^>]* height="\([0-9]*\)".*/\1/p' "$svg" | head -1)
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1.5 \
    --window-size="$w,$h" --screenshot="$PWD/${svg%.svg}.png" "file://$PWD/$svg" 2>/dev/null
  echo "wrote ${svg%.svg}.png"
done
