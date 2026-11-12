#!/usr/bin/env bash
# The improver: Claude Code (on your Claude subscription) runs the pipeline, inspects every stage and
# improves the system, in its own checkout and its own workspace, so the live server and the app's list of
# lessons are never touched.
#
#   scripts/agent/improve.sh setup                    one time: make the improver checkout and its workspace
#   scripts/agent/improve.sh run "<request>"          one request, start to finish, no questions asked
#   scripts/agent/improve.sh inspect <job id> [...]   look inside lessons already made (spends nothing)
#   scripts/agent/improve.sh queue                    run every request file waiting in the inbox
#   scripts/agent/improve.sh shell                    open Claude Code in the improver checkout, to talk to it
#
# Settings: scripts/agent/improver.env (copy improver.env.example). Docs: docs/agent/IMPROVER.md
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONF="${IMPROVER_CONF:-$SELF_DIR/improver.env}"
[ -f "$CONF" ] && . "$CONF"

LIVE_REPO="${LIVE_REPO:-$(cd "$SELF_DIR/../../.." && pwd -P)}"     # the git checkout the live server runs from
WORKTREE="${WORKTREE:-$(dirname "$LIVE_REPO")/$(basename "$LIVE_REPO")-improver}"
BASE_BRANCH="${BASE_BRANCH:-main}"
VENV="${VENV:-$LIVE_REPO/lessonforge/.venv}"
# The live server's workspace (the app's list, the ledger and its budget, the library, the caches). An
# improver.env from before 2026-10-15 named it LESSONFORGE_HOME; a call from inside a run finds IMPROVER_LIVE_HOME.
LIVE_HOME="${LIVE_HOME:-${IMPROVER_LIVE_HOME:-${LESSONFORGE_HOME:-$LIVE_REPO/lessonforge/lessonforge_workspace}}}"
# The improver's own workspace: the lessons it makes never enter the app's list. library/ and cache/ link to the live ones.
IMPROVER_HOME="${IMPROVER_HOME:-$LIVE_HOME/improver/home}"
export IMPROVER_MAX_USD="${IMPROVER_MAX_USD:-1.00}"
export IMPROVER_ROUNDS="${IMPROVER_ROUNDS:-2}"
CLAUDE_MODEL="${CLAUDE_MODEL:-sonnet}"
MAX_TURNS="${MAX_TURNS:-200}"
INBOX="${INBOX:-$LIVE_HOME/improver/inbox}"

LF="$WORKTREE/lessonforge"
LOGS="$LIVE_HOME/improver/logs"
SHARED=(library cache models)      # linked from the live workspace; models only when the live one has it

