"""Spend ledger: every metered OpenRouter call, and a budget that is actually enforced.

The engine's docs record TTS as the dominant cost and model calls as the second;
neither was ever summed in one place, so "how much did this video cost" was a guess.
Here every chat and speech request appends one line to ``<workspace>/spend.jsonl``
(``OPENROUTER_LEDGER`` overrides the path) with the model, the tokens and the cost
OpenRouter itself reports — the ``usage.cost`` field on chat completions, the
generation record for speech — so the number is the bill, not an estimate.

The budget is two-layered on purpose. ``OPENROUTER_BUDGET_USD`` (or ``budget.json`` next
to the ledger, which wins and can be changed while a server runs) caps what THIS
ledger may spend; ``OPENROUTER_USAGE_BASELINE`` is the key's lifetime usage when the
budget was granted, and the key's live usage (``/auth/key``, cached 30 s) is checked
against ``baseline + budget`` too, so spending from another process or a lost ledger
cannot slip past. A call that would exceed either raises ``BudgetExceeded`` BEFORE
it is sent; nothing is ever cut off mid-render.

There is a third ceiling that neither of those sees: the ACCOUNT's own credit. On
2026-10-09 the ledger showed 14.36 of a 20 USD cap while the account had 0.57 USD left;
OpenRouter began answering 402, and a 16-minute lesson that had already paid for its
script and its animations was narrated by the fallback voice. ``account_credit`` reads
that number and ``ensure_credit`` refuses a job the account cannot pay for BEFORE it
starts.

A fourth guard is per LESSON (2026-10-22). The key reached its 100 USD cap with the ledger at 47 USD; a lesson
costs 0.10 to 0.40, so the cap was not reached by ordinary lessons, but nothing would have stopped one lesson
caught in a retry or repair loop from spending without end either. ``lesson_scope`` opens a tally for one lesson:
every ledger row written inside it carries the lesson's ``job`` id, and ``check`` refuses the next call once the
lesson has spent its own ceiling (``LESSONFORGE_LESSON_MAX_USD``; by default a multiple of its estimate). The same
scope is what makes "how much did THIS lesson cost" a sum instead of a guess (``job["cost_usd"]``).
"""
from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

OPENROUTER_API = "https://openrouter.ai/api/v1"
_LOCK = threading.Lock()
_REMOTE = {"at": 0.0, "usage": None, "daily": None}
_CREDIT = {"at": 0.0, "left": None}
_LAST: dict | None = None


class BudgetExceeded(RuntimeError):
    """The configured budget would be exceeded by the next metered call."""


class _Lesson:
    """One lesson's running tally. Shared by every thread of the lesson (``knobs.wrap`` carries it to pools)."""

    def __init__(self, job_id: str, cap: float | None):
        self.job_id, self.cap, self.spent, self.calls = job_id, cap, 0.0, 0
        self.lock = threading.Lock()

    def add(self, cost: float) -> None:
        with self.lock:
            self.spent += float(cost or 0.0)
            self.calls += 1


_LESSON: contextvars.ContextVar[_Lesson | None] = contextvars.ContextVar("lessonforge_spend_lesson", default=None)

#: How many times its own estimate one lesson may spend before its next call is refused. The estimate already
#: leans high (``lesson_estimate``); measured lessons came in at 0.3 to 0.7 of it. Two and a half times is
#: far beyond any lesson seen, and well short of what a loop spends.
LESSON_CAP_FACTOR = 2.5
#: Never below this, so a short lesson that needs one extra review round is not stopped by its own small estimate.
LESSON_CAP_FLOOR = 1.0


