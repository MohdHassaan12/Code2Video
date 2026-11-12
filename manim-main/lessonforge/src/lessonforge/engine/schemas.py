"""Pydantic schemas — the Scene DSL (storyboard shape) + request bodies."""
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

Direction = Literal[
    "UP", "DOWN", "LEFT", "RIGHT", 
    "UP_RIGHT", "UP_LEFT", "DOWN_RIGHT", "DOWN_LEFT"
]


SafeZone = Literal[
    "TOP_CENTER", "BOTTOM_CENTER", "TOP_LEFT", "TOP_RIGHT", 
    "LEFT_CENTER", "RIGHT_CENTER"
]


class RelativePosition(BaseModel):
    relative_to: str = Field(description="The exact 'id' of the target visual element this object is anchored to.")
    direction: Direction = Field(description="The direction relative to the target object (e.g., UP_RIGHT).")
    buffer: float = Field(default=0.5, description="The distance or padding from the target object. Usually 0.2 to 0.5.")
    relation: Literal["next_to", "inside"] = Field(
        default="next_to",
        description=(
            "How this object sits relative to the target. 'next_to' (default) places it beside the target in "
            "`direction`. 'inside' places it WITHIN the target's box — use it for contents of a container "
            "(candies in a tray, a number in a node, particles in a box). Several elements marked 'inside' the "
            "same target are automatically distributed in a grid within it and shrunk to fit, so declare each "
            "content item as its OWN element rather than describing them in the container's text. "
            "With 'inside', `direction` is ignored."
        ),
    )


class VisualElement(BaseModel):
    id: str = Field(description="Unique identifier for the element, e.g., 'x_axis_label'")
    type: Literal["text", "math", "shape", "svg_icon", "chemical_molecule", "coordinate_system", "graph", "math_evolution", "image", "simulation"] = Field(
        description="Type of visual element. Use 'math_evolution' when an equation transforms into another (e.g. F=ma → a=F/m); the renderer uses TransformMatchingTex between the 'from' and 'to' LaTeX strings separated by '→' in content. Use 'image' for real photographs/paintings/maps sourced from Wikimedia Commons (historical events, people, places, artifacts). Use 'simulation' for a system EVOLVING OVER TIME that a static diagram cannot express — a projectile tracing its arc, a wave propagating, particles diffusing, a pendulum swinging, an orbit; the server generates and verifies the animation code."
    )
    content: str = Field(description="Visual content. For math, provide LaTeX (no surrounding $). For text, standard string. For svg_icon, a clean singular English search keyword. For chemical_molecule, a valid SMILES string. For shape, a description. For coordinate_system or graph, include axis ranges in the format 'x:MIN-MAX, y:MIN-MAX' (e.g. 'pH scale x:0-14, y:0-7' or 'time vs velocity x:0-10 to 100, y:-50 to 50') — the renderer parses these to set correct Axes bounds. For math_evolution, use 'FROM_LATEX → TO_LATEX' with a literal → separator. For image, a concise English Wikimedia Commons search query of 2-5 words (e.g. 'Storming of the Bastille painting', 'Mahatma Gandhi Salt March 1930'). For simulation, ONE precise English sentence naming the system, what moves, and the quantities that must be visible (e.g. 'a ball launched at 45 degrees tracing a parabolic arc above a ground line, with its velocity arrow shrinking near the top').")
    color: Optional[str] = Field(None, description="Hex color (e.g. '#00FFCC') or standard Manim color name (e.g. 'BLUE')")
    entrance_animation: str = Field(description="Manim entrance animation, e.g., 'FadeIn', 'Write', 'Create'")
    exit_animation: str = Field(description="Manim exit animation, e.g., 'FadeOut', 'Uncreate'")
    scale: Optional[float] = Field(0.7, description="Scale factor to ensure safe zone bounding box compliance (recommend 0.7 or 0.8 for text/math)")
    
    absolute_position: Optional[List[float]] = Field(
        default=None, 
        description="[x, y] coordinates. ONLY use this for shapes or coordinate systems. NEVER use this for text labels."
    )
    
    relative_positioning: Optional[RelativePosition] = Field(
        default=None,
        description="MUST be used for text labels that describe a specific shape or point on the canvas."
    )
    
    safe_zone_alignment: Optional[SafeZone] = Field(
        default=None,
        description="MUST be used for standalone text (titles, questions). NEVER use 'ORIGIN' for standalone text."
    )

    connects: Optional[List[str]] = Field(
        default=None,
        description=(
            "Exactly TWO element ids, e.g. ['node_84', 'node_12']. Marks this element as an EDGE joining them: "
            "the renderer draws it from one shape's boundary to the other's and keeps it attached, so never give "
            "a connector a position of its own. Use it for every link in a diagram — factor-tree branches, "
            "flowchart arrows, bonds, force vectors between bodies. Both ids must be elements of THIS scene. "
            "If the shape's content mentions 'arrow', the edge is drawn with an arrowhead."
        ),
    )


