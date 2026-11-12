"""Claude over the API improves a lesson on the workbench, inside a hard spending cap.

What a person (Claude in a chat) did for the hand-made quadrilateral videos, done by a program: look at the stills,
read what code found, make small edits, check again. The owner's conditions (2026-11-07): it must never run up a
bill on its own, so

* free first: code checks, craft numbers and stills are made before any call, and a lesson with nothing to fix
  costs nothing;
* a hard cap per lesson (``cap_usd``): before every call the next call's cost is estimated from the last one, and
  the run stops, keeping its best version, when it would go over; every call is written to the spend ledger;
* small calls: the model answers with a few edits (``workbench.apply_edits``), never the whole lesson; the fixed
  instructions are marked for the provider's prompt cache; one contact sheet, not a video;
* a cheap model first (Haiku), and a bigger one only after the cheap one fails to improve the lesson twice;
* at most ``rounds`` rounds, stopping early when a round improves nothing.

Two ways to reach Claude: ``ANTHROPIC_API_KEY`` (Anthropic's API) or ``OPENROUTER_API_KEY`` (the same models
through OpenRouter, from the account the rest of lessonforge spends).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time

from .. import kits
from . import workbench as W

#: Dollars per million tokens: input, output, cached input. Checked against OpenRouter's catalogue 2026-11-07.
PRICES = {"haiku": (0.10, 0.50, 0.01), "sonnet": (2.0, 10.0, 0.2), "opus": (4.0, 20.0, 0.4)}
MODELS = {
    "anthropic": {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"},
    "openrouter": {"haiku": "anthropic/claude-haiku-5.5", "sonnet": "anthropic/claude-sonnet-5.5",
                   "opus": "anthropic/claude-opus-5.5"},
}
DEFAULT_CAP = 0.10
FIRST_CALL_GUESS = 0.005           # a Haiku-class call measured 0.2-0.5 cents (2026-11-07 pilot); others scale by price

SYSTEM = """You improve one narrated lesson video made by lessonforge. Code draws every picture from the lesson's
JSON, a voice reads the narration, and each step's "show" words appear on screen when its "say" words are spoken.

You get: the lesson (chapters of beats), the faults code found, craft numbers, and a contact sheet of stills (one
image per step, in order, labelled with the beat id). Answer with a few EDITS that make the video teach better.

WHAT GOOD LOOKS LIKE (hand-made lessons and good lecturers):
- The screen changes with the voice: every sentence that says something new starts a step ("say" = a few words of
  that sentence, copied exactly; "show" = at most 9 words on screen, not a copy of the sentence).
- Pictures build up. The next beat keeps the same shape and ADDS what the voice now talks about (an angle, a
  diagonal, a shaded region, a verdict) instead of showing the same picture again.
- Explain with the picture: shade the triangles a proof uses ("fills"), replay a motion when it is explained
  ("move"), put examples side by side ("panels") for a summary, show the unknown as "?" before revealing it.
- Plain, short sentences a teacher says to one learner; no stiff words ("configuration", "degenerate" unless taught).
- Do not crowd a beat: at most about 3 new things on its picture, 25 to 70 spoken words.
- Keep questions, their options and their reasons unless code reports a fault in them: a wrong option that comes
  from a real mistake (using 180 instead of 360, taking the outside angle) is the point of the question.
- Numbers already written in the lesson were filled in by code from the points: leave them as they are.
- Keep the lesson's length within 15%.