def lesson_cap(estimate: float | None) -> float | None:
    """The most one lesson may spend. ``LESSONFORGE_LESSON_MAX_USD``: a dollar figure, ``0`` for no per-lesson
    ceiling, unset for ``LESSON_CAP_FACTOR`` times the lesson's estimate (at least ``LESSON_CAP_FLOOR``).
    A server-wide setting on purpose (``os.getenv``, not a lesson's own control): a ceiling a request could
    raise for itself would guard nothing."""
    raw = os.getenv("LESSONFORGE_LESSON_MAX_USD", "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is not None:
            return None if value <= 0 else value
    if estimate is None:
        return None
    return round(max(LESSON_CAP_FLOOR, LESSON_CAP_FACTOR * float(estimate)), 2)


@contextmanager
def lesson_scope(job_id: str, cap: float | None = None):
    """Count every metered call made inside the block as this lesson's, and hold it to ``cap`` USD.

    Yields the tally (``.spent``, ``.calls``). Nested scopes are not expected; an inner one would simply
    count on its own."""
    tally = _Lesson(str(job_id), cap)
    token = _LESSON.set(tally)
    try:
        yield tally
    finally:
        _LESSON.reset(token)


def current_lesson() -> _Lesson | None:
    """The lesson whose calls are being counted here, if any (``knobs.wrap`` hands it to a pool's workers)."""
    return _LESSON.get()


def ledger_path() -> Path:
    override = os.getenv("OPENROUTER_LEDGER", "").strip()
    if override:
        return Path(override)
    from . import paths
    return paths.home() / "spend.jsonl"


def budget_file() -> Path:
    """Next to the ledger: a budget changed while the server runs (``lessonforge budget N``)."""
    return ledger_path().with_name("budget.json")


def budget() -> float | None:
    """The cap in USD.

    ``budget.json`` next to the ledger wins over ``OPENROUTER_BUDGET_USD``. It is read on
    every call, so a budget raised with ``lessonforge budget N`` applies to the next
    metered call of a running server: the environment is fixed when a process starts,
    and restarting a server to raise it would kill whatever lesson it is generating.
    """
    try:
        value = json.loads(budget_file().read_text(encoding="utf-8")).get("budget_usd")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            return float(value)
    except (OSError, ValueError, AttributeError):
        pass
    raw = os.getenv("OPENROUTER_BUDGET_USD", "").strip()
    return float(raw) if raw else None


def set_budget(amount: float) -> float:
    """Set the cap for every process using this ledger, from its next metered call on."""
    amount = float(amount)
    if not amount >= 0:
        raise ValueError("a budget is zero or more dollars")
    path = budget_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"budget_usd": amount, "set_at": round(time.time(), 1)}), encoding="utf-8")
    os.replace(tmp, path)
    return amount


def baseline() -> float:
    return float(os.getenv("OPENROUTER_USAGE_BASELINE", "0") or 0)


def api_key() -> str | None:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return key or None


def record(kind: str, model: str, cost: float | None, *, prompt_tokens: int = 0, completion_tokens: int = 0,
           reasoning_tokens: int = 0, seconds: float | None = None, note: str = "",
           generation_id: str | None = None, estimated: bool = False, cached_tokens: int = 0) -> dict:
    """Append one metered call. ``kind`` is ``chat`` | ``tts`` | ``vision``. ``cached_tokens``: how many of the prompt's
    tokens the provider read from its prompt cache (billed at about a tenth; ``engine.llm.cached_of`` reads it from a
    call's usage). Written only when there were any, so older rows and tools that read them are as they were."""
    global _LAST
    entry = {
        "at": time.time(), "kind": kind, "model": model, "cost": float(cost or 0.0),
        "prompt_tokens": int(prompt_tokens or 0), "completion_tokens": int(completion_tokens or 0),
        "reasoning_tokens": int(reasoning_tokens or 0), "seconds": seconds, "note": note,
        "generation_id": generation_id, "estimated": bool(estimated),
    }
    if cached_tokens:
        entry["cached_tokens"] = int(cached_tokens)
    lesson = _LESSON.get()
    if lesson is not None:
        entry["job"] = lesson.job_id
        lesson.add(entry["cost"])
    path = ledger_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _ledger_lock(path):
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _LAST = entry
    return entry


class _ledger_lock:
    """One writer of the ledger at a time, ACROSS processes (the server, a command-line run, ``lessonforge spend``).

    ``_LOCK`` is a thread lock: it protects nothing between two processes. ``reconcile`` replaces the
    whole file, so a row another process appended between its read and its write was lost, and a
    process that had the old file open kept appending to a file nobody would read again. Both sides
    now take this lock, and the appender opens the file only once it holds it.
    """

    def __init__(self, path: Path):
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.handle = None

    def __enter__(self):
        try:
            import fcntl
            self.handle = open(self.lock_path, "a")
            fcntl.flock(self.handle, fcntl.LOCK_EX)
        except (ImportError, OSError):          # no flock here: the thread lock is all there is, as before
            self.handle = None
        return self

    def __exit__(self, *exc):
        if self.handle is not None:
            try:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_UN)
            finally:
                self.handle.close()
        return False


