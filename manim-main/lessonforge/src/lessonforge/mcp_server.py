"""Lessonforge as an MCP server: Claude (in a chat, in Claude Code, or over the API) drives the workbench.

    lessonforge mcp                      # stdio, for Claude Code / Claude Desktop
    lessonforge mcp --http --port 8765   # streamable HTTP, for a server Claude connects to

Claude Code:  claude mcp add lessonforge -- lessonforge mcp

Every tool but ``draft_unit`` is free (code checks, low-quality stills, a local voice, measurements of the file).
``draft_unit`` asks lessonforge's own pack writer for a lesson: a few cents of OpenRouter credit, metered by
``spend`` and refused once the account's cap is reached. The tools return plain JSON; ``preview`` also returns
the contact sheet as an image so Claude can look at what the learner will see.
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP, Image

from . import kits
from .harness import workbench as W

server = FastMCP("lessonforge", instructions=(
    "Lessonforge makes narrated lesson videos. Work on one lesson at a time: check it, preview it, make small "
    "edits, check again, and film it only when check finds no faults. Geometry pictures are drawn by code from "
    "points: never type a measured value, write a gap such as {angle D} and code fills it. Each beat should change "
    "the screen with its sentences (a step per sentence), and each beat should add to its picture rather than "
    "repeat it." + (" " + kits.mcp_note() if kits.mcp_note() else "")))


def _quiet(*_args, **_kw) -> None:
    pass


@server.tool()
def list_lessons() -> list[dict]:
    """The lessons on the workbench, with their number of versions."""
    return W.lessons()


@server.tool()
def pack_units(pack_file: str) -> list[dict]:
    """The units of a teaching pack (a Markdown file with '# 3. Title' units and '## A ...' sections)."""
    return W.units(pack_file)


@server.tool()
def draft_unit(pack_file: str, unit: int, language: str = "en-US") -> dict:
    """PAID (a few cents): lessonforge's own writer drafts a unit of a pack; code checks every value and claim."""
    return W.draft_pack(pack_file, unit, language, log=_quiet)


@server.tool()
def add_lesson(lesson_json: str, name: str = "") -> dict:
    """Put a lesson (lessonforge's lesson JSON) on the workbench. Returns its id, faults and craft numbers."""
    return W.add(json.loads(lesson_json), name or None, source="mcp")


@server.tool()
def get_lesson(lesson_id: str, version: int | None = None) -> dict:
    """The lesson's JSON (newest version unless one is named)."""
    return W.load(lesson_id, version)


@server.tool()
def check_lesson(lesson_id: str) -> dict:
    """Free. Faults found by code (wrong values, claims the points do not make, words not spoken in order) and
    craft numbers: sentences with no screen change, beats that repeat the picture before them, long screen words."""
    return W.check(lesson_id)


@server.tool()
def preview(lesson_id: str, chapters: list[int] | None = None) -> list:
    """Free, under a minute. Stills of every step as a contact sheet image, plus the layout's own findings."""
    found = W.preview(lesson_id, chapters, log=_quiet)
    out: list = [json.dumps({k: v for k, v in found.items() if k != "sheet"})]
    if found.get("sheet"):
        out.append(Image(path=found["sheet"]))
    return out


@server.tool()
def edit_lesson(lesson_id: str, edits: list[dict], why: str = "") -> dict:
    """Small changes, checked at once. Each edit is one of:
    {"op":"set_beat","beat":"04","fields":{"narration":..,"steps":[{"say":..,"show":..,"kind":"point|key|math"}],
      "figure":{..},"quiz":{..}}}  (a field set to null is removed)
    {"op":"insert_beat","after":"04","beat":{"narration":..,"steps":[..],"figure":{..}}}
    {"op":"delete_beat","beat":"04"}
    {"op":"set_shape","name":"arrow","shape":{"points":{"A":[0,0],..},"polygon":"ABCD","is":["concave"]}}
    An edit that adds faults is not kept; the reply lists them."""
    return W.edit(lesson_id, edits, by="claude (mcp)", why=why)


@server.tool()
def revert(lesson_id: str, version: int) -> dict:
    """Make an earlier version the newest again."""
    return W.revert(lesson_id, version, by="claude (mcp)")


@server.tool()
def lesson_history(lesson_id: str) -> list[dict]:
    """Every version: who made it, why, and the edits."""
    return W.history(lesson_id)


@server.tool()
def film(lesson_id: str, voice: str = W.DEFAULT_VOICE) -> dict:
    """Free with the default local voice; several minutes. Films the newest version; refuses one with faults."""
    return W.film(lesson_id, voice=voice, log=_quiet)


@server.tool()
def review_video(lesson_id: str) -> dict:
    """Free. The newest film measured: share of half-seconds where the screen changes (good lectures 81-92%),
    longest still stretch, silence, words a minute; with the script's craft numbers."""
    return W.review(lesson_id)


@server.tool()
def judge_frames(lesson_id: str, cap_usd: float = 0.03) -> dict:
    """PAID (about 0.65 US cents a video): a vision model judges one frame per spoken sentence of the newest film
    (does the picture and the screen text go with the words?). Frames that did not change are found free."""
    from .harness import frame_judge
    return frame_judge.judge(lesson_id, cap_usd=cap_usd, log=_quiet)


@server.tool()
def list_kits() -> dict:
    """Free. The subject kits (what each draws, its subjects, classes and keywords, served or legacy) and the
    lesson-visuals components on offer."""
    from .harness import kit_pipeline
    return kit_pipeline.list_kits()


@server.tool()
def describe_kit(name: str) -> dict:
    """Free. One kit in full: what it draws, the rules a writer is given for it, example figures. A component kit also
    lists every component with its parts and states."""
    from .harness import kit_pipeline
    return kit_pipeline.describe_kit(name)


@server.tool()
def route_kits(text: str, classes: str = "", subjects: str = "") -> dict:
    """Free, no model. Which kit should draw each part of a brief (a paragraph, a list item or a sentence), chosen by code
    from the kits' own keywords, subjects and classes (1 to 12). A part nothing fits gets kit null. Classes such as
    "7,8" and subjects such as "physics,chemistry" are optional filters."""
    from .harness import kit_pipeline
    return kit_pipeline.route_text(text, classes or None, subjects or None)


@server.tool()
def run_kit_pipeline(brief_text: str, lesson_json: str = "", classes: str = "", subjects: str = "", preview: bool = False) -> dict:
    """Free, check only (no model is called, nothing is filmed). Routes the brief to kits, then checks a ready lesson
    (lessonforge's lesson JSON) with every kit's model, settles its gaps and puts it on the workbench. The report lists
    the plan, the lesson id, the faults left, the craft numbers and the steps taken. With no lesson it stops after the
    plan: write the lesson yourself from the plan's hints and the kits' rules, add it here, then edit until check is clean.
    Film separately with the film tool."""
    from .harness import kit_pipeline
    report = kit_pipeline.run(brief_text, lesson=lesson_json or None, classes=classes or None, subjects=subjects or None,
                              preview=preview, log=_quiet)
    return report.to_dict()


def main(http: bool = False, host: str = "127.0.0.1", port: int = 8765) -> None:
    if http:
        server.settings.host, server.settings.port = host, port
        server.run(transport="streamable-http")
    else:
        server.run()


if __name__ == "__main__":
    main()
