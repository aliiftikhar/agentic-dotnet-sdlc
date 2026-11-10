#!/bin/bash
# Screenshots of the pages a UI change touches, as evidence for the verifier and the PR.
# See "UI changes" in AGENTS.md.
#
#   scripts/ui-screenshots.sh [--guest] [--append] [--wait <ms>] [--height <px>] <change-name> <route>...
#       Screenshots of each route at 1280 and 390 wide, saved in
#       openspec/changes/<change-name>/screenshots/, with screenshots.md listing them.
#       Uses the saved session in .auth/ui-user.json if there is one (signed in), else a guest.
#       --guest   take the pages as a guest (with .auth/ui-guest.json if saved) even if signed in is possible
#       --append  keep earlier screenshots and add this run to screenshots.md (e.g. guest + signed in)
#       --wait    milliseconds to wait after load for the page to render (default 3000)
#       --height  viewport height (default 2000); a tall viewport shows content below the fold,
#                 also when the layout scrolls inside an element rather than the page
#
#   scripts/ui-screenshots.sh --login | --setup-guest
#       Owner only, once: opens a browser window and saves the session (gitignored):
#       --login        sign in with the test account -> .auth/ui-user.json
#       --setup-guest  as a guest, finish any first-visit prompt -> .auth/ui-guest.json
#       Agents never run these or type credentials.
#
# Starts the API and Web apps if they aren't running, and stops only the ones it started.
# Only loads pages: never clicks or types.
# Needs Chromium for Playwright once: npx playwright@1.64.1 install chromium

# --- Configure for your repository -------------------------------------------------
# Pin Playwright to a release at least two weeks old.
PLAYWRIGHT="playwright@1.64.1"
API_URL="http://localhost:<api port>"
WEB_URL="http://localhost:<web port>"
LOGIN_PATH="<sign-in path, e.g. /auth/login>"
start_apps() {
  # start_app <name> <project file> <url> <source folders whose changes the running app must be newer than>
  start_app api '<ApiProject>/<ApiProject>.csproj' "$API_URL" '<ApiProject>'
  start_app web '<WebProject>/<WebProject>.csproj' "$WEB_URL" '<WebProject>' '<SharedUiProject>'
}
# UI files (git pathspecs) that must be committed before taking screenshots
UI_PATHSPECS=(':(glob)<SharedUiProject>/**/*.razor' ':(glob)<SharedUiProject>/**/*.css' ':(glob)<WebProject>/**/*.razor' ':(glob)<WebProject>/**/*.css' ':!:*/wwwroot/lib/*' ':!:*/wwwroot/bootstrap/*')
# -----------------------------------------------------------------------------------

set -u
SESSION=".auth/ui-user.json"
GUEST_SESSION=".auth/ui-guest.json"

repo=$(git rev-parse --show-toplevel) || exit 1
cd "$repo" || exit 1

usage() {
  sed -n '4,22p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 2
}

login=0 setup_guest=0 guest=0 append=0 wait_ms=3000 height=2000
while [ $# -gt 0 ]; do
  case "$1" in
    --login) login=1; shift ;;
    --setup-guest) setup_guest=1; shift ;;
    --guest) guest=1; shift ;;
    --append) append=1; shift ;;
    --wait) [ $# -ge 2 ] || usage; wait_ms=$2; shift 2 ;;
    --height) [ $# -ge 2 ] || usage; height=$2; shift 2 ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) break ;;
  esac
done

started_pids=""
started_ports=""
cleanup() {
  for port in $started_ports; do
    pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null)
    [ -n "$pids" ] && kill $pids 2>/dev/null
  done
  for pid in $started_pids; do
    pkill -P "$pid" 2>/dev/null
    kill "$pid" 2>/dev/null
  done
}
trap cleanup EXIT

is_up() {
  curl -s -o /dev/null --max-time 2 "$1"
}

# Seconds since the process listening on <port> started (dotnet run doesn't reload, so an app started
# before the latest source change serves old code).
listener_age() {
  pid=$(lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null | head -1)
  [ -z "$pid" ] && return 1
  ps -o etime= -p "$pid" | tr -d ' ' | awk '{
    t = $0; d = 0
    if (index(t, "-")) { split(t, a, "-"); d = a[1]; t = a[2] }
    n = split(t, p, ":"); s = 0
    for (i = 1; i <= n; i++) s = s * 60 + p[i]
    print d * 86400 + s }'
}

# Newest modification time (epoch seconds) of the tracked files in the given folders. A checkout or
# edit updates it, so it also catches switching branches under a running app.
newest_source() {
  git ls-files -- "$@" | python3 -c '
import os, sys
times = [os.path.getmtime(p) for p in (l.rstrip("\n") for l in sys.stdin) if os.path.isfile(p)]
print(int(max(times, default=0)))'
}

