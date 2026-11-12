"""Composition tried before it is paid for: a lesson is previewed as stills, measured, looked at, and given the look
the preview shows to work.

The owner, 2026-10-10: "Render previews, detect problems, apply localized fixes, rerender, and run regression tests.
Add vision-based assessment for issues that bounding boxes cannot detect. … Learn or infer which layouts work for
different content types … Split scenes when necessary rather than forcing everything into one frame."

Until that day every decision about a lesson's screen was made blind and checked only after the narration had been
bought and the chapters filmed. A lesson can be previewed in seconds (``longform/preview.py``), so now, after the
script is final and BEFORE the speech stage:

1. the lesson is previewed in the look it would get;
2. a choice that can be made by trying is tried: a lesson with pictures drawn by code is previewed again with them
   enlarged to the room the frame has (``look``: ``pictures: fill``), and gets that only when the preview shows no
   fault the first did not have. Which layouts work is found out on the lesson itself, not assumed;
3. the stills are measured (type too small for a phone, a picture left a thumbnail: ``preview.measure``) and looked at
   by a vision model for what no box can say (``vision_review.assess``: the drawing is of something else than the
   voice is about; the words speak of a thing that is not in it; a line that is a note to the animator).

What is found is written into the lesson's folder (``composition.json``) and its log, and one kind of finding is ACTED
on (``mend``; ``HARNESS_COMPOSE_MEND=0`` for a report only): a beat spoken over a drawing of something else is given a
drawing of its own from the drawing service (``HARNESS_COMPOSE_DRAW=0`` to leave that out), or, when none can be had
and the beat never had a picture, is shown without one. Each change is previewed and looked at again, and put back
unless it holds. Words are rewritten only with ``HARNESS_COMPOSE_MEND=words`` (tried, not recommended: ``mending``).

Nothing here raises to its caller and nothing here can cost the lesson: the service runs it as advisory.
``HARNESS_COMPOSE=0`` switches the whole step off; ``HARNESS_COMPOSE_LOOK=0`` only the vision model's look.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import time
from pathlib import Path

from .. import knobs
from ..longform import look as lesson_look
from ..longform import preview


def enabled() -> bool:
    return (knobs.get("HARNESS_COMPOSE") or "1").strip() != "0"


def looking() -> bool:
    """Whether a vision model looks at the stills: not when it is switched off here, or for the whole lesson."""
    return (knobs.get("HARNESS_COMPOSE_LOOK") or "1").strip() != "0" and (knobs.get("HARNESS_VISION_REVIEW") or "1").strip() != "0"


def mending() -> str:
    """How far what the look finds is acted on (``HARNESS_COMPOSE_MEND``): ``""`` not at all (a report), ``"pictures"``
    a beat spoken over a drawing of something else is shown without it, ``"words"`` that and a rewrite of words that
    speak of what their drawing does not hold.

    Rewriting is NOT the default and should not be made it lightly. Tried on three real lessons (2026-10-11, every
    change read): of thirteen rewrites that the second look called cures, four made the lesson worse. One read the
    answer of the lesson's own question off the picture ("Picture mein arrow … ball pushes foot"), one put the
    conclusion before the proof it was to come from, one talked about the caption, one turned "chlorophyll captures
    sunlight" into "works with sunlight" because the drawing does not show it. The cause is upstream (the writer is
    not told what its drawing holds) and is better cured there than by a rewrite after it.
    """
    asked = (knobs.get("HARNESS_COMPOSE_MEND") or MEND).strip().lower()
    return {"1": "pictures", "pictures": "pictures", "words": "words"}.get(asked, "")


MEND = "pictures"


#: What the look finds that a program can act on: the drawing is of something else, or the words speak of a thing
#: that is not in it. (Print too small inside a drawing, half a drawing, a crowded frame: reported, nothing to do here.)
MENDABLE = ("mismatch", "missing")


def _open(looked: dict, beats=None) -> dict[str, list[dict]]:
    """``{beat: its mendable findings}`` from a look, plain or medium ones only (a "low" one is an aside)."""
    found: dict[str, list[dict]] = {}
    for row in looked.get("detail") or []:
        if beats is not None and str(row["beat"]) not in beats:
            continue
        mine = [f for f in row.get("findings") or [] if f.get("kind") in MENDABLE and f.get("severity") in ("high", "medium")]
        if mine:
            found[str(row["beat"])] = mine
    return found


def _faults_in(result: dict, chapters) -> int:
    """``preview.faults`` for some chapters only: what must not get worse where a change was made."""
    wanted = set(chapters)
    return (sum(1 for c in result.get("failed") or [] if c in wanted)
            + sum(1 for note in result.get("notes") or [] if any(str(note).startswith(f"chapter {c:02}:") for c in wanted))
            + sum(1 for b in result.get("bounds") or [] if b.get("chapter") in wanted)
            + sum(1 for item in result.get("layout") or [] if item.get("counted") and item.get("chapter") in wanted))


def _drawing_key(figure) -> str | None:
    """Which drawing a figure is: a prepared drawing by its file, a written scene by its module, anything else by
    all it says. Two beats that name the same file show the same drawing even if one names fewer of its parts."""
    if not isinstance(figure, dict):
        return None
    which = figure.get("file") or figure.get("module")
    return json.dumps({"which": which} if which else figure, sort_keys=True, default=str)


def _shared(chapters) -> set[str]:
    """The beats whose figure is a drawing another beat of the lesson carries too.

    The lesson's one prepared drawing is copied onto every beat that uses it (``writer.use_diagram``,
    ``scripted.place_picture``), so "this beat has a figure" does not say the drawing is that beat's own. The speed
    lesson (2026-10-16) kept a car between start and finish lines over beats about a scooter, a bus and a runner;
    Newton's lesson kept two people pushing over a truck and a car: each was found by the look and left on screen,
    because every one of those beats "had a picture". Taking a shared drawing off one beat loses nothing: the next
    beat that carries it draws it in again (``runtime.GuidedChapter``).
    """
    count: dict[str, int] = {}
    keys = {}
    for chapter in chapters:
        for beat in chapter.get("beats") or []:
            key = _drawing_key(beat.get("figure"))
            if key:
                keys[str(beat["id"])] = key
                count[key] = count.get(key, 0) + 1
    return {beat for beat, key in keys.items() if count[key] > 1}


def _asks(beat: dict) -> bool:
    """Whether a beat stops for an answer: it has a pause or a question card, and its words end by asking."""
    return bool(beat.get("thinking_pause_seconds") or beat.get("quiz")) and str(beat.get("narration") or "").rstrip().endswith("?")


def mend(lesson: dict, root: str | Path, result: dict, looked: dict, llm=None, judge=None, keep_words: bool = False,
         log=print, jobs: int = 8, stills=None) -> dict:
    """Act on what the look found, where a program can, and keep each change only if a second look says it cured something.

    Three things are done, all before any narration exists, so each costs a preview and a few looks, not a render:

    * a beat over which the look says the drawing on screen is of something else (an experiment with half a leaf, over
      the whole plant; a balloon to try at home, over a foot and a ball) is given a drawing of its own from the
      drawing service, of what its words ARE about (``drawing``; kept when a second look says drawing and words now
      agree; the beats after it show what they showed before);
    * such a beat that got no drawing and never had a picture of its own is shown without the picture
      (``"picture": "off"``); a drawing the beat shares with other beats (the lesson's one prepared drawing, copied
      onto each beat that uses it) is not its own (``_shared``);
    * a beat whose words speak of things its drawing does not hold ("the faint squares", "six centimetres" over a
      drawing that prints b and h) is given to the reviser with the list of what the drawing HOLDS, read from the
      drawing itself (``vision_review.holds``), and rewritten under the reviser's own contracts (``critic.apply_edits``).
      Never for an author's own script (``keep_words``).

    The lesson is previewed again and each changed beat is looked at FAULT BY FAULT (``vision_review.recheck``).
    A beat is kept when a fault it had is cured, the new words claim nothing new that the drawing lacks, a beat that
    stopped on a question still does, and its chapter's layout is no worse; otherwise it is put back exactly as it
    was: a rewrite improves or stands aside. Whatever goes wrong here, the lesson is left as it came.
    Returns ``{"tried", "kept", "undone", "picture_off", "before", "after", "changes"}``; changes ``lesson`` in place.
    """
    before = _open(looked)
    summary = {"tried": [], "kept": [], "undone": [], "picture_off": [],
               "before": {b: len(f) for b, f in before.items()}, "after": {}, "changes": {}}
    if not before:
        return summary
    as_it_was = copy.deepcopy(lesson["chapters"])
    try:
        return _mend(lesson, Path(root), result, looked, before, summary, as_it_was, llm, judge, keep_words, log, jobs, stills)
    except Exception:
        lesson["chapters"][:] = as_it_was
        raise


def drawing() -> bool:
    """Whether a beat that is about another situation than the picture on screen is given a drawing of its own from
    the drawing service (``HARNESS_COMPOSE_DRAW``, on unless "0"; needs the service: ``diagrams.topic_pictures``)."""
    from . import diagrams  # noqa: PLC0415
    return (knobs.get("HARNESS_COMPOSE_DRAW") or "1").strip() != "0" and diagrams.topic_pictures()


#: Drawings asked for in this way, at most, for one lesson: each is a wait of up to a minute before the narration.
MAX_OWN = 3
#: At most this many model-written scenes are written again in one lesson (each: one code call, a preview, a look).
MAX_SCENES = 4


def redrawing() -> bool:
    """Whether a model-written scene that does not show what its own words point at is written again
    (``HARNESS_COMPOSE_SCENES``; ON by default, "0" turns it off).

    Turned on (2026-11-07): the look's "the words point at X, which is not in the drawing" was the most repeated fault
    (14 times in 6 of 10 lessons) and was found, written down and shipped. A redraw is kept only when a second look
    says a fault was cured and nothing new is lacking, else the scene is put back as it came.

    Tried on two real lessons (2026-10-19, every frame looked at): five scenes were drawn again and the second look
    kept four. Two were plainly better (the ice lesson's "one water and one ice, the ice block bigger" now shows both,
    labelled, the ice larger; the Moon lesson's "a lamp in a room" now has the room), one was mixed, and one was WORSE:
    asked to show "the spin", the scene wrote the word "spin" under the Earth. The look that judges the change asks
    whether each fault is cured, not what else the new scene got wrong, so it passed. Same rule as rewriting words: a
    pass that makes one lesson in four worse is not the default."""
    return (knobs.get("HARNESS_COMPOSE_SCENES") or "1").strip() != "0"


def _question(beat: dict) -> str:
    """What a beat asks its learner at its end (its closing questions, and its card's), or '' when it asks nothing."""
    from ..longform.contract import split_sentences  # noqa: PLC0415
    closing = []
    for sentence in reversed(split_sentences(str(beat.get("narration") or ""))):
        if not sentence.rstrip().endswith("?") or len(closing) == 2:
            break
        closing.insert(0, sentence.strip())
    card = str((beat.get("quiz") or {}).get("question") or "").strip()
    return " ".join(closing + ([card] if card and card not in closing else []))


def _own_drawings(lesson: dict, beats: list[str], shows: dict, was: dict, stills=None, log=print, avoid: dict | None = None) -> dict[str, str]:
    """Ask the drawing service for a picture of what each of ``beats`` is about: ``{beat: the request}`` for those that got one.

    The way a lesson's model-written scenes are offered to the service (``writer.drawings_for_scenes``: one small call
    writes the requests, beats about the same things share a drawing, each drawing is taken apart and looked at): for
    the length of that call each beat stands as a scene described by what its words are about. A beat the service has
    nothing for is as it was.
    """
    from . import scripted, writer  # noqa: PLC0415
    by_id = {str(b["id"]): b for c in lesson["chapters"] for b in c["beats"]}
    for beat in beats:
        here = by_id[beat]
        about = str((shows.get(beat) or {}).get("words_about") or "").strip() or " ".join(str(here.get("narration") or "").split()[:14])
        here.pop("picture", None)
        here["figure"] = {"kind": "scene", "describe": (
            f"Beat {beat}: exactly the situation ITS WORDS describe ({about}), with nothing they do not say"
            + ("; its words end by ASKING the learner what happens or what is right: draw only the things and the set-up, "
               "never the outcome, the answer, a result or an arrow of the motion that is asked about" if _question(here) else "")
            + (f"; a first drawing was refused because it told the answer ({str(avoid[beat])[:200]}): leave that out"
               if (avoid or {}).get(beat) else ""))}
    pictures = list(lesson.get("pictures") or [])
    writer.drawings_for_scenes(lesson, lesson.get("brief") or {}, log=log, stills=stills)
    placed = [p for p in lesson.get("pictures") or [] if p not in pictures]
    if pictures or placed:
        lesson["pictures"] = pictures + placed
    got = {}
    for beat in beats:
        here = by_id[beat]
        if (here.get("figure") or {}).get("kind") in ("diagram", "picture"):
            got[beat] = next((str(p.get("ask") or "") for p in placed if beat in [str(x) for x in p.get("beats") or []]), "")
        else:                                             # the service had nothing a lesson can show: the beat as it was
            here.clear()
            here.update(copy.deepcopy(was[beat]))
    if got:                                               # a drawing in panels nobody asks for is shown whole
        writer.settle_panels(lesson, log=lambda *a: None)
        scripted.whole_once_brought_in(lesson, log=lambda *a: None)
    return got


def _keep_showing(lesson: dict, before: dict, pinned: set) -> None:
    """Every beat with no picture of its own shows what it showed BEFORE anything was changed.

    A beat without a picture keeps the last one named. When a beat in front of it is given a drawing of its own, that
    would be the new drawing: the beat is then given, by name, the picture it showed until now (``pinned`` remembers
    which beats were, so the rule can be worked out again after a change is undone).
    """
    last = None
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            name = str(beat["id"])
            if name in pinned:
                beat.pop("figure", None)
                pinned.discard(name)
            if isinstance(beat.get("figure"), dict):
                last = beat["figure"]
            elif beat.get("picture") != "off":
                want = before.get(name)
                if want is not None and json.dumps(want, sort_keys=True) != json.dumps(last, sort_keys=True):
                    beat["figure"] = copy.deepcopy(want)
                    pinned.add(name)
                    last = beat["figure"]


def _mend(lesson, root, result, looked, before, summary, as_it_was, llm, judge, keep_words, log, jobs, stills=None) -> dict:
    from . import critic, vision_review, writer  # noqa: PLC0415
    was = {str(b["id"]): b for c in as_it_was for b in c["beats"]}
    chapter_of = {str(b["id"]): c["id"] for c in as_it_was for b in c["beats"]}
    judge = judge or vision_review.default_judge(temperature=0.0)
    shows = {str(row["beat"]): row for row in looked.get("detail") or []}
    showing = vision_review._showing({"chapters": as_it_was})          # what every beat showed as the lesson came
    pinned: set = set()

    def now(beat):
        return next(b for c in lesson["chapters"] for b in c["beats"] if str(b["id"]) == beat)

    def put_back(beat):
        for chapter in lesson["chapters"]:
            for index, here in enumerate(chapter["beats"]):
                if str(here["id"]) == beat:
                    chapter["beats"][index] = copy.deepcopy(was[beat])

    def seen_again(chapters):
        return preview.stills(root, work=root / "preview" / "mended", lesson=lesson, only=sorted(chapters) if chapters else None,
                              jobs=jobs, log=lambda *a: None)

    def worse_in(again, chapters):
        return {chapter for chapter in chapters if _faults_in(again, [chapter]) > _faults_in(result, [chapter])}

    def note(beat, what, why, **more):
        earlier = summary["changes"].get(beat)            # a drawing of its own was tried first and not kept
        for name in ("kept", "undone"):
            if beat in summary[name]:
                summary[name].remove(beat)
        summary["changes"][beat] = {"what": what, "kept": not why, "why_not": why, **more,
                                    **({"tried_first": {k: earlier.get(k) for k in ("what", "why_not", "ask", "now_showing")}} if earlier else {})}
        (summary["kept"] if not why else summary["undone"]).append(beat)

    # The drawing on screen is of ANOTHER thing than the beat's words are about.
    different = [beat for beat, found in before.items() if beat in was and was[beat].get("picture") != "off"
                 and any(f["kind"] == "mismatch" for f in found)]

    # 1. A drawing of its own, from the drawing service, of what the beat IS about. Kept when a second look says the
    #    new drawing and the words are about the same thing.
    drawn: list[str] = []
    todo, avoid = (different[:MAX_OWN] if drawing() else []), {}
    for attempt in (1, 2):
        asked = _own_drawings(lesson, todo, shows, was, stills=stills, log=log, avoid=avoid) if todo else {}
        for beat in todo:
            if beat in avoid and beat not in asked:
                note(beat, "own drawing", "its first drawing told the answer to the beat's own question, and another could not be had",
                     could_tell=avoid[beat])
        if not asked:
            break
        _keep_showing(lesson, showing, pinned)
        chapters = {chapter_of[beat] for beat in asked} | {chapter_of[beat] for beat in pinned}
        again = seen_again(chapters)
        there = {str(s["beat"]) for s in again.get("stills") or [] if s.get("what") == "end" and s.get("picture")}
        worse = worse_in(again, chapters)
        retry = {}
        for beat, request in asked.items():
            # The new drawing itself, at its full size, against the beat's words: the request for it was written by a
            # small model and can drift to another experiment, or show how the beat's own question comes out.
            here = now(beat)
            seen = vision_review.fits(here.get("figure"), here, llm_call=judge, log=log)
            question = _question(here)
            told = vision_review.tells(here.get("figure"), question, llm_call=judge, log=log) if question and seen and seen["fits"] else None
            why = ("the new drawing could not be shown" if beat not in there else
                   "nobody could look at it" if seen is None or (question and told is None) else
                   "the new drawing does not show what the words describe" + (f" ({'; '.join(seen['against'])[:140]})" if seen["against"] else "")
                   if not seen["fits"] or seen["against"] else
                   "the new drawing tells the answer to the beat's own question" if told and told["tells"] else
                   "its chapter's layout got worse" if chapter_of[beat] in worse else "")
            if told and told["tells"] and seen["fits"] and not seen["against"] and attempt == 1:
                retry[beat] = "; ".join(told["could_tell"]) or "it showed how the question comes out"
                put_back(beat)
                log(f"[compose] beat {beat}: the drawing made for it tells the answer to its own question ({retry[beat][:110]}); asking for another")
                continue
            note(beat, "own drawing", why, ask=request, was_showing=(shows.get(beat) or {}).get("shows", ""),
                 words_about=(shows.get(beat) or {}).get("words_about", ""), now_showing=(seen or {}).get("drawing_shows", ""),
                 **({"could_tell": "; ".join(told["could_tell"])} if told and told["tells"] else {}))
            if why:
                put_back(beat)
                log(f"[compose] beat {beat}: a drawing of its own was not kept ({why}); it is as it was")
            else:
                drawn.append(beat)
                log(f"[compose] beat {beat}: given a drawing of its own (“{request[:70]}”): the one on screen was of something else")
        _keep_showing(lesson, showing, pinned)
        todo, avoid = list(retry), retry
    summary["drawn"] = list(drawn)

    # 2. No drawing of its own could be had, and the beat never had a picture of its own (none, or only one it shares
    #    with other beats): shown without the picture.
    shared = _shared(as_it_was)
    off = [beat for beat in different if beat not in drawn
           and (not isinstance(was[beat].get("figure"), dict) or beat in shared)]
    for beat in off:
        now(beat)["picture"] = "off"
    # 3. Words that speak of things their drawing does not hold, rewritten (only when asked for: ``mending``).
    words = [beat for beat in before if beat in was and beat not in different] if mending() == "words" and not keep_words else []
    if words:
        llm = llm or critic.default_llm()
        if llm is None:
            words = []
        else:
            findings = [{"beat": beat, "severity": "major", "what": f"{f['kind']}: {f['what']}",
                         "fix": "say only what the picture holds as being in it; see THE PICTURE HOLDS"}
                        for beat in words for f in before[beat]]
            edits = critic.revise(lesson, findings, llm, log=log, holds=looked.get("holds") or {})
            report = {"edits": [e for e in edits if str(e.get("beat")) in words]}
            critic.apply_edits(lesson, report, log=log)
            words = [beat for beat in words if beat in report.get("edits_applied", [])]
            if words:                                     # steps written again point at their drawing again (writer.point_again)
                writer.point_again(lesson, log=log, was={"chapters": as_it_was})
    if off or words:
        # Pointing again may change which names the drawing carries on beats nobody rewrote: then every chapter is seen again.
        chapters = set() if words else {chapter_of[beat] for beat in off}
        again = seen_again(chapters)
        second = vision_review.recheck(again, lesson, {beat: before[beat] for beat in words}, llm_call=judge, log=log) if words else {}
        gone = {str(s["beat"]) for s in again.get("stills") or [] if s.get("what") == "end" and not s.get("picture")}
        worse = worse_in(again, {chapter_of[beat] for beat in off + words})
        for beat in off:                                  # the preview's own record says whether the drawing has gone
            why = ("the drawing is still there" if beat not in gone else "its chapter's layout got worse" if chapter_of[beat] in worse else "")
            note(beat, "picture off", why, shows=(shows.get(beat) or {}).get("shows", ""), words_about=(shows.get(beat) or {}).get("words_about", ""),
                 cured=[f["what"] for f in before[beat] if f["kind"] == "mismatch"] if not why else [],
                 still=[f["what"] for f in before[beat] if why or f["kind"] != "mismatch"], new=[])
            if why:
                now(beat).pop("picture", None)
                log(f"[compose] beat {beat}: the change was not kept ({why}); it is as it was")
            else:
                summary["picture_off"].append(beat)
                log(f"[compose] beat {beat}: shown without the picture, which was of something else")
        for beat in words:
            here = now(beat)
            seen = second.get(beat) or {"cured": [], "still": before[beat], "new": []}
            why = ("nothing it had was cured" if not seen["cured"] else
                   "its new words speak of something else the drawing lacks" if seen["new"] else
                   "it no longer ends on its question" if _asks(was[beat]) and not _asks(here) else
                   "its chapter's layout got worse" if chapter_of[beat] in worse else "")
            note(beat, "words", why, cured=[f["what"] for f in seen["cured"]], still=[f["what"] for f in seen["still"]], new=seen["new"],
                 was=was[beat]["narration"], now=here["narration"], lines_was=[s.get("show") for s in was[beat].get("steps") or []],
                 lines_now=[s.get("show") for s in here.get("steps") or []])
            log(f"[compose] beat {beat}: " + (f"the change was not kept ({why}); it is as it was" if why else
                                              f"its words no longer speak of what its drawing does not show ({len(seen['cured'])} of "
                                              f"{len(before[beat])} thing(s) found in it cured)"))
        if words:
            kept_words = [beat for beat in words if summary["changes"][beat]["kept"]]
            standing = {beat: copy.deepcopy(now(beat)) for beat in drawn}
            if not kept_words:
                lesson["chapters"][:] = copy.deepcopy(as_it_was)      # no rewrite stands: every beat and its drawing as they came …
                pinned.clear()
                for beat, made in standing.items():                   # … but for what the other fixes did
                    now(beat).clear()
                    now(beat).update(made)
                for beat in summary["picture_off"]:
                    now(beat)["picture"] = "off"
            else:
                for beat in words:
                    if beat not in kept_words:
                        put_back(beat)
                # The beats put back carry the drawing as it was named before: one set of names for the lesson again (no model).
                writer.point_again(lesson, log=lambda *a: None, pointer=False, was={"chapters": as_it_was})
                lesson["continuity"] = writer.continuity(lesson)
        _keep_showing(lesson, showing, pinned)
    _redraw_scenes(lesson, before, summary, chapter_of, now, put_back, note, seen_again, worse_in, judge, log)
    summary["tried"] = sorted(summary["changes"])
    summary["after"] = {beat: len(change.get("still") or []) + len(change.get("new") or []) for beat, change in summary["changes"].items()}
    if not summary["tried"]:
        lesson["chapters"][:] = as_it_was
    shutil.rmtree(root / "preview" / "mended" / "media", ignore_errors=True)
    return summary


def _redraw_scenes(lesson, before, summary, chapter_of, now, put_back, note, seen_again, worse_in, judge, log) -> None:
    """4. A model-written scene that does not hold what its OWN beat's words point at is written again, once, with those
    things named in its description; kept when a look at the new still, fault by fault, says something was cured.

    The ice lesson (2026-10-19): "Here are two blocks of exactly equal mass, one water and one ice. The ice block looks
    bigger." over a scene that drew one block and a small white square; "the ice block drawn larger" asked for, and the
    ice drawn smaller. The look at the stills had found both, and nothing acted on it: the other mends are for a beat
    shown over ANOTHER beat's picture. A scene is checked by code to draw, move and stay in its box, never that it shows
    what it was asked for; this is where that is caught, before any narration exists.
    """
    from . import vision_review  # noqa: PLC0415
    redraw = [beat for beat, found in before.items() if beat not in summary["changes"]
              and isinstance(now(beat).get("figure"), dict) and now(beat)["figure"].get("kind") == "scene"
              and now(beat)["figure"].get("module") and any(f["kind"] == "missing" and f.get("thing") for f in found)]
    redraw = redraw[:MAX_SCENES] if redrawing() else []
    if not redraw:
        return
    from .service import resolve_scenes  # noqa: PLC0415 - late: service imports this module
    asked = {}
    for beat in redraw:
        figure = now(beat)["figure"]
        found = [f for f in before[beat] if f["kind"] == "missing"]
        things = list(dict.fromkeys(str(f["thing"]).strip() for f in found if f.get("thing")))[:4]
        quotes = list(dict.fromkeys(str(f.get("quote") or "").strip() for f in found if f.get("quote")))[:2]
        new = {k: v for k, v in figure.items() if k != "module"}
        # No title and no sentence in the picture: the beat's own lines are already beside it. The first wording
        # ("each with a short label") gave the Moon lesson's lamp scene a heading that repeated the line next to it.
        new["describe"] = (str(figure.get("describe") or "").rstrip(" .") + ". It must plainly show: " + "; ".join(things)
                           + ". A one-word label only where two things could be taken for each other; no title, no sentence"
                           + (" (the words over it: " + " ".join(f"\u201c{q}\u201d" for q in quotes) + ")" if quotes else "") + ".")
        trial = {"chapters": [{"id": chapter_of[beat], "beats": [{"id": beat, "figure": new}]}]}
        try:
            resolve_scenes(trial, log=lambda *a: None)
        except Exception as exc:  # noqa: BLE001 - the scene as it was stays
            log(f"[compose] beat {beat}: its scene could not be written again ({type(exc).__name__}: {str(exc)[:100]})")
        made = trial["chapters"][0]["beats"][0].get("figure")
        if isinstance(made, dict) and made.get("module") == figure.get("module"):
            # The same scene back (a cache that keyed two descriptions alike did this): a look at it is no test.
            note(beat, "scene drawn again", "the same scene came back", missing=things)
        elif isinstance(made, dict) and made.get("module"):
            now(beat)["figure"] = made
            asked[beat] = things
        else:
            note(beat, "scene drawn again", "the scene could not be written again", missing=things)
    if not asked:
        return
    chapters = {chapter_of[beat] for beat in asked}
    again = seen_again(chapters)
    second = vision_review.recheck(again, lesson, {beat: before[beat] for beat in asked}, llm_call=judge, log=log)
    worse = worse_in(again, chapters)
    for beat, things in asked.items():
        seen = second.get(beat) or {"cured": [], "still": before[beat], "new": []}
        why = ("nothing it had was cured" if not seen["cured"] else
               "its words now speak of something else the scene lacks" if seen["new"] else
               "its chapter's layout got worse" if chapter_of[beat] in worse else "")
        note(beat, "scene drawn again", why, missing=things, cured=[f["what"] for f in seen["cured"]],
             still=[f["what"] for f in seen["still"]], new=seen["new"], describe=now(beat)["figure"].get("describe", ""))
        if why:
            put_back(beat)
        log(f"[compose] beat {beat}: " + (f"its scene drawn again was not kept ({why}); it is as it was" if why else
                                          f"its scene drawn again now shows {', '.join(things)[:90]} "
                                          f"({len(seen['cured'])} of {len(before[beat])} thing(s) found cured)"))


def drawn_by_code(lesson: dict) -> bool:
    """Whether a lesson has a picture that code draws (a figure, a model-written scene): the kind that can be enlarged."""
    return any(isinstance(beat.get("figure"), dict) and beat["figure"].get("kind") not in lesson_look.DRAWN_FOR_YOU + (None, "")
               for chapter in lesson.get("chapters") or [] for beat in chapter.get("beats") or [])


def settle(lesson: dict, root: str | Path, judge=None, log=print, jobs: int | None = None, keep_words: bool = False) -> dict | None:
    """Preview ``lesson`` (which carries its ``look``), settle what of the look is settled by trying, report the rest.

    Changes ``lesson["look"]["pictures"]`` in place when enlarging the code-drawn pictures passes its preview.
    Returns the summary that is also written to ``<root>/composition.json``; None when the step is off or the lesson
    is not in the stage frame (the old frame is not previewed: nothing about it is to be chosen).
    """
    if jobs is None:
        jobs = knobs.render_jobs()
    look = lesson.get("look") if isinstance(lesson.get("look"), dict) else None
    if not enabled() or not look or look.get("frame") != "stage":
        return None
    root, began = Path(root), time.time()
    work = root / "preview"
    tried = {"kept": preview.stills(root, work=work / "kept", lesson={**lesson, "look": {**look, "pictures": "kept"}}, jobs=jobs, log=log)}
    chosen = "kept"
    if drawn_by_code(lesson) and not tried["kept"]["failed"]:
        tried["fill"] = preview.stills(root, work=work / "fill", lesson={**lesson, "look": {**look, "pictures": "fill"}}, jobs=jobs, log=log)
        if not tried["fill"]["failed"] and preview.faults(tried["fill"]) <= preview.faults(tried["kept"]):
            chosen = "fill"
        log(f"[compose] pictures drawn by code, enlarged to the room they have: {preview.faults(tried['fill'])} fault(s) in the "
            f"preview against {preview.faults(tried['kept'])} as they were; " + ("enlarged" if chosen == "fill" else "left as they were"))
    look["pictures"] = chosen
    result = tried[chosen]
    looked = None
    if looking():
        try:
            from . import vision_review  # noqa: PLC0415
            judge = judge or vision_review.default_judge(temperature=0.0)
            looked = vision_review.assess(result, lesson, llm_call=judge, log=lambda *a: None) if judge else None
        except Exception as exc:  # noqa: BLE001 - a second pair of eyes is an improvement, never a requirement
            log(f"[compose] the stills were not looked at ({type(exc).__name__}: {str(exc)[:120]})")
    seen = [{"beat": row["beat"], **finding} for row in (looked or {}).get("detail") or [] for finding in row.get("findings") or []]
    summary = {"pictures": chosen, "stills": len(result["stills"]), "timing": result["timing"],
               "faults": {name: preview.faults(one) for name, one in tried.items()},
               "measured": result["findings"], "seen": seen, "looked_at": (looked or {}).get("frames", 0),
               "seconds": round(time.time() - began, 1)}
    for finding in result["findings"]:
        log(f"[compose] beat {finding['beat']}: {finding['what']}")
    for finding in seen:
        if finding.get("severity") == "high":
            log(f"[compose] beat {finding['beat']}, seen in its still: {finding['what'][:150]}")
    log(f"[compose] previewed in {summary['seconds']:.0f} s: {len(result['findings'])} thing(s) measured, "
        + (f"{len(seen)} seen in {summary['looked_at']} stills ({sum(1 for f in seen if f.get('severity') == 'high')} of them plain)"
           if looked else "the stills were not looked at"))
    if looked and mending():
        try:
            summary["mended"] = mend(lesson, root, result, looked, judge=judge, keep_words=keep_words, log=log, jobs=jobs)
        except Exception as exc:  # noqa: BLE001 - a lesson that could not be mended is the lesson as it was
            log(f"[compose] nothing was mended ({type(exc).__name__}: {str(exc)[:140]})")
    try:
        (root / "composition.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
        for name in tried:                                # the stills of the look that was not chosen are not kept
            if name != chosen:
                shutil.rmtree(work / name, ignore_errors=True)
        for part in ("media", "audio"):
            shutil.rmtree(work / chosen / part, ignore_errors=True)
    except OSError:
        pass
    return summary