def last() -> dict | None:
    """The most recent entry recorded by this process."""
    return _LAST


def entries() -> list[dict]:
    path = ledger_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def spent() -> float:
    return sum(e.get("cost", 0.0) for e in entries())


def remote_usage(max_age: float = 30.0) -> float | None:
    """The key's lifetime usage in USD as OpenRouter reports it, or None when unknown."""
    key = api_key()
    if not key:
        return None
    now = time.time()
    if _REMOTE["usage"] is not None and now - _REMOTE["at"] < max_age:
        return _REMOTE["usage"]
    try:
        import httpx
        r = httpx.get(f"{OPENROUTER_API}/auth/key", headers={"Authorization": f"Bearer {key}"}, timeout=15.0)
        data = r.json()["data"]
        usage = float(data["usage"])
        daily = data.get("usage_daily")
        daily = float(daily) if isinstance(daily, (int, float)) and not isinstance(daily, bool) else None
    except Exception:  # noqa: BLE001 - the local ledger still guards
        return _REMOTE["usage"]
    _REMOTE.update({"at": now, "usage": usage, "daily": daily})
    return usage


def remote_daily(max_age: float = 30.0) -> float | None:
    """What the key has spent today (UTC day) as OpenRouter reports it, or None when unknown."""
    remote_usage(max_age)
    return _REMOTE.get("daily")


def daily_cap() -> float | None:
    """``OPENROUTER_DAILY_USD``: the most the key may spend in one UTC day, whoever spends it. Unset: no daily cap."""
    raw = os.getenv("OPENROUTER_DAILY_USD", "").strip()
    try:
        value = float(raw) if raw else None
    except ValueError:
        return None
    return value if value is not None and value > 0 else None


def check(estimate: float = 0.0, what: str = "a metered call") -> None:
    """Raise ``BudgetExceeded`` when ``estimate`` more dollars would pass the budget, this lesson's own ceiling
    (``lesson_scope``) or the key's daily cap (``OPENROUTER_DAILY_USD``)."""
    lesson = _LESSON.get()
    if lesson is not None and lesson.cap is not None and lesson.spent + estimate > lesson.cap:
        raise BudgetExceeded(f"this lesson has spent {lesson.spent:.2f} USD in {lesson.calls} calls, its ceiling is "
                             f"{lesson.cap:.2f} (LESSONFORGE_LESSON_MAX_USD); refusing {what}. A lesson that costs "
                             "this much is usually repeating a failing step: read its log before trying again.")
    day = daily_cap()
    if day is not None:
        today = remote_daily()
        if today is not None and today + estimate > day:
            raise BudgetExceeded(f"the key has spent {today:.2f} USD today (UTC) against a daily cap of {day:.2f} "
                                 f"(OPENROUTER_DAILY_USD); refusing {what}.")
    cap = budget()
    if cap is None:
        return
    local = spent()
    if local + estimate > cap:
        raise BudgetExceeded(f"budget {cap:.2f} USD: ledger shows {local:.4f} spent; refusing {what} "
                             f"(~{estimate:.4f}). Raise OPENROUTER_BUDGET_USD to continue.")
    remote = remote_usage()
    if remote is not None and (remote - baseline()) + estimate > cap:
        raise BudgetExceeded(f"budget {cap:.2f} USD: the key has used {remote - baseline():.4f} since the "
                             f"baseline; refusing {what}.")


def account_credit(max_age: float = 60.0) -> float | None:
    """What is left on the OpenRouter ACCOUNT in USD (credits bought minus used), or None when unknown."""
    key = api_key()
    if not key:
        return None
    now = time.time()
    if _CREDIT["left"] is not None and now - _CREDIT["at"] < max_age:
        return _CREDIT["left"]
    try:
        import httpx
        r = httpx.get(f"{OPENROUTER_API}/credits", headers={"Authorization": f"Bearer {key}"}, timeout=15.0)
        data = r.json()["data"]
        left = float(data["total_credits"]) - float(data["total_usage"])
    except Exception:  # noqa: BLE001 - unknown is not zero: the call itself will say if there is nothing left
        return _CREDIT["left"]
    _CREDIT.update({"at": now, "left": left})
    return left


