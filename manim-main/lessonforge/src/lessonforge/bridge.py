"""The bridge: one lesson, either production path.

The two halves of this package agree on what a lesson IS (words, picture intent,
on-screen text, equations) and differ in who decides timing and geometry:

    engine    a model writes a storyboard IR → the transpiler owns layout and motion,
              speech is synthesized per cue during the render
    longform  a person approves a script → speech is synthesized and measured first,
              scenes are written (or generated) against that timeline

So a lesson can move between them without loss of the parts both understand:

``lesson_to_storyboard``  renders an approved long-form script through the engine's
    deterministic transpiler — layout enforcement, theming and the repair loop
    included — with no scene code and no model call. It is a *floor*, not a
    director: one text panel and one equation per beat. A storyboard model can then
    be asked to enrich exactly this board while the narration stays fixed.

``storyboard_to_lesson``  takes a board the engine generated and turns it into a
    lesson contract, so a short generated video can be re-narrated in blocks,
    captioned, chaptered and checked by the long-form build.

Both directions are pure data → data and import neither manim nor the server.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from .longform.contract import Beat, Chapter, Lesson, split_sentences

_PACING_TAG = re.compile(r"\[[^\]]{1,24}\]|<[^>]{1,24}>")


def _engine_schemas():
    """The storyboard IR models, loaded WITHOUT booting the engine.

    ``import lessonforge.engine.schemas`` would run ``engine/__init__`` (FastAPI app,
    environment self-healing, workspace creation). The models themselves are plain
    Pydantic with no package-relative imports, so they load fine by path.
    """
    path = Path(__file__).resolve().parent / "engine" / "schemas.py"
    spec = importlib.util.spec_from_file_location("lessonforge_engine_schemas_standalone", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _slug(text: str, limit: int = 24) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:limit] or "x"


def lesson_to_storyboard(lesson: Lesson, chapter_id: int | None = None,
                         style: str = "3blue1brown", validate: bool = True) -> dict[str, Any]:
    """Lesson (or one chapter of it) → a ``StoryboardResponse``-shaped dict.

    One scene per beat. The narration is carried over verbatim, one cue per sentence;
    the beat's board text and equation become a left/right split, the equation
    arriving mid-beat so the frame changes while the voice is still going.
    """
    chapters = [lesson.chapter(chapter_id)] if chapter_id is not None else lesson.chapters
    beats = [(c, b) for c in chapters for b in c.beats]
    scenes = []
    for index, (chapter, beat) in enumerate(beats, start=1):
        sentences = beat.sentences or [beat.narration]
        tag = f"s{index}"
        elements = [{
            "id": f"{tag}_title", "type": "text", "content": chapter.title.title(),
            "entrance_animation": "FadeIn", "exit_animation": "FadeOut", "scale": 0.8,
            "safe_zone_alignment": "TOP_CENTER",
        }]
        first_events = [{"action": "show", "target": f"{tag}_title"}]
        later_events: list[dict] = []
        if beat.board_text:
            elements.append({
                "id": f"{tag}_board", "type": "text", "content": beat.board_text,
                "entrance_animation": "Write", "exit_animation": "FadeOut", "scale": 0.7,
                "safe_zone_alignment": "LEFT_CENTER" if beat.equation else "BOTTOM_CENTER",
            })
            first_events.append({"action": "show", "target": f"{tag}_board"})
        if beat.equation:
            elements.append({
                "id": f"{tag}_eq", "type": "math", "content": beat.equation,
                "entrance_animation": "Write", "exit_animation": "FadeOut", "scale": 0.8,
                "safe_zone_alignment": "RIGHT_CENTER" if beat.board_text else "BOTTOM_CENTER",
            })
            later_events.append({"action": "show", "target": f"{tag}_eq"})
        reveal_at = len(sentences) // 2 if len(sentences) > 1 else 0
        cues = []
        for i, sentence in enumerate(sentences):
            events = (first_events if i == 0 else []) + (later_events if i == reveal_at else [])
            cues.append({"cue": sentence, "event": "", "animation_events": events or None})
        scenes.append({
            "scene_index": index,
            "description": beat.visual or beat.check or chapter.learning_goal or chapter.title,
            "role": "hook" if index == 1 else "recap" if index == len(beats) and len(beats) > 2 else "build",
            "elements": elements,
            "narration_cues": cues,
            "wait_time": 0.6 + float(beat.thinking_pause_seconds),
            "composition": "Chapter title top; board wording left; equation right.",
            "layout_template": "FullCanvas",
        })
    theorems = list(dict.fromkeys(b.equation for _, b in beats if b.equation))
    board = {
        "topic": lesson.title,
        "narrative": ({"through_line": lesson.thesis, "anchor": getattr(lesson, "anchor", None) or lesson.title}
                      if lesson.thesis else None),
        "key_theorems": theorems[:8],
        "key_terms": list(getattr(lesson, "key_terms", None) or []),
        "style_profile": style,
        "aspect_ratio": "widescreen",
        "visual_storyboard": scenes,
    }
    if validate:
        board = _engine_schemas().StoryboardResponse.model_validate(board).model_dump()
    return board


def storyboard_to_lesson(storyboard: dict[str, Any], language: str = "en-IN",
                         scenes_per_chapter: int | None = None) -> Lesson:
    """An engine storyboard → a lesson contract (one beat per scene).

    Pacing tags the engine writes into cues (``[pause]``, ``<break>``) are removed:
    in the long-form contract narration is exactly what is spoken, and silence is a
    number (``thinking_pause_seconds``), never a token in the text.
    """
    scenes = storyboard.get("visual_storyboard") or []
    if not scenes:
        raise ValueError("storyboard has no scenes")
    size = scenes_per_chapter or len(scenes)
    chapters = []
    for start in range(0, len(scenes), size):
        group, beats = scenes[start:start + size], []
        for scene in group:
            spoken = " ".join(_PACING_TAG.sub(" ", c.get("cue", "")).strip() for c in scene.get("narration_cues", []))
            spoken = re.sub(r"\s+", " ", spoken).strip()
            if not spoken:
                continue
            by_type = {}
            for element in scene.get("elements", []):
                by_type.setdefault(element.get("type"), element.get("content", ""))
            beats.append(Beat(
                id=f"{int(scene.get('scene_index', len(beats) + 1)):02}",
                narration=spoken,
                visual=scene.get("composition") or scene.get("description", ""),
                board_text=by_type.get("text", ""),
                equation=by_type.get("math", ""),
                thinking_pause_seconds=0.0,
                check=scene.get("description", ""),
            ))
        if beats:
            number = len(chapters) + 1
            title = storyboard.get("topic", "Lesson") if size >= len(scenes) else \
                f"{storyboard.get('topic', 'Lesson')} — part {number}"
            chapters.append(Chapter(id=number, title=title, beats=beats))
    narrative = storyboard.get("narrative") or {}
    return Lesson(title=storyboard.get("topic", "Lesson"), thesis=narrative.get("through_line", ""),
                  language=language, chapters=chapters)


def transpile(storyboard: dict[str, Any], language: str = "en-IN", speaker: str = "shubh",
              persona: str = "en", background: str = "default", tts_provider: str = "sarvam",
              style: str = "", per_scene: bool = False):
    """Storyboard → Manim source via the engine's deterministic transpiler.

    Returns one script, or with ``per_scene=True`` the list of standalone per-scene
    scripts the engine renders in parallel. No model is called.
    """
    from . import transpiler
    fn = transpiler.parse_schema_to_scene_scripts if per_scene else transpiler.parse_schema_to_base_scene
    return fn(storyboard, language=language, speaker=speaker, persona=persona, background=background,
              tts_provider=tts_provider, asset_warnings=None, style=style)