THE STORY (the framework measured on 290 good explainer videos; keep the pack's content, tell it this way):
1. Open on one concrete thing the learner can picture and a question they want answered; say what most people
   would guess.  2. Turn it: "But..." show why that guess is not quite right.  3. Explain through that same example,
   each sentence picking up the one before it (so, because, which means, but); the reason before the name.
4. Check once with a real question on a slightly different case, then answer it with its reason.
5. Close by answering the opening question plainly and saying the key idea.
Never say the plan aloud ("Pause on that", "Your turn", "Predict before you look", "Now the rule"). Lines that do are
listed under story_stage_talk: rewrite them. A chapter that opens with a definition instead of a question or a
surprise is a place to improve.

WHERE TO LOOK FIRST: find the sentences where the voice explains something the picture does not show (a proof
that splits a shape into triangles with nothing shaded, a "compare" with one shape on screen, a summary with no
picture of the cases, a motion described but not shown). Fix those with figure changes before rewording steps.

EDITS (JSON list, applied in order, each checked by code):
  {"op":"set_beat","beat":"04","fields":{"narration":"..","steps":[{"say":"..","show":"..","kind":"point|key|math"}],"figure":{..}}}
      replaces only the fields given (a field set to null is removed). Steps must list ALL the beat's steps.
  {"op":"insert_beat","after":"04","beat":{"narration":"..","steps":[..],"figure":{..}}}
  {"op":"delete_beat","beat":"04"}
  {"op":"set_shape","name":"tri","shape":{"points":{"A":[0,0],"B":[4,0],"C":[1,3]},"polygon":"ABC","is":["convex"]}}

SHAPE FIGURES (geometry):
{shape_rules}
  In a finished lesson a figure usually carries its shape inline: {"kind":"shape","points":{..},"polygon":"ABCD",
  ...what to show}. Keep the same points when you add to a picture. You may also write {"kind":"shape","use":"<name>"}
  with a shape from "shapes" or one you declare with set_shape.
  NEVER type a measured value: write a gap ({angle D}, {side AB}, {360 - angle A - angle B - angle C}); code fills it.

Answer ONLY JSON: {"edits":[...], "why":"one sentence"}. Make at most 6 edits per answer; choose the ones that help
the learner most. If nothing needs changing, answer {"edits":[], "why":"..."}."""


class CapReached(RuntimeError):
    pass


def _system() -> str:
    from .shapes import SHAPE_RULES
    return SYSTEM.replace("{shape_rules}", SHAPE_RULES)


def provider() -> str | None:
    if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        return "anthropic"
    if (os.getenv("OPENROUTER_API_KEY") or "").strip():
        return "openrouter"
    return None


def _slim(lesson: dict) -> dict:
    """The lesson as the model needs it: chapters and beats with the fields an edit can touch."""
    keep = ("id",) + W.BEAT_FIELDS
    return {"title": lesson.get("title"), "shapes": lesson.get("shapes") or {}, **kits.slim(lesson),
            "chapters": [{"id": c.get("id"), "title": c.get("title"),
                          "beats": [{k: b[k] for k in keep if b.get(k) not in (None, "", [], 0.0)} for b in c.get("beats") or []]}
                         for c in lesson.get("chapters") or []]}


def _sheet_b64(path: str | None, width: int = 1400) -> str | None:
    if not path:
        return None
    from PIL import Image
    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def score(check: dict) -> float:
    """Lower is better: faults first, then the craft problems a viewer sees."""
    c = check["craft"]
    return (10 * len(check["faults"]) + 2 * len(c["beats_with_held_sentences"]) + 2 * len(c["beats_same_picture_as_before"])
            + len(c["long_screen_words"]) + 2 * len(c.get("story_stage_talk") or []) + max(0.0, 0.9 - c["screen_changes_per_sentence"]) * 10)


def _ask(kind: str, tier: str, system: str, text: str, image: str | None, note: str = "improver") -> tuple[dict, float, dict]:
    """One call. Returns the answer, its cost in dollars and its token counts."""
    import httpx
    model = MODELS[kind][tier]
    price_in, price_out, price_cached = PRICES[tier]
    began = time.time()
    if kind == "anthropic":
        content = ([{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image}}] if image else [])
        content.append({"type": "text", "text": text})
        body = {"model": model, "max_tokens": 6000,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": content}]}
        r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=240,
                       headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        data = r.json()
        answer = "".join(part.get("text", "") for part in data.get("content") or [])
        u = data.get("usage") or {}
        cached = int(u.get("cache_read_input_tokens") or 0)
        fresh = int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) * 1.25
        tokens = {"in": int(u.get("input_tokens") or 0) + cached + int(u.get("cache_creation_input_tokens") or 0),
                  "out": int(u.get("output_tokens") or 0), "cached": cached}
        cost = (fresh * price_in + cached * price_cached + tokens["out"] * price_out) / 1e6
    else:
        content = [{"type": "text", "text": text}]
        if image:
            content.insert(0, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})
        body = {"model": model, "max_tokens": 6000, "usage": {"include": True},
                "messages": [{"role": "system", "content": [{"type": "text", "text": system,
                                                              "cache_control": {"type": "ephemeral"}}]},
                             {"role": "user", "content": content}]}
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=240,
                       headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "X-Title": "lessonforge improver"})
        r.raise_for_status()
        data = r.json()
        answer = data["choices"][0]["message"]["content"] or ""
        u = data.get("usage") or {}
        cached = int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        tokens = {"in": int(u.get("prompt_tokens") or 0), "out": int(u.get("completion_tokens") or 0), "cached": cached}
        cost = float(u.get("cost") if u.get("cost") is not None else
                     ((tokens["in"] - cached) * price_in + cached * price_cached + tokens["out"] * price_out) / 1e6)
    try:
        from .. import spend
        spend.record("chat", model, cost, prompt_tokens=tokens["in"], completion_tokens=tokens["out"],
                     seconds=round(time.time() - began, 1), note=note, cached_tokens=tokens["cached"])
    except Exception:  # noqa: BLE001 - the ledger is a record, never a reason to fail
        pass
    m = re.search(r"\{.*\}", answer, re.S)
    try:
        parsed = json.loads(m.group(0)) if m else {}
    except ValueError:
        parsed = {}
    return parsed, cost, tokens


def improve(lesson_id: str, cap_usd: float = DEFAULT_CAP, rounds: int = 3, tier: str = "haiku",
            escalate: str | None = "sonnet", look: bool = True, log=print, ask=None,
            film_faults: list[str] | None = None) -> dict:
    """Up to ``rounds`` rounds of edits by Claude, never spending more than ``cap_usd``. The best version is kept
    as the newest. ``ask``: a stand-in for the API call (tests). ``film_faults``: what the frame judge saw in the
    last film (``frame_judge.as_faults``); given to the first round only, since an edit changes what a film shows."""
    kind = provider()
    if ask is None and kind is None:
        raise RuntimeError("no Claude key: set ANTHROPIC_API_KEY, or OPENROUTER_API_KEY to reach Claude through OpenRouter")
    ask = ask or (lambda t, s, text, image: _ask(kind, t, s, text, image))
    system = _system()
    spent, last_cost, failures, report = 0.0, None, 0, []
    best = W.check(lesson_id)
    best_score, best_version = score(best), best["versions"]
    log(f"[improve] {lesson_id}: start score {best_score:.1f} ({len(best['faults'])} fault(s))")
    for n in range(1, rounds + 1):
        now = W.check(lesson_id)
        seen = film_faults if n == 1 else None
        if not now["faults"] and score(now) < 0.5 and not seen:
            log("[improve] nothing left to fix: stopping before any further call")
            break
        guess = (last_cost or FIRST_CALL_GUESS * PRICES[tier][0] / PRICES["haiku"][0]) * 1.3
        if spent + guess > cap_usd:
            log(f"[improve] the next call (about ${guess:.3f}) would pass the cap (${cap_usd:.2f}, spent ${spent:.3f}): stopping")
            break
        shown = W.preview(lesson_id, log=lambda *a: None) if look else {}
        lesson = W.load(lesson_id)
        text = ((f"THE SUBJECT KIT THIS LESSON DRAWS FROM (its rules; code checks them):{kits.rules_for_lesson(lesson)}\n\n"
                 if kits.active(lesson) else "")
                + f"LESSON:\n{json.dumps(_slim(lesson), ensure_ascii=False)}\n\n"
                f"FAULTS FOUND BY CODE (fix all of them):\n{json.dumps(now['faults'], ensure_ascii=False) or '[]'}\n\n"
                + (f"WHAT A VISION CHECK SAW IN THE LAST FILM (one frame per sentence):\n{json.dumps(seen, ensure_ascii=False)}\n\n" if seen else "")
                + f"CRAFT NUMBERS:\n{json.dumps(now['craft'], ensure_ascii=False)}\n\n"
                f"LAYOUT FINDINGS:\n{json.dumps((shown.get('findings') or [])[:12], ensure_ascii=False)}\n\n"
                + ("The image is the contact sheet of this version's stills." if shown.get("sheet") else ""))
        answer, cost, tokens = ask(tier, system, text, _sheet_b64(shown.get("sheet")))
        spent += cost
        last_cost = cost
        edits = answer.get("edits") or []
        record = {"round": n, "model": tier, "cost": round(cost, 5), "tokens": tokens, "edits": len(edits),
                  "why": answer.get("why", "")}
        if not edits:
            record["result"] = "no edits"
            report.append(record)
            log(f"[improve] round {n}: no edits (${cost:.4f})")
            break
        try:
            done = W.edit(lesson_id, edits, by=f"improver/{tier}", why=str(answer.get("why", "")))
        except W.WorkbenchError as exc:
            done = {"kept": False, "faults": [str(exc)]}
        if not done["kept"] and spent + cost * 1.3 <= cap_usd:
            # One chance to fix the edit, with exactly what code refused.
            again, cost2, tokens2 = ask(tier, system, text + "\n\nYOUR EDITS WERE REFUSED BY CODE:\n"
                                        + json.dumps(done["faults"][:10], ensure_ascii=False)
                                        + f"\nYOUR EDITS WERE:\n{json.dumps(edits, ensure_ascii=False)}\nSend corrected edits.", None)
            spent += cost2
            record["cost"] = round(cost + cost2, 5)
            try:
                done = W.edit(lesson_id, again.get("edits") or [], by=f"improver/{tier}", why=str(again.get("why", "")))
            except W.WorkbenchError as exc:
                done = {"kept": False, "faults": [str(exc)]}
        after = W.check(lesson_id)
        record["score"] = round(score(after), 2)
        record["kept"] = done.get("kept", False)
        if not record["kept"]:
            record["refused"] = (done.get("faults") or [])[:6]
            for line in record["refused"][:3]:
                log(f"[improve]   refused: {line[:200]}")
        report.append(record)
        log(f"[improve] round {n} ({tier}): {len(edits)} edit(s), kept={record['kept']}, score {record['score']}, "
            f"${record['cost']:.4f} (spent ${spent:.4f} of ${cap_usd:.2f})")
        # A kept round that does not score worse stands: the score counts faults and still screens, not a shaded
        # proof or a summary panel, so a tie can be a better picture (pilot 2026-11-07: Sonnet's recap panels were
        # thrown away on a tie). Only a strictly better score resets the patience.
        if record["kept"] and score(after) <= best_score + 0.01:
            better = score(after) < best_score - 0.01
            best_score, best_version = min(best_score, score(after)), after["versions"]
            failures = 0 if better else failures + 1
        else:
            failures += 1
            if failures >= 2 and escalate and tier != escalate:
                log(f"[improve] {tier} did not improve the lesson twice: the next round asks {escalate}")
                # The bigger model reads the same prompt: its first call costs about the last one times the price ratio.
                ratio = PRICES[escalate][0] / PRICES[tier][0]
                tier, last_cost, failures = escalate, (last_cost or FIRST_CALL_GUESS) * ratio, 0
            elif failures >= 2:
                break
    if W.check(lesson_id)["versions"] != best_version:
        W.revert(lesson_id, best_version, by="improver (best version)")
    return {"lesson_id": lesson_id, "spent_usd": round(spent, 4), "cap_usd": cap_usd, "rounds": report,
            "best_version": best_version, "best_score": round(best_score, 2), **W.check(lesson_id)}