# start_app <name> <project> <url> <source folder>...
start_app() {
  name=$1 project=$2 url=$3
  shift 3
  if is_up "$url"; then
    age=$(listener_age "${url##*:}")
    newest=$(newest_source "$@")
    if [ -z "$age" ] || [ "$newest" -gt $(( $(date +%s) - age )) ]; then
      echo "$name is running on $url but was started before the latest change in $*, so it may show old code." >&2
      echo "Stop it (the script then starts a fresh one) or restart it, and run this again." >&2
      exit 1
    fi
    echo "$name is already running on $url and is newer than its source; using it."
    return 0
  fi
  set -- "$name" "$project" "$url"
  log="${TMPDIR:-/tmp}/ui-screenshots-$1.log"
  echo "Starting $1 on $3 (log: $log)..."
  dotnet run --project "$2" --urls "$3" >"$log" 2>&1 &
  started_pids="$started_pids $!"
  started_ports="$started_ports ${3##*:}"
  for _ in $(seq 1 120); do
    is_up "$3" && return 0
    sleep 1
  done
  echo "$1 didn't start within 120 seconds; see $log" >&2
  exit 1
}

if [ $login -eq 1 ] || [ $setup_guest -eq 1 ]; then
  start_apps
  mkdir -p .auth
  if [ $login -eq 1 ]; then
    file=$SESSION url="$WEB_URL$LOGIN_PATH"
    echo "Sign in with the test account in the browser window (finish any first-visit prompt), then close it."
  else
    file=$GUEST_SESSION url="$WEB_URL/"
    echo "Finish any first-visit prompt in the browser window, then close it."
  fi
  npx --yes "$PLAYWRIGHT" codegen --save-storage="$file" "$url" || exit 1
  echo "Saved the session to $file (gitignored)."
  exit 0
fi

[ $# -ge 2 ] || usage
change=$1
shift
dir="openspec/changes/$change"
if [ ! -d "$dir" ]; then
  echo "No change folder $dir. Give the name of an active OpenSpec change." >&2
  exit 1
fi

# The recorded commit must be what's on screen, so UI files must be committed first.
dirty=$(git status --porcelain -- "${UI_PATHSPECS[@]}" | sed 's/^...//')
if [ -n "$dirty" ]; then
  echo "These UI files have uncommitted changes; commit them first, so screenshots.md records the commit they show:" >&2
  sed 's/^/  /' <<<"$dirty" >&2
  exit 1
fi

signed_in=no
storage=""
if [ $guest -eq 0 ] && [ -f "$SESSION" ]; then
  signed_in=yes
  storage=$SESSION
else
  [ $guest -eq 0 ] && echo "Warning: no saved session ($SESSION), so pages are taken as a guest. The owner can run scripts/ui-screenshots.sh --login." >&2
  if [ -f "$GUEST_SESSION" ]; then
    storage=$GUEST_SESSION
  else
    echo "Note: no saved guest session ($GUEST_SESSION), so pages show a first visit. The owner can run scripts/ui-screenshots.sh --setup-guest." >&2
  fi
fi
storage_args=()
mode=$([ $signed_in = yes ] && echo signed-in || echo guest)

shots="$dir/screenshots"
record="$dir/screenshots.md"
if [ $append -eq 0 ] || [ ! -f "$record" ]; then
  rm -rf "$shots"
  printf '# Screenshots: %s\n' "$change" >"$record"
fi
mkdir -p "$shots"

start_apps

sha=$(git rev-parse HEAD)
{
  printf '\nTaken at: %s\nSigned in: %s\nViewports: 1280x%s (desktop), 390x%s (phone)\n\n' "$sha" "$signed_in" "$height" "$height"
  printf '| Route | Desktop | Phone |\n|-------|---------|-------|\n'
} >>"$record"

for route in "$@"; do
  case "$route" in /*) ;; *) route="/$route" ;; esac
  slug=$(printf '%s' "$route" | tr '[:upper:]' '[:lower:]' | sed -E 's#[^a-z0-9]+#-#g; s#^-+##; s#-+$##')
  [ -z "$slug" ] && slug=home
  for view in "desktop:1280, $height" "phone:390, $height"; do
    name="$slug-$mode-${view%%:*}.png"
    size=${view#*:}
    if [ -n "$storage" ]; then
      # Save the session back after each page, so refreshed tokens and the sliding cookie are kept.
      storage_args=(--load-storage "$storage" --save-storage "$storage.tmp")
    fi
    if ! npx --yes "$PLAYWRIGHT" screenshot -b chromium --full-page --wait-for-timeout "$wait_ms" \
        --viewport-size "$size" ${storage_args[@]+"${storage_args[@]}"} "$WEB_URL$route" "$shots/$name" >/dev/null; then
      echo "Screenshot of $route failed. If Chromium is missing: npx $PLAYWRIGHT install chromium" >&2
      exit 1
    fi
    [ -n "$storage" ] && [ -s "$storage.tmp" ] && mv "$storage.tmp" "$storage"
  done
  printf '| %s | ![](screenshots/%s) | ![](screenshots/%s) |\n' "$route" "$slug-$mode-desktop.png" "$slug-$mode-phone.png" >>"$record"
  echo "Took $route ($mode)."
done

echo "Saved to $shots and listed in $record. Commit them with the change."
