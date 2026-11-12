"""A lesson planned by Lesson Forge, made into a video here.

Lesson Forge (``/api/forge/v1`` on a lesson-board server) plans a course as lectures briefed as one story, and builds
each keypoint of a lecture as renderer-neutral sections, each with the words said over it (schema ``forge/1``):

  narrate {say} · card {title, text, say, lines_said, your_turn} · mark {card, text, say} ·
  graphic {layout, params, svg, text, computed, say, lines_said} · image {query, caption, say} · source {say} ·
  check {question, answer, choices: [{text, correct, feedback}], pairs}

Here a lecture becomes ``lesson.json`` the way the writer's own script does (``writer.discipline``): a keypoint is a
chapter, a card or a graphic is a beat whose narration is everything said over it, each line of a card is a step that
appears on its own sentence, a check is a question the player stops on (its per-choice feedback kept as ``why``)
followed by a beat that SAYS the answer. Forge's plots are drawn by ``figures.graph`` from the functions themselves
(every fact on them computed again here); a number line becomes ``figures.number_line``; any other Forge graphic is
its SVG, taken apart by ``diagrams.take_apart`` so the renderer can draw it part by part with the words.

From then on the lesson goes through the same stages as any other (``service._run_job``): the critic checks every
claim with code and may rewrite, the questions pass improves the cards, then compose, speech, render and checks.

``Client`` talks to the API; ``lesson_from_forge`` is pure apart from writing the SVG drawings into the library.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import frameworks, writer

GENERATED_BY = "lesson forge"
SCHEMA = "forge/1"
MAX_BEATS = 40
_GREETING = re.compile(r"^\s*(?:hi|hello|hey|namaste|welcome)\b[^.!?]{0,60}[.!?]\s*", re.I)
_EQUATION = re.compile(r"^[\s\w().+\-*/^=<>≤≥×÷√²³,:]*[=<>≤≥][\s\w().+\-*/^=<>≤≥×÷√²³,]*$")
_PRAISE = re.compile(r"^(?:(?:correct|exactly|right|yes|great|well done|perfect|good job|spot on|that's right)\b[.!,]*\s*)+", re.I)
_LANGUAGES = {"en": "en-IN", "hi": "hi-IN", "hinglish": "hinglish", "te": "te-IN", "ta": "ta-IN"}


def is_forge(brief: dict) -> bool:
    return isinstance(brief, dict) and brief.get("mode") == "forge"


# ── the API ─────────────────────────────────────────────────────────────────────────────────────────────────────────

class Client:
    """Lesson Forge over HTTP. ``base`` is the server (``https://…`` or ``http://localhost:8000``); ``user_id`` a
    signed-in learner there (credits: 1 per plan, 1 per keypoint built); ``token`` its bearer token when the server
    checks accounts."""

    def __init__(self, base: str, user_id: str, token: str | None = None, timeout: float = 600):
        self.base, self.user_id, self.timeout = base.rstrip("/") + "/api/forge/v1", user_id, timeout
        self.headers = {"content-type": "application/json"} | ({"authorization": f"Bearer {token}"} if token else {})

    def _post(self, path: str, body: dict, stream: bool = False):
        import requests  # noqa: PLC0415
        r = requests.post(self.base + path, json={"user_id": self.user_id, **body}, headers=self.headers,
                          timeout=self.timeout, stream=stream)
        if r.status_code >= 400:
            raise RuntimeError(f"Lesson Forge {path}: HTTP {r.status_code}: {r.text[:300]}")
        return r

    def plan(self, topic: str, level: str, language: str = "en", goal: str = "", answers: dict | None = None,
             depth: str = "standard") -> dict:
        return self._post("/plan", {"topic": topic, "level": level, "language": language, "goal": goal,
                                    "answers": answers or {}, "depth": depth}).json()

    def build(self, plan: dict, lecture: int = 0, keypoints: list[int] | None = None, learner: str = "class",
              log=print) -> dict:
        """One lecture built: ``{"start", "keypoints": [...in order], "errors", "done"}``."""
        r = self._post("/build", {"plan": plan, "lecture": lecture, "keypoints": keypoints or [], "learner": learner,
                                  "targets": ["svg"]}, stream=True)
        out = {"start": {}, "keypoints": [], "errors": [], "done": {}}
        event = None
        for raw in r.iter_lines(decode_unicode=True):
            if raw.startswith("event:"):
                event = raw[6:].strip()
            elif raw.startswith("data:"):
                data = json.loads(raw[5:])
                if event == "keypoint":
                    out["keypoints"].append(data)
                    log(f"[forge] built keypoint {data['keypoint'] + 1}: {data['title']}")
                elif event == "error":
                    out["errors"].append(data)
                    log(f"[forge] keypoint {data.get('keypoint', 0) + 1} failed: {data.get('message')}")
                elif event in ("start", "done"):
                    out[event] = data
        out["keypoints"].sort(key=lambda k: k["keypoint"])
        return out


# ── sections → the writer's raw lesson ──────────────────────────────────────────────────────────────────────────────

def _clean(text) -> str:
    text = re.sub(r"\*\*|__|`|#+\s*", "", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _sentence(text: str) -> str:
    text = _clean(text)
    return text if not text or text[-1] in ".!?।" else text + "."


def _anchor(sentence: str, language: str) -> str:
    """The first words of a sentence as the voice will say them: a step appears when they are spoken."""
    words = writer.speakable(_clean(sentence), language).split()
    return " ".join(words[:4]).rstrip(".,;:!?")


def _table_rows(lines: list[str]) -> list[str]:
    """A markdown table → one line per row ("x = 0, y = 10"): a step cannot show a grid, and its pipes were drawn as text."""
    out, head = [], None
    for ln in lines:
        if not (ln.startswith("|") and ln.endswith("|")):
            out.append(ln)
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if head is None:
            head = cells
            continue
        out.append(", ".join(f"{h} = {c}" if h else c for h, c in zip(head, cells)))
    return out


def _card_lines(text: str) -> tuple[str, list[str]]:
    """A card's markdown → (its first line when it is a heading, the lines under it)."""
    lines = _table_rows([ln.strip() for ln in str(text or "").splitlines() if ln.strip()])
    lines = [re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", ln).replace("**", "").strip() for ln in lines]
    lines = [ln for ln in lines if ln]
    return (lines[0], lines[1:]) if len(lines) > 1 else ("", lines)


def _kind(line: str) -> str:
    """An equation is set as maths; a sentence in the lesson font."""
    if "$" in line or re.search(r"\\(?:frac|sqrt|times|cdot|div|theta|pi|le|ge)\b", line):
        return "math"
    words = re.findall(r"[A-Za-z]{3,}", line)
    return "math" if _EQUATION.match(line) and len(words) <= 1 else "point"


def _math(line: str) -> str:
    out = line.replace("$$", "").replace("$", "")
    out = out.replace("×", r"\times ").replace("÷", r"\div ").replace("≤", r"\le ").replace("≥", r"\ge ")
    out = re.sub(r"\^(\d+|\w)", r"^{\1}", out).replace("√", r"\sqrt ")
    out = re.sub(r"(\d+)\s*/\s*(\d+)", r"\\frac{\1}{\2}", out)
    return out.replace("___", r"\underline{\quad}")


def _steps(lines: list[str], said: list[str], language: str, title: str = "", opening: str = "") -> list[dict]:
    """A card's steps: its title (and a first line under it) on the opening sentence, each line after on its own."""
    def step(line: str, sentence: str, kind: str = "") -> dict:
        kind = kind or _kind(line)
        return {"say": _anchor(sentence, language) if sentence else "", "show": _math(line) if kind == "math" else line[:90],
                "kind": kind}
    steps = [step(title[:80], opening or (said[0] if said else ""), "key")] if title else []
    lead = len(lines) - len(said)                       # lines with no sentence of their own go with the opening
    for i, line in enumerate(lines[:writer.MAX_STEPS - len(steps)]):
        steps.append(step(line, opening if i < lead else said[i - lead] if 0 <= i - lead < len(said) else ""))
    return steps


# The board's diagram kit (lesson-board web/kit.js): Forge's SVG names classes and leaves their colours to the page that
# shows it. A drawing taken out of the board needs them inside it, or every shape is black.
_PALETTE = {"purple": ("#EEEDFE", "#534AB7", "#3C3489"), "teal": ("#E1F5EE", "#0F6E56", "#085041"),
            "coral": ("#FAECE7", "#993C1D", "#712B13"), "pink": ("#FBEAF0", "#993556", "#72243E"),
            "gray": ("#F1EFE8", "#5F5E5A", "#444441"), "blue": ("#E6F1FB", "#185FA5", "#0C447C"),
            "green": ("#EAF3DE", "#3B6D11", "#27500A"), "amber": ("#FAEEDA", "#854F0B", "#633806"),
            "red": ("#FCEBEB", "#A32D2D", "#791F1F")}
_KIT = (".t{font-size:14px;font-weight:400;fill:#2C2C2A}.th{font-size:14px;font-weight:600;fill:#2C2C2A}"
        ".ts{font-size:12px;fill:#5F5E5A}.box{fill:#F1EFE8;stroke:#B4B2A9;stroke-width:1}"
        "path:not([stroke]):not([class]){stroke:#5F5E5A;stroke-width:1.5}"
        + "".join(f".c-{n}>rect,.c-{n}>circle,.c-{n}>ellipse,.c-{n}>polygon,.c-{n}>path,rect.c-{n},circle.c-{n},ellipse.c-{n},"
                  f"polygon.c-{n},path.c-{n}{{fill:{f};stroke:{st};stroke-width:1}}"
                  f".c-{n}>line,.c-{n}>polyline,line.c-{n},polyline.c-{n}{{stroke:{st};fill:none}}"
                  f".c-{n}>.t,.c-{n}>.th{{fill:{t}}}.c-{n}>.ts{{fill:{st}}}.c-{n}>.frame,.c-{n}>.arr{{stroke:{st}}}"
                  for n, (f, st, t) in _PALETTE.items())
        + '[fill="none"]{fill:none}.arr{stroke:#73726c;stroke-width:1.5;fill:none!important;stroke-linecap:round;'
          "stroke-linejoin:round}.leader{stroke:#888780;stroke-width:1;stroke-dasharray:3 3;fill:none!important}"
          ".frame{fill:none!important;stroke-width:2;stroke:#5F5E5A}.em{stroke-width:2.5!important}"
          "text{font-family:Lato,'Atkinson Hyperlegible',Arial,sans-serif}")


def standalone_svg(fragment: str) -> str | None:
    """Forge's figure markup (a ``<style>`` for the board's fade-in, the ``<svg>``, a caption ``<p>``) → one SVG file
    that draws the same on its own: namespaced, with the kit's colours inside and no animation."""
    match = re.search(r"<svg\b[^>]*>.*</svg>", fragment or "", re.S)
    if not match:
        return None
    svg = match.group(0)
    head = re.match(r"<svg\b[^>]*>", svg).group(0)
    attrs = re.sub(r"\s(?:class|role)=\"[^\"]*\"", "", head[4:-1])
    if "xmlns=" not in attrs:
        attrs = ' xmlns="http://www.w3.org/2000/svg"' + attrs
    box = re.search(r'viewBox="[\d.\s-]+\s([\d.]+)\s([\d.]+)"', attrs)
    if box and "width=" not in attrs:
        attrs += f' width="{box.group(1)}" height="{box.group(2)}"'
    body = svg[len(head):-len("</svg>")].replace(' hk-n"', '"').replace('class="hk-n"', "")
    return f"<svg{attrs}><style>{_KIT}</style>{body}</svg>"


# Layouts whose drawing has been seen to say something wrong. A wrong picture is worse than none:
# Forge's tape put both sides of "3x + 5 = 14" on one tape and printed "Total: 22" (2026-10-16).
UNTRUSTED_LAYOUTS = {"tape": "it draws an equation's two sides as one total"}


def _figure(section: dict, store: Path | None, log=print) -> dict | None:
    """A Forge graphic as a figure the renderer draws: a plot or a number line natively, anything else from its SVG."""
    layout, params, computed = section.get("layout") or "", section.get("params") or {}, section.get("computed") or {}
    if layout == "plot":
        functions = [f for f in (params.get("expression"), params.get("expression2")) if str(f or "").strip()]
        if functions:
            return {"kind": "graph", "functions": functions,
                    "x_range": [params.get("x_min", -5), params.get("x_max", 5)],
                    "x_label": params.get("x_label") or "", "y_label": params.get("y_label") or "",
                    "points": [{"x": p.get("x"), "label": p.get("label") or "", "open": bool(p.get("open"))}
                               for p in computed.get("points") or [] if isinstance(p, dict)]}
    if layout == "number_line" and computed.get("points"):
        lo, hi = (computed.get("range") or [-5, 5])[:2]
        return {"kind": "number_line", "min": lo, "max": hi,
                "points": [{"x": p["x"], "label": p.get("label") or f"{p['x']:g}", "role": "result" if p.get("open") else "given"}
                           for p in computed["points"][:6]]}
    if layout in UNTRUSTED_LAYOUTS:
        log(f"[forge] the {layout} graphic is left out: {UNTRUSTED_LAYOUTS[layout]}")
        return None
    svg = standalone_svg(section.get("svg") or "")
    if not svg or store is None:
        return None
    folder = store / hashlib.sha256(svg.encode()).hexdigest()[:16]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source.svg").write_text(svg, encoding="utf-8")
    whole = folder / "whole.png"
    if not whole.is_file():
        try:
            from . import diagrams  # noqa: PLC0415
            diagrams.take_apart(folder / "source.svg", log=log)
        except Exception as exc:  # noqa: BLE001 - a drawing that cannot be taken apart is still a picture
            log(f"[forge] the {layout} drawing was not taken apart ({type(exc).__name__}: {str(exc)[:100]})")
    if not whole.is_file():
        _rasterize(folder / "source.svg", whole, log=log)
    return {"kind": "picture", "file": str(whole), "ask": section.get("alt") or layout} if whole.is_file() else None


def _rasterize(svg: Path, png: Path, width: int = 1400, log=print) -> None:
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    tool = shutil.which("rsvg-convert")
    if not tool:
        log("[forge] no rsvg-convert or browser: a Forge drawing is left out")
        return
    subprocess.run([tool, "-w", str(width), "-b", "white", "-o", str(png), str(svg)], check=False, timeout=60)


def _beat(narration: str, steps=(), figure=None, pause: float = 0.0, quiz=None, visual: str = "") -> dict:
    beat = {"narration": narration, "steps": list(steps), "visual": visual, "thinking_pause_seconds": pause}
    if figure:
        beat["_figure"] = figure          # put back after writer.discipline, which keeps only the kinds a model may ask for
    if quiz:
        beat["quiz"] = quiz
    return beat


def chapter_beats(sections: list[dict], language: str, store: Path | None = None, first: bool = False, log=print) -> list[dict]:
    """One keypoint's sections → the raw beats of its chapter."""
    beats: list[dict] = []
    for sec in sections:
        kind, say = sec.get("type"), _sentence(sec.get("say"))
        if kind == "narrate":
            say = _GREETING.sub("", say)          # "Hi Riya!" belongs to the board, where the learner is known
            if say:
                beats.append(_beat(say))
        elif kind == "card":
            heading, lines = _card_lines(sec.get("text"))
            said = [s for s in (_sentence(x) for x in sec.get("lines_said") or []) if s]
            title = _clean(sec.get("title")) or heading
            under = ([heading] if heading and heading != title else []) + lines
            beats.append(_beat(" ".join([say] + said if say else said), _steps(under, said, language, title, say),
                               pause=4.0 if sec.get("your_turn") else 0.0, visual=f"card: {title}"))
        elif kind == "mark" and beats:
            prev = beats[-1]
            if say:
                prev["narration"] = (prev["narration"] + " " + say).strip()
            prev["steps"].append({"say": _anchor(say, language) if say else "", "show": _clean(sec.get("text"))[:90],
                                  "kind": "key", "highlight": True})
        elif kind == "graphic":
            said = [s for s in (_sentence(x) for x in sec.get("lines_said") or []) if s]
            sentences = [s for s in [say] + said if s]
            # "marked: Base (3) at x = 0" is Forge describing a point it drew; the point is on the graph with its
            # label, and as a line of working it read "marked : 0atx=0" on screen (2026-10-16).
            facts = [ln.lstrip("- ").strip() for ln in str(sec.get("text") or "").splitlines()[1:]
                     if ln.strip().startswith("- ") and not ln.lstrip("- ").strip().lower().startswith("marked")
                     ] if sec.get("layout") in ("plot", "number_line") else []
            figure = _figure(sec, store, log=log)
            steps = _steps(facts[:3], said, language, opening=say) if facts else []
            if sentences:
                beats.append(_beat(" ".join(sentences), steps, figure=figure, visual=f"{sec.get('layout')}: {sec.get('alt') or ''}"))
        elif kind in ("image", "source"):
            if say:
                caption = _clean(sec.get("caption"))
                beats.append(_beat(say, [{"say": _anchor(say, language), "show": caption[:80], "kind": "point"}] if caption else []))
        elif kind == "check":
            question = _sentence(sec.get("question"))
            choices = [c for c in sec.get("choices") or [] if isinstance(c, dict) and _clean(c.get("text"))]
            right = next((n for n, c in enumerate(choices) if c.get("correct")), None)
            quiz = None
            if 2 <= len(choices) <= 4 and right is not None:
                quiz = {"question": question, "options": [_clean(c["text"])[:60] for c in choices], "answer_index": right,
                        "explain": _clean(sec.get("answer"))[:160],
                        "why": [_clean(c.get("feedback")) or ("Right." if c.get("correct") else "Not this one.") for c in choices]}
            if question:
                beats.append(_beat(question, [{"say": _anchor(question, language), "show": question[:90], "kind": "key"}],
                                   pause=5.0, quiz=quiz))
                answer = _clean(sec.get("answer"))
                # The feedback a tapped choice gets opens with praise ("Correct! …"); spoken to everyone it praises an
                # answer nobody gave (the reviewer's finding on the first Forge lessons). Only its reason is said.
                told = _PRAISE.sub("", _clean(choices[right].get("feedback"))) if quiz else ""
                if answer or told:
                    # The answer to a question is always SPOKEN (CLAUDE.md, 2026-10-10): a learner who did not tap must still hear it.
                    said = (f"The answer is {answer.rstrip('.')}" if len(answer.split()) <= 4 else answer) if answer else ""
                    beats.append(_beat(" ".join(_sentence(x) for x in (said, told) if x),
                                       [{"say": "", "show": answer[:90], "kind": "point"}] if answer else []))
            for pair in sec.get("pairs") or []:
                if isinstance(pair, dict) and pair.get("term") and pair.get("meaning"):
                    beats.append(_beat(_sentence(f"{_clean(pair['term'])} means {_clean(pair['meaning'])}"),
                                       [{"say": "", "show": f"{_clean(pair['term'])}: {_clean(pair['meaning'])}"[:90], "kind": "point"}]))
    return beats


def lesson_from_forge(plan: dict, built: dict, lecture: int = 0, brief: dict | None = None,
                      store: Path | None = None, log=print) -> dict:
    """A built Forge lecture → a lesson dict that passes the lesson contract, labelled ``generated_by: lesson forge``."""
    if store is None:
        from .. import paths  # noqa: PLC0415
        store = paths.sub("library", "forge")
    lec = (plan.get("lectures") or [])[lecture]
    language = _LANGUAGES.get(str(plan.get("language") or "en"), "en-IN")
    kps = lec.get("keypoints") or []
    # What the reviewer holds the script to (critic._lesson_text): the plan's own goals, audience and the mistakes its
    # briefs say learners make. Without them the first review reported "no GOAL, no METHOD" as a major finding.
    mistakes = [m.group(0).strip() for kp in kps for m in re.finditer(r"[^.]*\b(?:often|mistake|forget|confuse|wrongly|"
                                                                      r"common error|misconception)\b[^.]*\.", str(kp.get("brief") or ""), re.I)]
    level = str(plan.get("level") or "")
    brief = dict(brief or {}, mode="forge", topic=plan.get("topic") or plan.get("title"), level=level, language=language,
                 goal="; ".join(str(kp.get("goal") or "").rstrip(".") for kp in kps if kp.get("goal"))[:600] or plan.get("goal") or "",
                 audience=brief.get("audience") if brief and brief.get("audience") else
                 (f"{level} students in India (NCERT syllabus)" if level else "school students"),
                 misconception=" ".join(mistakes[:2])[:400])
    framework = frameworks.get(brief.get("framework") or frameworks.recommend(brief.get("level")))
    chapters, total = [], 0
    for n, kp in enumerate(built.get("keypoints") or []):
        beats = chapter_beats(kp.get("sections") or [], language, store=store, first=n == 0, log=log)[:max(0, MAX_BEATS - total)]
        total += len(beats)
        if beats:
            chapters.append({"title": kp.get("title") or f"Part {n + 1}", "learning_goal": kp.get("goal") or kp.get("brief") or "",
                             "beats": beats})
    if not chapters:
        raise ValueError("Lesson Forge returned nothing that can be narrated for this lecture")
    raw = {"title": lec.get("title") or plan.get("title"), "thesis": lec.get("story") or plan.get("summary") or "",
           "anchor": lec.get("running_example") or "", "chapters": chapters,
           "method": [str(kp.get("goal") or kp.get("title")).strip()[:160] for kp in kps if kp.get("goal") or kp.get("title")]}
    lesson = writer.discipline(raw, brief, framework)
    planned = [b for c in chapters for b in c["beats"] if _clean(b["narration"])]
    made = [b for c in lesson["chapters"] for b in c["beats"]]
    if len(planned) == len(made):
        for raw_beat, beat in zip(planned, made):
            if raw_beat.get("_figure"):
                beat["figure"] = raw_beat["_figure"]
    lesson["generated_by"] = GENERATED_BY
    lesson["forge"] = {"schema": plan.get("schema") or SCHEMA, "course": plan.get("title"), "lecture": lecture,
                       "lecture_title": lec.get("title"), "story": lec.get("story") or "",
                       "keypoints": [{k: kp.get(k) for k in ("keypoint", "title", "goal", "brief", "moves", "builds_on")}
                                     for kp in built.get("keypoints") or []],
                       "failed": [e.get("keypoint") for e in built.get("errors") or []],
                       "cost_usd": (built.get("done") or {}).get("cost_usd")}
    lesson["continuity"] = writer.continuity(lesson)
    return lesson


def lesson_for(brief: dict, log=print) -> dict:
    """The lesson for a ``mode: "forge"`` brief, which carries what Lesson Forge planned and built
    (``forge: {plan, built, lecture}``): made again from it on every run, so "Try again" pays Forge nothing."""
    given = brief.get("forge") or {}
    plan, built = given.get("plan"), given.get("built")
    if not isinstance(plan, dict) or not isinstance(built, dict):
        raise ValueError("a forge brief needs forge.plan and forge.built (lessonforge forge fetches both)")
    lecture = int(given.get("lecture") or 0)
    # Only what decides the lesson goes into it: the review is kept under the lesson as it stands, so a brief that says
    # how to run (stop after the review, a fresh take) must not make the script read with --check differ from the one filmed.
    from . import store  # noqa: PLC0415
    lesson = lesson_from_forge(plan, built, lecture, brief={k: v for k, v in store.content(brief).items() if k != "forge"}, log=log)
    log(f"[forge] {lesson['title']!r}: {len(lesson['chapters'])} chapter(s), "
        f"{sum(len(c['beats']) for c in lesson['chapters'])} beat(s), {lesson['continuity']['words']} words from Lesson Forge")
    return lesson


def spoken_words(brief: dict) -> int:
    """Roughly how many words the lesson will say (for the cost estimate before it starts)."""
    words = 0
    for kp in ((brief.get("forge") or {}).get("built") or {}).get("keypoints") or []:
        for sec in kp.get("sections") or []:
            words += len(str(sec.get("say") or "").split()) + sum(len(str(x).split()) for x in sec.get("lines_said") or [])
            words += len(str(sec.get("question") or "").split()) + len(str(sec.get("answer") or "").split())
    return words


def brief_from(plan: dict, built: dict, lecture: int, **extra) -> dict:
    """The job brief for one built lecture."""
    lec = plan["lectures"][lecture]
    return {"mode": "forge", "topic": f"{plan.get('title') or plan.get('topic')}: {lec.get('title')}",
            "level": plan.get("level") or "", "language": _LANGUAGES.get(str(plan.get("language") or "en"), "en-IN"),
            "goal": plan.get("goal") or "", "forge": {"plan": plan, "built": built, "lecture": lecture}, **extra}


def writer_brief(plan: dict, lecture: int, built: dict | None = None, **extra) -> dict:
    """The other way to use a Forge plan: as the BRIEF for this package's own script writer (``writer.write_lesson``),
    which writes for a video (one voice, the figure inventory, the question rules) where Forge writes for a board.
    The plan's story, each keypoint's brief, moves and check aim reach the writer as the requester's own words about
    the lesson plan; its running example as the suggested example; its known mistakes as the misconception."""
    lec = plan["lectures"][lecture]
    kps = lec.get("keypoints") or []
    level = str(plan.get("level") or "")
    lines = [f"Course: {plan.get('title')}. This lesson is lecture {lecture + 1} of {len(plan['lectures'])}: "
             f"{lec.get('title')}. {lec.get('story') or ''}".strip()]
    if lecture > 0:
        lines.append("Learners have already had: " + "; ".join(str(x.get("title")) for x in plan["lectures"][:lecture]) + ".")
    for n, kp in enumerate(kps, 1):
        part = f"Part {n}: {kp.get('title')}. {kp.get('brief') or kp.get('goal') or ''}"
        if kp.get("opens_with"):
            part += f" Open it with: {kp['opens_with']}"
        if kp.get("check_aim"):
            part += f" Check: {kp['check_aim']}"
        if kp.get("moves"):
            part += " Teaching moves: " + ", ".join(str(m).replace("_", " ") for m in kp["moves"]) + "."
        lines.append(part)
    mistakes = [m.group(0).strip() for kp in kps for m in re.finditer(r"[^.]*\b(?:often|mistake|forget|confuse|wrongly|"
                                                                      r"common error|misconception)\b[^.]*\.", str(kp.get("brief") or ""), re.I)]
    return {"topic": f"{lec.get('title')} ({plan.get('topic') or plan.get('title')})", "subject": plan.get("title") or "",
            "level": level, "audience": f"{level} students in India (NCERT syllabus)" if level else "school students",
            "goal": "; ".join(str(kp.get("goal") or "").rstrip(".") for kp in kps if kp.get("goal"))[:600],
            "context": lec.get("running_example") or "", "misconception": " ".join(mistakes[:2])[:400],
            "duration_minutes": 4,          # Forge's own lecture minutes are for the board, with its pauses and taps
            "language": _LANGUAGES.get(str(plan.get("language") or "en"), "en-IN"),
            "notes": {"lesson plan": " ".join(lines)[:3000]}, **extra}
