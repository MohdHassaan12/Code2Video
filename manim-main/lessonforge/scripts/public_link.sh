#!/bin/bash
# Bring lessonforge up for testers and print the link to share.
#
#   bash scripts/public_link.sh            start what is not running; keep a link that still works
#   bash scripts/public_link.sh --new      also replace the public link with a fresh one
#   bash scripts/public_link.sh --restart  also restart the server (to load new code)
#
# The server and the tunnel are two processes. After a reboot both are gone, and a quick
# tunnel never gets its old address back, so the link changes — run this and share the new one.
# With a named tunnel (one-time: scripts/fixed_link_setup.sh <name.yourdomain>) the link never
# changes: LESSONFORGE_TUNNEL_CONFIG and LESSONFORGE_PUBLIC_URL in .env, and --new keeps the address.
#
# --restart refuses while a lesson is being generated: a restart would lose it (FORCE=1 overrides).
# A lesson another process is making (lessonforge script / harness in a shell) does not count: the
# server lists it as running, and restarting the server does not touch it.
# Logs, pids and the current link live in <workspace>/logs/, which survives a reboot (/tmp does not).
# The machine's own cloudflared service (/etc/cloudflared) is a different tunnel and is never touched.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
set -a; . ./.env; set +a
. .venv/bin/activate
export LESSONFORGE_HOME="${LESSONFORGE_HOME:-$ROOT/lessonforge_workspace}"
PORT="${LESSONFORGE_PORT:-5000}"
LOGS="$LESSONFORGE_HOME/logs"; mkdir -p "$LOGS"
LOCAL="http://127.0.0.1:$PORT"
NEW=0; RESTART=0
for arg in "$@"; do
  case "$arg" in
    --new) NEW=1 ;;
    --restart) RESTART=1 ;;
    *) echo "unknown option: $arg"; exit 2 ;;
  esac
done

code() { curl -s -o /dev/null -m "${2:-10}" -w '%{http_code}' "$1"; }
server_up() { [ "$(code "$LOCAL/api/harness/frameworks?token=$LESSONFORGE_ACCESS_TOKEN")" = "200" ]; }
in_progress() {
  curl -s -m 10 -H "X-Access-Token: $LESSONFORGE_ACCESS_TOKEN" "$LOCAL/api/harness/jobs" |
    python3 -c "import sys,json; print(' '.join(j['job_id'] for j in json.load(sys.stdin)['jobs'] if j['status'] in ('running','queued') and not j.get('elsewhere')))" 2>/dev/null
}
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }

# ── server ──
if server_up && [ "$RESTART" = "1" ]; then
  BUSY="$(in_progress)"
  if [ -n "$BUSY" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "REFUSING to restart: lesson(s) being generated: $BUSY (FORCE=1 to override)"; exit 3
  fi
  OLD="$(cat "$LOGS/server.pid" 2>/dev/null)"
  alive "$OLD" || OLD="$(pgrep -f 'bin/lessonforge serve' | head -1)"
  if alive "$OLD"; then
    kill "$OLD"; for _ in $(seq 1 40); do alive "$OLD" || break; sleep 0.5; done
  fi
fi
if ! server_up; then
  nohup lessonforge serve --host 127.0.0.1 --port "$PORT" >> "$LOGS/server.log" 2>&1 &
  echo $! > "$LOGS/server.pid"
  for _ in $(seq 1 90); do server_up && break; sleep 1; done
fi
if ! server_up; then echo "the server did not start; see $LOGS/server.log"; tail -5 "$LOGS/server.log"; exit 1; fi
echo "server: up on $LOCAL (pid $(cat "$LOGS/server.pid" 2>/dev/null))"

# ── tunnel ──
URL="$(cat "$LOGS/tunnel.url" 2>/dev/null)"
TPID="$(cat "$LOGS/tunnel.pid" 2>/dev/null)"
works() { [ -n "$URL" ] && [ "$(code "$URL/app/?token=$LESSONFORGE_ACCESS_TOKEN" 20)" = "200" ]; }
# A named tunnel (scripts/fixed_link_setup.sh) keeps its address; a quick tunnel gets a new one each start.
FIXED="${LESSONFORGE_TUNNEL_CONFIG:-}"
if [ -n "$FIXED" ]; then
  [ -f "$FIXED" ] || { echo "LESSONFORGE_TUNNEL_CONFIG points at a missing file: $FIXED"; exit 1; }
  [ -n "${LESSONFORGE_PUBLIC_URL:-}" ] || { echo "LESSONFORGE_PUBLIC_URL is not set (run scripts/fixed_link_setup.sh)"; exit 1; }
  [ "$URL" = "$LESSONFORGE_PUBLIC_URL" ] || NEW=1   # the running tunnel is the old quick one: replace it
  URL="$LESSONFORGE_PUBLIC_URL"
fi
if [ "$NEW" = "1" ] || ! alive "$TPID" || ! works; then
  alive "$TPID" && kill "$TPID" && sleep 1
  : > "$LOGS/tunnel.log"
  if [ -n "$FIXED" ]; then
    # Its own config file, so the machine's /etc/cloudflared service is never read or touched.
    nohup cloudflared tunnel --no-autoupdate --config "$FIXED" run >> "$LOGS/tunnel.log" 2>&1 &
    echo $! > "$LOGS/tunnel.pid"
  else
    # QUIC is blocked on this network, hence http2.
    nohup cloudflared tunnel --no-autoupdate --protocol http2 --url "$LOCAL" >> "$LOGS/tunnel.log" 2>&1 &
    echo $! > "$LOGS/tunnel.pid"
    URL=""
    for _ in $(seq 1 60); do
      URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOGS/tunnel.log" | head -1)"
      [ -n "$URL" ] && break; sleep 1
    done
    if [ -z "$URL" ]; then echo "the tunnel did not give a link; see $LOGS/tunnel.log"; tail -5 "$LOGS/tunnel.log"; exit 1; fi
  fi
  echo "$URL" > "$LOGS/tunnel.url"
  # The name takes a few seconds to resolve everywhere.
  for _ in $(seq 1 45); do works && break; sleep 2; done
fi
if ! works; then echo "the link does not answer yet: $URL (try again in a minute; see $LOGS/tunnel.log)"; exit 1; fi

echo
echo "Link for testers (do not post publicly: it carries the access key):"
echo "  $URL/app/?token=$LESSONFORGE_ACCESS_TOKEN"
echo "Dashboard (yours):"
echo "  $URL/app/?token=$LESSONFORGE_ACCESS_TOKEN#dashboard"