class AnimationEvent(BaseModel):
    action: Literal["show", "hide", "transform", "highlight", "move_to", "focus"] = Field(
        description=(
            "'show': entrance animation for target (element must be in this scene's elements list). "
            "'hide': FadeOut the target — use to clean up finished elements. "
            "'transform': morph target into `to` element (TransformMatchingTex for math, else ReplacementTransform). "
            "'highlight': Indicate the target with a color flash for emphasis. "
            "'move_to': animate target to sit next to the `to` element. "
            "'focus': semantic spotlight — dim every other on-screen element while the narration "
            "is about the target, then restore. Use at most once per scene, for the beat that "
            "carries the scene's key idea; prefer 'highlight' for a quick flash."
        )
    )
    target: str = Field(description="element_id of the primary element to animate.")
    to: Optional[str] = Field(None, description="For 'transform': destination element_id. For 'move_to': reference element_id to position next to.")
    color: Optional[str] = Field(None, description="For 'highlight': hex color (e.g. '#FFFF00') or Manim color name (e.g. 'YELLOW').")
    direction: Optional[str] = Field(None, description="For 'move_to': Manim direction constant, e.g. 'RIGHT', 'DOWN', 'UP+RIGHT'. Defaults to RIGHT.")


class NarrationCue(BaseModel):
    cue: str = Field(description="The spoken narration text.")
    event: str = Field(
        default="",
        description="Legacy: comma-separated Manim animation strings (e.g. 'FadeOut(title_id)'). Ignored when animation_events is provided — prefer animation_events for new storyboards."
    )
    animation_events: Optional[List[AnimationEvent]] = Field(
        None,
        description=(
            "Structured animation events for this cue. Preferred over the free-text 'event' field. "
            "Use 'show' for element entrances (target must be in scene elements list), "
            "'hide' to FadeOut elements that are no longer needed, "
            "'transform' to morph one element into another (great for equation evolution), "
            "'highlight' to flash-emphasise an element with Indicate, "
            "'move_to' to reposition an element next to another. "
            "FadeOuts are batched into one play(); each other action fires in sequence."
        )
    )


class StoryboardScene(BaseModel):
    scene_index: int = Field(description="Scene sequence index starting at 1")
    description: str = Field(description="Description of the educational action or concept being shown in this scene")
    role: Optional[Literal["hook", "build", "turn", "payoff", "recap"]] = Field(
        None,
        description=(
            "This scene's job in the story arc. 'hook': open a concrete question or "
            "situation the viewer wants resolved. 'build': develop it one step further, "
            "continuing from the previous scene. 'turn': the insight, twist, or "
            "misconception correction that changes how the viewer sees it. 'payoff': "
            "resolve the hook's question explicitly. 'recap': close the loop and name "
            "what changed. A lesson is scenes in an ARC, not a list of sections."
        ),
    )
    elements: List[VisualElement] = Field(description="List of visual elements present or animated in this scene")
    narration_cues: List[NarrationCue] = Field(description="List of spoken cues and corresponding visual events (Temporal Contiguity)")
    wait_time: float = Field(description="Number of seconds to wait/pause before ending the scene")
    composition: Optional[str] = Field(
        None,
        description=(
            "Concise description of the overall visual composition and spatial arrangement of this scene. "
            "Describes how elements are positioned relative to each other on the canvas, e.g. "
            "'Title banner at top, large coordinate grid filling centre, axis labels directly on axes, "
            "derivation steps stacked in right column.' "
            "This is a scene-level composition intent descriptor that complements per-element positioning fields. "
            "The transpiler uses it to understand the intended layout gestalt."
        ),
    )
    layout_template: Optional[Literal[
        "TitleStageCaption", "SplitScreen", "FullCanvas", "ProcessFlow", "BeforeAfter"
    ]] = Field(
        None,
        description=(
            "Optional layout template for this scene. Pick the one matching the scene's pedagogical shape. "
            "'TitleStageCaption': first element anchors at TOP_CENTER (title), last at BOTTOM_CENTER (caption), "
            "middle elements fill the center stage. "
            "'SplitScreen': elements without explicit positioning alternate LEFT_CENTER / RIGHT_CENTER — "
            "ideal for compare-contrast or equation-vs-diagram splits. "
            "'ProcessFlow': a mechanism or process read left-to-right — the first unpositioned element starts "
            "at LEFT_CENTER, the last lands at RIGHT_CENTER, intermediate stages fill the centre stage. "
            "'BeforeAfter': the first half of unpositioned elements form the BEFORE state on the left, "
            "the second half the AFTER state on the right. "
            "'FullCanvas': no template constraints; positioning is fully manual via safe_zone_alignment / "
            "relative_positioning / absolute_position. "
            "Vary templates across scenes — the same template on 3+ consecutive scenes reads monotonous and is "
            "reset by the transpiler."
        ),
    )