# Claude Code may work in the live workspace: reports, logs, inbox, the app's lessons to inspect, and its own workspace.
ADD_DIRS=(--add-dir "$LIVE_HOME")
case "$IMPROVER_HOME/" in "$LIVE_HOME"/*) ;; *) ADD_DIRS+=(--add-dir "$IMPROVER_HOME");; esac

say() { echo "[improver] $*"; }

make_home() {
  # The improver's own workspace. Its lessons land in $IMPROVER_HOME/lessons, never in the app's list; the library
  # (cards, drawings, the concept base) and the caches (speech, the stage store) are the live ones: nothing is paid twice.
  [ -d "$LIVE_HOME" ] || { say "no live workspace at $LIVE_HOME: set LIVE_HOME in $CONF"; exit 1; }
  mkdir -p "$IMPROVER_HOME"
  if [ "$(cd "$IMPROVER_HOME" && pwd -P)" = "$(cd "$LIVE_HOME" && pwd -P)" ]; then
    say "IMPROVER_HOME is the live workspace: its lessons would show in the app's list. Set another one in $CONF"; exit 1
  fi
  local name
  for name in "${SHARED[@]}"; do
    if [ "$name" = models ] && [ ! -d "$LIVE_HOME/models" ]; then continue; fi
    mkdir -p "$LIVE_HOME/$name"
    if [ -L "$IMPROVER_HOME/$name" ]; then
      ln -sfn "$LIVE_HOME/$name" "$IMPROVER_HOME/$name"
    elif [ -e "$IMPROVER_HOME/$name" ]; then
      say "$IMPROVER_HOME/$name is a real folder, not a link: left as it is. Move it away and run setup again to share the live one"
    else
      ln -s "$LIVE_HOME/$name" "$IMPROVER_HOME/$name"
    fi
  done
  say "improver workspace at $IMPROVER_HOME (library and cache linked to $LIVE_HOME)"
}

load_live_keys() {
  # The provider keys reach a run through its environment; no .env sits in the improver checkout.
  local env_file="$LIVE_REPO/lessonforge/.env" anthropic="${ANTHROPIC_API_KEY-__unset__}"
  if [ ! -f "$env_file" ]; then
    say "note: no live .env at $env_file: provider keys come from this shell's environment only"; return 0
  fi
  set +u; set -a
  . "$env_file"
  set +a; set -u
  # Claude Code bills an ANTHROPIC_API_KEY instead of the plan (IMPROVER.md step 3): the .env never brings one in.
  if [ "$anthropic" = "__unset__" ]; then unset ANTHROPIC_API_KEY; else export ANTHROPIC_API_KEY="$anthropic"; fi
}

use_env() {
  [ -d "$LF" ] || { say "no improver checkout at $WORKTREE: run '$0 setup' first"; exit 1; }
  [ -d "$IMPROVER_HOME" ] || { say "no improver workspace at $IMPROVER_HOME: run '$0 setup' first"; exit 1; }
  export PATH="$VENV/bin:$PATH"
  export PYTHONPATH="$LF/src${PYTHONPATH:+:$PYTHONPATH}"   # the worktree's code wins over the live editable install
  load_live_keys
  export LESSONFORGE_HOME="$IMPROVER_HOME"                 # after the keys: the live .env may name the live workspace
  export IMPROVER_LIVE_HOME="$LIVE_HOME"
  export OPENROUTER_LEDGER="${OPENROUTER_LEDGER:-$LIVE_HOME/spend.jsonl}"   # the owner's ledger, and budget.json beside it
  mkdir -p "$LOGS" "$INBOX"
  cd "$LF"
}

fresh_base() {
  # Every request starts from the latest base branch; branches from earlier requests stay for review.
  if [ -n "$(git status --porcelain)" ]; then
    say "the improver checkout has uncommitted changes (an earlier run stopped half way?):"
    git status --short | head -20
    say "commit or discard them in $WORKTREE, then run again"; exit 1
  fi
  git fetch -q origin "$BASE_BRANCH" || say "could not fetch origin/$BASE_BRANCH; using what is here"
  git switch -q --detach "origin/$BASE_BRANCH" 2>/dev/null || git switch -q --detach "$BASE_BRANCH"
}

headless() {   # $1 = log name, $2 = prompt
  local log="$LOGS/$(date +%Y%m%d-%H%M%S)-$1.log"
  say "Claude Code is working; follow along with: tail -f $log"
  set +e
  claude -p "$2" --model "$CLAUDE_MODEL" --permission-mode acceptEdits --max-turns "$MAX_TURNS" \
    "${ADD_DIRS[@]}" \
    --output-format text </dev/null >"$log" 2>&1
  local code=$?
  set -e
  tail -n 40 "$log"
  if [ $code -ne 0 ]; then
    if grep -qiE "usage limit|rate limit|limit reached|resets" "$log"; then
      say "stopped by the Claude plan's usage limit; run it again after the limit resets"; return 75
    fi
    say "Claude Code exited with code $code; see $log"; return $code
  fi
}

case "${1:-}" in
  setup)
    cd "$LIVE_REPO"
    if [ ! -d "$WORKTREE" ]; then
      git fetch -q origin "$BASE_BRANCH" || true
      git worktree add --detach "$WORKTREE" "origin/$BASE_BRANCH" 2>/dev/null || git worktree add --detach "$WORKTREE" "$BASE_BRANCH"
      say "made the improver checkout at $WORKTREE"
    else
      say "improver checkout already at $WORKTREE"
    fi
    # An older setup linked the live .env into the checkout. Only a link is removed, never a file.
    if [ -L "$WORKTREE/lessonforge/.env" ]; then
      rm -f "$WORKTREE/lessonforge/.env"; say "removed the old link to the live .env from the improver checkout"
    fi
    [ -x "$VENV/bin/python" ] || { say "no venv at $VENV: set VENV in $CONF"; exit 1; }
    command -v claude >/dev/null || { say "Claude Code is not installed: see docs/agent/IMPROVER.md step 2"; exit 1; }
    make_home
    mkdir -p "$INBOX" "$LOGS"
    use_env
    bash scripts/agent/preflight.sh --check && say "setup is fine. Next: $0 run \"<what the video should teach>\""
    ;;
  run)
    shift; [ $# -ge 1 ] || { say "usage: $0 run \"<request>\""; exit 2; }
    use_env; fresh_base
    headless "run" "/make-best-video $*"
    ;;
  inspect)
    shift; [ $# -ge 1 ] || { say "usage: $0 inspect <job id> [...]"; exit 2; }
    use_env
    headless "inspect" "/inspect-lesson $*"
    ;;
  queue)
    use_env
    shopt -s nullglob
    for request in "$INBOX"/*.txt "$INBOX"/*.json; do
      [ -f "$request" ] || continue
      mkdir -p "$INBOX/done" "$INBOX/failed"
      say "request: $(basename "$request")"
      fresh_base
      arg="$request"; case "$request" in *.txt) head -c 2 "$request" | grep -q '^#' || arg="$(cat "$request")";; esac
      if headless "queue" "/make-best-video $arg"; then mv "$request" "$INBOX/done/"
      else code=$?; [ $code -eq 75 ] && { say "usage limit: the rest of the inbox waits"; exit 0; }; mv "$request" "$INBOX/failed/"; fi
    done
    ;;
  shell)
    use_env
    say "Claude Code in $LF. Try: /make-best-video Class 8, why the area of a circle is pi r squared"
    exec claude --model "$CLAUDE_MODEL" "${ADD_DIRS[@]}"
    ;;
  *)
    sed -n '2,12p' "$0"; exit 2 ;;
esac