def lesson_estimate(minutes: float) -> float:
    """Roughly what one lesson of this length costs (measured 2026-10-08/09: 0.13 to 0.25 USD for 50 seconds,
    0.5 to 0.9 for six minutes, and about 1.3 for an 8.5-minute script with 25 animations BEFORE its narration).
    An estimate for a go/no-go, never a figure to report: it leans high, because a lesson that runs out
    half-way has paid for its script and pictures and comes out silent."""
    return round(0.3 + 0.12 * max(0.0, float(minutes or 0)), 2)


def narration_estimate(minutes: float) -> float:
    """Roughly what narrating and timing a lesson of this length costs (speech about 1.4 cents a minute through
    OpenRouter, alignment 0.2, the frame review a few cents): the price of adding a voice to a finished lesson."""
    return round(0.08 + 0.03 * max(0.0, float(minutes or 0)), 2)


def room() -> float | None:
    """Dollars left under the budget cap, by whichever count is further along: the ledger's or OpenRouter's own
    for the key (the ledger runs behind). None when no cap is set."""
    cap = budget()
    if cap is None:
        return None
    used = spent()
    remote = remote_usage()
    if remote is not None:
        used = max(used, remote - baseline())
    return cap - used


def ensure_room(needed: float, what: str = "this lesson") -> None:
    """Raise ``BudgetExceeded`` when the cap does not leave ``needed``. Asked BEFORE a lesson is started.

    ``check`` refuses one call at a time, so a lesson started with too little room was planned, drawn and
    then refused its narration: on 2026-10-09 an 8.5-minute script with all 25 of its pictures came out
    silent because 1.10 USD was left when its speech began.
    """
    left = room()
    if left is not None and left < needed:
        raise BudgetExceeded(f"The spending cap of {budget():.2f} USD leaves {max(0.0, left):.2f} and {what} needs about "
                             f"{needed:.2f}. Nothing was started. The owner can raise the cap (lessonforge budget +5), "
                             "then try again.")


def ensure_credit(needed: float, what: str = "this lesson") -> None:
    """Raise ``BudgetExceeded`` when the account's credit is known and below ``needed``."""
    floor = float(os.getenv("OPENROUTER_MIN_CREDIT_USD", "0") or 0)
    left = account_credit()
    if left is not None and left < max(needed, floor):
        raise BudgetExceeded(f"The OpenRouter account has {max(0.0, left):.2f} USD of credit left and {what} needs about "
                             f"{max(needed, floor):.2f}. Nothing was started. Add credit at "
                             "https://openrouter.ai/settings/credits and try again.")


def generation_cost(generation_id: str, tries: int = 4, wait: float = 1.0) -> dict | None:
    """The billed record for one generation (speech responses carry no usage body)."""
    key = api_key()
    if not key or not generation_id:
        return None
    import httpx
    for attempt in range(tries):
        try:
            r = httpx.get(f"{OPENROUTER_API}/generation", params={"id": generation_id},
                          headers={"Authorization": f"Bearer {key}"}, timeout=15.0)
            if r.status_code == 200:
                d = r.json().get("data") or {}
                if d.get("total_cost") is not None:
                    return {"cost": float(d["total_cost"]), "prompt_tokens": d.get("tokens_prompt") or 0,
                            "completion_tokens": d.get("tokens_completion") or 0, "model": d.get("model")}
        except Exception:  # noqa: BLE001
            pass
        if attempt < tries - 1:
            time.sleep(wait * (attempt + 1))
    return None