class Narrative(BaseModel):
    """The spine that makes a set of scenes one video instead of several.

    Added 2026-08-14 after a user watched a projectile-motion render and reported
    "there is no story in the video being narrated, all the scenes are
    disconnected". The board that produced it was a correct syllabus — intro,
    components, independence, equations, quiz, summary — where every scene opened by
    re-declaring the topic and the ball introduced in scene 1 never came back.
    """

    through_line: str = Field(
        description=(
            "One sentence naming the question the whole video answers, phrased so a "
            "student would want the answer, e.g. 'Why does a thrown ball land where "
            "it does, and can we predict the spot before it lands?' Every scene must "
            "move this question forward."
        )
    )
    anchor: str = Field(
        description=(
            "ONE concrete running example that appears in EVERY scene and carries the "
            "abstraction, e.g. 'a basketball thrown toward a hoop'. Not a topic name — "
            "a specific thing the viewer can picture. Scene 1 introduces it, later "
            "scenes return to it as it gains detail, the last scene finishes its story."
        )
    )


class StoryboardResponse(BaseModel):
    topic: str = Field(description="The STEM topic/concept")
    narrative: Optional[Narrative] = Field(
        None, description="The story spine tying the scenes together (through_line + anchor)"
    )
    key_theorems: List[str] = Field(description="Core formulas, rules, or theorems relevant to this topic")
    key_terms: List[str] = Field(description="List of core scientific, technical, and mathematical terms in English (e.g. ['Angle of Depression', 'Horizontal Line', 'Line of Sight'])")
    style_profile: str = Field(description="Visual styling configuration (e.g. '3blue1brown/minimalist/neon' or 'chalkboard/pastel')")
    aspect_ratio: str = Field("widescreen", description="The planned aspect ratio of the animation: 'widescreen' or 'vertical'")
    visual_storyboard: List[StoryboardScene] = Field(description="Chronological list of scenes making up the full animation plan")


class TransliterationResponse(BaseModel):
    transliterated_cues: List[str] = Field(description="List of Hinglish transliterated cues using standard Latin script/English alphabet letters only")


class LabelTranslationResponse(BaseModel):
    translated_labels: List[str] = Field(description="List of on-screen labels translated to concise English (Latin alphabet only), preserving any LaTeX/math notation and numbers exactly")


class SlideContent(BaseModel):
    slide_index: int = Field(description="Index of the slide starting from 1")
    title: str = Field(description="Slide title")
    hook: str = Field(description="A hook mapping the scientific concept to the student's personal interest")
    explanation: str = Field(description="A clear, intuitive explanation of the STEM concept")
    hook_simulation: str = Field(description="Detailed description of an interactive simulation or concept sandbox using the student interest")
    narration_cues: List[NarrationCue] = Field(description="List of spoken cues and corresponding visual events (Temporal Contiguity)")
    image_prompt: str = Field(description="Midjourney/DALL-E prompt to generate a beautiful illustration for this slide")
    manim_video_prompt: str = Field(description="Prompt instructing Manim on what to animate for this slide")
    manim_code: str = Field(description="A complete, self-contained, valid Python class extending VoiceoverScene that compiles into a Manim video for this slide. Must include imports, voiceover service initialization (UniversalTTSService), and with self.voiceover contexts.")


