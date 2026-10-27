#!/bin/sh
# Renders the Mermaid diagrams in docs/diagrams/*.md to PNG with headless Google Chrome (macOS).
# Loads mermaid@11.4.1 from cdn.jsdelivr.net, so it needs internet. Run from the repo root:
#   sh docs/diagrams/src/make_state_png.sh
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
cd "$(dirname "$0")/.." || exit 1
TMP=$(mktemp -d)
# Markdown file -> PNG names, one per mermaid block, in order.
python3 - "$TMP" > "$TMP/names" <<'PY'
import re, sys, html
SOURCES = {
    "state_order.md": ["state_order", "state_payment"],
    "data_model.md": ["data_model"],
}
for md, names in SOURCES.items():
    blocks = re.findall(r"```mermaid\n(.*?)```", open(md, encoding="utf-8").read(), re.S)
    for name, block in zip(names, blocks):
        page = f"""<!doctype html><meta charset="utf-8">
<body style="margin:0;background:#fff"><pre class="mermaid">{html.escape(block)}</pre>
<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";
mermaid.initialize({{ startOnLoad: true, theme: "default", themeVariables: {{ fontSize: "15px" }} }});
</script></body>"""
        open(f"{sys.argv[1]}/{name}.html", "w", encoding="utf-8").write(page)
        print(name)
PY
for name in $(cat "$TMP/names"); do
  # Chrome sometimes stalls in headless mode: give it 40 s, then retry once.
  for attempt in 1 2; do
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
      --virtual-time-budget=8000 --window-size=2400,2000 \
      --screenshot="$TMP/$name.png" "file://$TMP/$name.html" 2>/dev/null &
    pid=$!
    ( sleep 40; kill "$pid" 2>/dev/null ) &
    wait "$pid" 2>/dev/null
    [ -s "$TMP/$name.png" ] && break
  done
  [ -s "$TMP/$name.png" ] || { echo "failed to render $name" >&2; continue; }
  magick "$TMP/$name.png" -trim +repage -bordercolor white -border 30 "$name.png"
  echo "wrote $name.png"
done
rm -rf "$TMP"