def reconcile(max_entries: int = 50) -> int:
    """Replace estimated speech costs with the billed figure once OpenRouter has it.

    The generation record lags the audio by several seconds, and synthesis must not
    wait for it; the ledger therefore carries an estimate first (``estimated: true``)
    and this pass — run by ``summary()`` — swaps in the real number. Returns how many
    entries were corrected.
    """
    pending = [e for e in entries() if e.get("estimated") and e.get("generation_id")][-max_entries:]
    if not pending:
        return 0
    # Ask OpenRouter first, with nothing held: these are HTTP calls and take seconds.
    billed = {}
    for entry in pending:
        answer = generation_cost(entry["generation_id"], tries=1)
        if answer:
            billed[entry["generation_id"]] = answer
    if not billed:
        return 0
    # Then, holding the ledger, read it AGAIN and correct those rows in what is there now. The first
    # version wrote back the rows it had read before asking: every row another process appended in
    # those seconds was deleted (found 2026-10-09; `lessonforge spend` run during a lesson was the window).
    path, fixed = ledger_path(), 0
    with _LOCK, _ledger_lock(path):
        rows = entries()
        for row in rows:
            answer = billed.get(row.get("generation_id")) if row.get("estimated") else None
            if answer:
                row.update({"cost": answer["cost"], "prompt_tokens": answer["prompt_tokens"] or row["prompt_tokens"],
                            "completion_tokens": answer["completion_tokens"] or row["completion_tokens"],
                            "estimated": False})
                fixed += 1
        if fixed:
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in rows), encoding="utf-8")
            os.replace(tmp, path)
    return fixed


def summary() -> dict:
    """Totals by kind and by model, with the budget position (billed figures where known)."""
    reconcile()
    rows = entries()
    by_kind: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    for e in rows:
        for table, key in ((by_kind, e.get("kind", "?")), (by_model, e.get("model", "?"))):
            slot = table.setdefault(key, {"calls": 0, "cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0,
                                          "reasoning_tokens": 0, "seconds": 0.0})
            slot["calls"] += 1
            slot["cost"] += e.get("cost", 0.0)
            slot["prompt_tokens"] += e.get("prompt_tokens", 0)
            slot["completion_tokens"] += e.get("completion_tokens", 0)
            slot["reasoning_tokens"] += e.get("reasoning_tokens", 0)
            slot["seconds"] += e.get("seconds") or 0.0
    total = sum(e.get("cost", 0.0) for e in rows)
    tagged = sum(e.get("cost", 0.0) for e in rows if e.get("job"))
    cap = budget()
    remote = remote_usage()
    return {
        "ledger": str(ledger_path()), "calls": len(rows), "spent": total,
        "budget": cap, "remaining": (cap - total) if cap is not None else None,
        "key_usage_since_baseline": (remote - baseline()) if remote is not None else None,
        "account_credit": account_credit(),
        "by_kind": by_kind, "by_model": by_model,
        # Rows written inside a lesson carry its id (since 2026-10-22); the rest are tests, evals, previews
        # and rows from before then.
        "in_lessons": tagged, "outside_lessons": total - tagged,
        "daily_cap": daily_cap(), "key_usage_today": _REMOTE.get("daily"),
    }


def format_summary(s: dict | None = None) -> str:
    s = s or summary()
    lines = [f"ledger: {s['ledger']}", f"calls: {s['calls']}   spent: ${s['spent']:.4f}"]
    if s["budget"] is not None:
        lines.append(f"budget: ${s['budget']:.2f}   remaining: ${s['remaining']:.4f}")
    if s.get("in_lessons"):
        lines.append(f"  of which in lessons: ${s['in_lessons']:.4f}   outside lessons: ${s['outside_lessons']:.4f}")
    if s.get("daily_cap") is not None:
        today = s.get("key_usage_today")
        lines.append(f"daily cap: ${s['daily_cap']:.2f}" + (f"   spent today (OpenRouter): ${today:.4f}" if today is not None else ""))
    if s["key_usage_since_baseline"] is not None:
        lines.append(f"key usage since baseline (OpenRouter's number): ${s['key_usage_since_baseline']:.4f}")
    credit = s.get("account_credit")
    if credit is not None:
        lines.append(f"account credit left (OpenRouter): ${credit:.2f}")
        if s["remaining"] is not None and credit < s["remaining"]:
            lines.append(f"  ! the ACCOUNT will run out before the budget does: top it up, or calls fail with 402 "
                         f"at about ${credit:.2f} more")
    for title, table in (("by kind", s["by_kind"]), ("by model", s["by_model"])):
        lines.append(f"-- {title} --")
        for name, t in sorted(table.items(), key=lambda kv: -kv[1]["cost"]):
            extra = f"  {t['seconds']:.0f}s audio" if t["seconds"] else ""
            lines.append(f"  {name:45s} {t['calls']:4d} calls  ${t['cost']:.4f}  "
                         f"in={t['prompt_tokens']} out={t['completion_tokens']} reason={t['reasoning_tokens']}{extra}")
    return "\n".join(lines)