class StudentCourseResponse(BaseModel):
    topic: str = Field(description="The scientific/STEM topic")
    interest: str = Field(description="The student's interest used for contextualization")
    style_profile: str = Field(description="Selected visual style profile")
    aspect_ratio: str = Field("widescreen", description="The planned aspect ratio of the animation: 'widescreen' or 'vertical'")
    slides: List[SlideContent] = Field(description="Sequence of personalized slide cards")


class StoryboardRequest(BaseModel):
    topic: str
    persona: str = "hybrid"
    language: str = "hi-IN"
    speaker: str = "shubh"
    tts_provider: str = "sarvam"
    gemini_tts_model: str = "google/gemini-3.1-flash-tts-preview"
    style: str = "3blue1brown/minimalist/neon"
    context: Optional[dict] = None
    # Source material to ground the storyboard in: YouTube links, article URLs, or
    # pasted notes (plain strings are auto-classified; a dict may set
    # {"kind": "youtube"|"web"|"text", "url"/"text"/"title"}). Merged into
    # `context["sources"]`, which is what the deep storyboard path reads. Grounding
    # only takes effect on the deep path (DEEP_STORYBOARD=1); the single call keeps
    # using `context["grounding_chunks"]` as before.
    sources: Optional[List] = None
    # How technical terms are spoken in narration: "english" (never translated —
    # no "point, yaani bindu"), "bilingual" (native equivalent once at first
    # mention), or "native" (translated throughout).
    tech_terms: str = "english"
    # Target video length in seconds. When set, the storyboard prompt derives its
    # scene count AND a total narration word budget from it (the words ARE the
    # runtime — TTS bills and paces by duration), and it partitions the storyboard
    # cache (appended as a key variant only when set, so requests without it keep
    # their exact prior cache keys). Unset = the legacy 60–90 s guidance.
    target_duration_s: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class ResearchRequest(BaseModel):
    """Body for /api/research — source intake preview, no generation, no LLM call."""
    topic: str = ""
    sources: List = []
    grade: str = ""
    subject: str = ""
    auto_search: Optional[bool] = None


class CodegenRequest(BaseModel):
    storyboard: dict
    style: str = "3blue1brown/minimalist/neon"
    background: str = "default"
    persona: str = "hybrid"
    language: str = "hi-IN"
    speaker: str = "shubh"
    tts_provider: str = "sarvam"
    gemini_tts_model: str = "google/gemini-3.1-flash-tts-preview"
    skip_layout_review: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class CompileRequest(BaseModel):
    code: str
    scene_class: str = "STEMAnimation"
    quality: str = "l"
    aspect_ratio: str = "widescreen"
    persona: str = "hybrid"
    scene_scripts: Optional[List[str]] = None
    # Allowlisted pipeline knobs (see _apply_env_overrides). Process-global:
    # last submission wins for concurrently running jobs — fine for the
    # single-user debugger/bulk flows this exists for.
    env_overrides: Optional[Dict[str, str]] = None


class StudentSlidesRequest(BaseModel):
    topic: str
    interest: str
    style: str = "3blue1brown/minimalist/neon"
    background: str = "default"
    language: str = "hi-IN"
    speaker: str = "shubh"
    tts_provider: str = "sarvam"
    gemini_tts_model: str = "google/gemini-3.1-flash-tts-preview"


class SimRequest(BaseModel):
    topic: str = ""
    interest: str = ""
    hook_simulation: str = ""
    style: str = "3blue1brown/minimalist/neon"
    background: str = "default"
    language: str = "hi-IN"
    speaker: str = "shubh"
    tts_provider: str = "sarvam"
    gemini_tts_model: str = "google/gemini-3.1-flash-tts-preview"
    skip_layout_review: bool = False


class PreflightRequest(BaseModel):
    storyboard: dict = {}


class ProbeAssetRequest(BaseModel):
    type: str = "svg_icon"
    keyword: str = ""


class BatchRenderRequest(BaseModel):
    nodes: list
    style: str = "3blue1brown/minimalist/neon"
    background: str = "default"
    persona: str = "hybrid"
    language: str = "hi-IN"
    speaker: str = "shubh"
    tts_provider: str = "sarvam"
    gemini_tts_model: str = "google/gemini-3.1-flash-tts-preview"
    quality: str = "l"
    aspect_ratio: str = "widescreen"
    skip_layout_review: bool = False
    env_overrides: Optional[Dict[str, str]] = None
    tech_terms: str = "english"  # see StoryboardRequest.tech_terms
