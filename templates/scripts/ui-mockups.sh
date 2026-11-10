#!/bin/bash
# Mock-ups of a planned UI change, drawn with the proposal before any code. See "UI changes" in AGENTS.md.
#
#   scripts/ui-mockups.sh --new <change-name> <mock-up-name>
#       Copies the starter page (scripts/ui-mockup-template.html: the app's stylesheets and layout
#       shell with an empty <main>) to openspec/changes/<change-name>/mockups/<mock-up-name>.html.
#
#   scripts/ui-mockups.sh <change-name>
#       Renders every mockups/*.html at 1280 and 390 wide (2000 high) to <name>-desktop.png and
#       <name>-phone.png, and writes mockups.md listing them. Stylesheet links and the icon sprite
#       are inlined from the repo, so it works from an archived change folder too.
#
# Opens local files only: starts no app and signs nothing in. Use made-up data in mock-ups.
# Needs Chromium for Playwright once: npx playwright@1.64.1 install chromium

# --- Configure for your repository -------------------------------------------------
PLAYWRIGHT="playwright@1.64.1"   # same version as scripts/ui-screenshots.sh
TEMPLATE="scripts/ui-mockup-template.html"
SPRITE=""   # optional SVG sprite of <symbol id="..."> icons to inline, e.g. <SharedUiProject>/wwwroot/icons.svg
# -----------------------------------------------------------------------------------

set -u

repo=$(git rev-parse --show-toplevel) || exit 1
cd "$repo" || exit 1

usage() {
  sed -n '4,15p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 2
}

find_change() {
  if [ -d "openspec/changes/$1" ]; then
    echo "openspec/changes/$1"
  else
    ls -d openspec/changes/archive/*-"$1" 2>/dev/null | tail -1
  fi
}

if [ "${1:-}" = "--new" ]; then
  [ $# -eq 3 ] || usage
  dir="openspec/changes/$2"
  if [ ! -d "$dir" ]; then
    echo "No change folder $dir. Give the name of an active OpenSpec change." >&2
    exit 1
  fi
  case "$3" in *[!a-z0-9-]*|"") echo "Mock-up names use lowercase letters, digits and hyphens: $3" >&2; exit 1 ;; esac
  file="$dir/mockups/$3.html"
  if [ -e "$file" ]; then
    echo "$file already exists." >&2
    exit 1
  fi
  mkdir -p "$dir/mockups"
  cp "$TEMPLATE" "$file"
  echo "Created $file. Draw the page inside <main>, then run scripts/ui-mockups.sh $2."
  exit 0
fi

case "${1:-}" in -h|--help|-*|"") usage ;; esac
[ $# -eq 1 ] || usage
change=$1
dir=$(find_change "$change")
if [ -z "$dir" ]; then
  echo "No change folder for $change." >&2
  exit 1
fi
mocks="$dir/mockups"
pages=$(ls "$mocks"/*.html 2>/dev/null)
if [ -z "$pages" ]; then
  echo "No mock-ups in $mocks. Start one with scripts/ui-mockups.sh --new $change <name>." >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
rm -f "$mocks"/*.png
record="$dir/mockups.md"
{
  printf '# Mock-ups: %s\n\n' "$change"
  printf 'Viewports: 1280x2000 (desktop), 390x2000 (phone)\n\n'
  printf '| Page | Desktop | Phone |\n|------|---------|-------|\n'
} >"$record"

for page in $pages; do
  name=$(basename "$page" .html)
  # Inline the stylesheets (dropping ::deep, which only Blazor's scoped CSS understands) and the icon
  # sprite if one is set, because Chromium blocks file:// pages from loading another file's SVG symbols.
  python3 - "$repo" "$page" "$SPRITE" "$work/$name.html" <<'PY' || exit 1
import os, re, sys
repo, page, sprite, out = sys.argv[1:]
html = open(page, encoding="utf-8").read()
def inline(m):
    path = os.path.join(repo, m.group(1))
    if not os.path.isfile(path):
        sys.exit(f"{page}: stylesheet {m.group(1)} not found (links are relative to the repo root)")
    css = open(path, encoding="utf-8").read().replace("::deep ", "")
    return "<style>\n" + css + "\n</style>"
html = re.sub(r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*/?>', inline, html)
if sprite:
    svg = open(os.path.join(repo, sprite), encoding="utf-8").read()
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = svg.replace("<svg ", '<svg style="display:none" ', 1)
    html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + svg, html, count=1)
html = re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + f'\n<base href="file://{repo}/">', html, count=1)
open(out, "w", encoding="utf-8").write(html)
PY
  for view in "desktop:1280, 2000" "phone:390, 2000"; do
    shot="$mocks/$name-${view%%:*}.png"
    if ! npx --yes "$PLAYWRIGHT" screenshot -b chromium --wait-for-timeout 500 \
        --viewport-size "${view#*:}" "file://$work/$name.html" "$shot" >/dev/null; then
      echo "Rendering $page failed. If Chromium is missing: npx $PLAYWRIGHT install chromium" >&2
      exit 1
    fi
  done
  printf '| %s | ![](mockups/%s) | ![](mockups/%s) |\n' "$name" "$name-desktop.png" "$name-phone.png" >>"$record"
  echo "Rendered $name."
done

echo "Saved to $mocks and listed in $record. Commit them with the proposal, before any UI code."
