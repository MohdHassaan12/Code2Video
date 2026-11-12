#!/usr/bin/env bash
# Checks before the improver spends anything. Prints RUN=<folder> on success; exits non-zero on a problem.
# Run from lessonforge/ inside the improver's own checkout (scripts/agent/improve.sh sets the environment).
set -uo pipefail
fail() { echo "PREFLIGHT FAILED: $*"; exit 1; }
here="$(pwd -P)"

[ -f pyproject.toml ] && [ -d src/lessonforge ] || fail "run this from the lessonforge/ folder"

# 1. Not the checkout the live server runs from: edits there would reach a tester's lesson mid-render.
git_dir="$(git rev-parse --git-dir 2>/dev/null)"; common="$(git rev-parse --git-common-dir 2>/dev/null)"
if [ "$(cd "$git_dir" && pwd -P)" = "$(cd "$common" && pwd -P)" ] && [ "${IMPROVER_ALLOW_MAIN_CHECKOUT:-0}" != "1" ]; then
  fail "this is the main checkout. Use the improver worktree (scripts/agent/improve.sh setup), or set IMPROVER_ALLOW_MAIN_CHECKOUT=1 if no live server runs from it"
fi
if [ -n "$(git status --porcelain -- . ':!lessonforge_workspace' 2>/dev/null)" ]; then
  echo "note: uncommitted changes in this checkout:"; git status --short -- . | head -20
fi

# 2. The code that runs is THIS checkout's.
code_from="$(python -c 'import lessonforge, pathlib; print(pathlib.Path(lessonforge.__file__).resolve().parent)' 2>/dev/null)" \
  || fail "python cannot import lessonforge (is the venv on PATH?)"
case "$code_from" in "$here"/*) ;; *) fail "lessonforge is imported from $code_from, not from this checkout ($here). Set PYTHONPATH=$here/src";; esac
echo "code:      $code_from"

# 3. Its OWN workspace (a lesson made in the live one would show in the app's list, with a "Try again" that spends
#    the owner's money), sharing the live library and caches (nothing paid twice) and spending on the live ledger
#    (the owner's cap; budget.json sits beside the ledger). scripts/agent/improve.sh sets all of this.
[ -n "${LESSONFORGE_HOME:-}" ] || fail "LESSONFORGE_HOME is not set (scripts/agent/improve.sh sets it to the improver's own workspace)"
[ -n "${IMPROVER_LIVE_HOME:-}" ] || fail "IMPROVER_LIVE_HOME is not set (the live workspace; scripts/agent/improve.sh sets it)"
[ -d "$LESSONFORGE_HOME" ] || fail "no workspace at $LESSONFORGE_HOME (scripts/agent/improve.sh setup makes it)"
[ -d "$IMPROVER_LIVE_HOME" ] || fail "no live workspace at $IMPROVER_LIVE_HOME"
own="$(cd "$LESSONFORGE_HOME" && pwd -P)"; live="$(cd "$IMPROVER_LIVE_HOME" && pwd -P)"
[ "$own" != "$live" ] || fail "LESSONFORGE_HOME is the live workspace: lessons made here would show in the app's list. Use the improver's own (scripts/agent/improve.sh setup makes it)"
for name in library cache; do
  [ -L "$own/$name" ] || fail "$own/$name is not a link to the live $name: cards, drawings and stages would be made and paid for again (scripts/agent/improve.sh setup links it)"
  [ "$(cd "$own/$name" 2>/dev/null && pwd -P)" = "$live/$name" ] || fail "$own/$name does not lead to the live $name ($live/$name)"
done
ledger="$(python -c 'from lessonforge import spend; print(spend.ledger_path())')" || fail "could not find the spend ledger"
case "$ledger" in /*) ;; *) fail "the ledger path is relative ($ledger): set OPENROUTER_LEDGER to the live ledger's full path";; esac
ledger_dir="$(cd "$(dirname "$ledger")" 2>/dev/null && pwd -P)" || fail "the ledger's folder does not exist ($ledger)"
case "$ledger_dir/" in "$own"/*) fail "the ledger ($ledger) is inside the improver's workspace: spending would not be on the owner's ledger or under the cap. Set OPENROUTER_LEDGER to the live one ($live/spend.jsonl)";; esac
[ -f "$ledger" ] || echo "note: no ledger at $ledger yet"
[ -d "$own/lessons" ] || echo "note: $own/lessons does not exist yet (the improver's first lesson?)"
echo "workspace: $own (its own; library and cache linked to $live)"
echo "ledger:    $ledger"
[ -n "${OPENROUTER_API_KEY:-}" ] || echo "note: OPENROUTER_API_KEY is not set: the pipeline would write a placeholder script (improve.sh puts the live keys into the run's environment)"

# 4. Toolchain.
command -v ffmpeg >/dev/null || fail "ffmpeg is missing"
command -v latex >/dev/null || echo "note: no LaTeX: formulas render as plain text"

# 5. Money.
python - <<'PY' || fail "could not read the spend ledger"
from lessonforge import spend
import os
room, credit = spend.room(), spend.account_credit()
cap = float(os.getenv("IMPROVER_MAX_USD", "1.00"))
print(f"money:     ledger spent {spend.spent():.2f} USD; room under the cap {'no cap' if room is None else f'{room:.2f} USD'}; "
      f"account credit {'unknown' if credit is None else f'{credit:.2f} USD'}; this request may use up to {cap:.2f} USD")
if room is not None and room < 0.15:
    raise SystemExit("not enough room under the spending cap for even one lesson")
PY

# 6. A folder for this request (not with --check).
[ "${1:-}" = "--check" ] && { echo "preflight ok"; exit 0; }
stamp="$(date +%Y%m%d-%H%M%S)"
run="${IMPROVER_LIVE_HOME:-$LESSONFORGE_HOME}/improver/$stamp"    # reports stay beside the live workspace's improver/logs
mkdir -p "$run" || fail "cannot create $run"
python -c 'from lessonforge import spend; print(round(spend.spent(), 4))' > "$run/spent_before.txt"
echo "RUN=$run"
