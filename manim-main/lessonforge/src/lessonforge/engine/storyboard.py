"""Storyboard stage (the DSL producer): generate the scene storyboard, the
pre-cache shape/language gate, on-screen-language healing, and the storyboard cache."""
import os
import re
import json
import time
import hashlib
import logging

from .llm import call_llm_with_fallback, loads_json_lenient
from .assets import extract_non_manim_items, _collect_asset_elements
from .schemas import (StoryboardResponse, TransliterationResponse,
                      LabelTranslationResponse)

logger = logging.getLogger(__name__)
from .. import paths as _paths

_INDIC_ANY = re.compile(
    r'[ऀ-ॿঀ-৿਀-੿઀-૿଀-୿஀-௿ఀ-౿ಀ-೿ഀ-ൿ]'
)


_ROMAN_HINDI_STOPWORDS = re.compile(
    r'\b(hai|hain|hoga|hota|hoti|nahi|nahin|aur|lekin|kya|kyun|kaise|yeh|woh|'
    r'iska|uska|mein|hum|aap|tum|ka|ki|ke|ko|se|par|liye|wala|wale|karte|karo|'
    r'karein|dekho|chalo|matlab|jaise|abhi|bahut|thoda|samajh|seekhenge|dosto|'
    r'namaste|shabash|bilkul|zaroori|sochiye|dhyan)\b',
    re.IGNORECASE,
)


def storyboard_shape_problems(storyboard, persona=None):
    """Structural + policy sanity check on a parsed storyboard — returns problems.

    "It parsed" proves nothing here: json_repair will happily close a TRUNCATED model
    response into valid JSON. These are the shapes a truncation actually leaves behind,
    measured on the 2026-07-20 Dalton's-law runs: a scene whose narration_cues list is
    empty (the cut landed between scenes) and a cue ending mid-pacing-tag
    ("Hey there! [SPEED: SPRINT"). Both rendered as ~3-second videos with no error.

    With a persona given, also enforces the language contract the same run violated
    (8/8 cues English, 7 elements Devanagari — the exact inverse of hybrid):
    - hybrid/en: on-screen element content must not contain Indic script. Unambiguous —
      the codegen sanitizer would only strip it to blank headings downstream.
    - hybrid: narration must actually be Hinglish. Checked post-transliteration, so
      valid cues are Latin-script — plain English is detected by NO cue containing
      Devanagari AND NO cue containing any romanized-Hindi function word. All cues
      must look English for this to fire (any one Hinglish cue ⇒ pass), so legitimate
      code-mix never trips it.
    """
    problems = []
    scenes = storyboard.get("visual_storyboard") or []
    if not scenes:
        return ["storyboard has no scenes"]
    all_cues = []
    for i, scene in enumerate(scenes, 1):
        cues = scene.get("narration_cues") or []
        if not cues:
            problems.append(f"scene {i} has no narration cues")
        for j, cue in enumerate(cues, 1):
            text = (cue.get("cue") or "").strip()
            if not text:
                problems.append(f"scene {i} cue {j} is empty")
            elif text.count("[") != text.count("]"):
                problems.append(f"scene {i} cue {j} ends mid-pacing-tag (truncated)")
            if text:
                all_cues.append(text)
        if persona in ("hybrid", "en"):
            for el in scene.get("elements") or []:
                content = str(el.get("content") or "")
                if el.get("type") in ("text", "math") and _INDIC_ANY.search(content):
                    problems.append(
                        f"scene {i} element '{el.get('id', '?')}' has native-script "
                        f"on-screen content under persona '{persona}' (must be English)"
                    )
    if persona == "hybrid" and all_cues:
        if not any(_INDIC_ANY.search(c) or _ROMAN_HINDI_STOPWORDS.search(c) for c in all_cues):
            problems.append(
                "all narration cues are plain English under persona 'hybrid' "
                "(contract: Hinglish code-mix)"
            )
    return problems


def reference_problems(storyboard):
    """Cross-reference slips inside a scene that the shape check cannot see: two elements with one id, a connector
    that does not name two of the scene's elements, an animation aimed at an id the scene does not have. Each makes
    the transpiler skip or mis-bind something silently. Used to ask the model for ONE corrected board; never to
    reject (an earlier scene's element may legitimately be hidden later), so they also ride along as warnings."""
    problems = []
    for i, scene in enumerate(storyboard.get("visual_storyboard") or [], 1):
        ids = [str(el.get("id")) for el in scene.get("elements") or [] if el.get("id") is not None]
        seen = set()
        for eid in ids:
            if eid in seen:
                problems.append(f"scene {i} uses the element id '{eid}' twice")
            seen.add(eid)
        for el in scene.get("elements") or []:
            conn = el.get("connects")
            if conn and (len(conn) != 2 or any(str(c) not in seen for c in conn)):
                problems.append(f"scene {i} element '{el.get('id', '?')}' connects {conn}: needs exactly two "
                                f"element ids of this scene")
        for cue in scene.get("narration_cues") or []:
            for ev in cue.get("animation_events") or []:
                if ev.get("action") == "hide":
                    continue
                for field in ("target", "to"):
                    ref = ev.get(field)
                    if ref and str(ref) not in seen:
                        problems.append(f"scene {i} animates '{ref}' ({field} of {ev.get('action')}), "
                                        f"which is not an element of that scene")
    return problems


def renumber_scenes(storyboard):
    """Make scene_index 1..n in board order. The transpiler skips the canvas clear for index 1 and names variables
    by index, so a repeated or missing index clashed names and kept the previous scene on screen. Returns how many
    scenes changed."""
    changed = 0
    for i, scene in enumerate(storyboard.get("visual_storyboard") or [], 1):
        if scene.get("scene_index") != i:
            scene["scene_index"] = i
            changed += 1
    return changed


def narrative_problems(storyboard):
    """Measure story continuity across scenes. Returns human-readable problems.

    Reported, never fatal — unlike a truncated board (which is broken), a weak story
    still renders, and rejecting it would burn a full regeneration on a soft metric.
    The point is to MEASURE the thing the user complained about ("no story ... all the
    scenes are disconnected", 2026-08-14) so the prompt change above can be judged by
    evidence instead of vibes, and so the UI can show it.

    Two checks, both taken from the failure that was actually observed:

    * **Cold opens.** In the projectile-motion board every scene began by restating the
      topic ("Projectile Motion ko samajhne ke liye…", "Ab dekhte hain Projectile Motion
      ke equations"), which is what a *section* does. Scene 1 is exempt (it must
      introduce the topic) and so is a `recap` (a summary legitimately restates).
    * **Anchor recurrence.** The ball thrown in scene 1 never came back. If the board
      declares a `narrative.anchor`, it must actually appear in most scenes' narration.
    """
    problems = []
    scenes = storyboard.get("visual_storyboard") or []
    if len(scenes) < 2:
        return problems

    topic = str(storyboard.get("topic") or "").strip().lower()
    topic_words = [w for w in re.split(r"[^a-z0-9]+", topic) if len(w) > 3]

    def _first_cue(scene):
        for cue in scene.get("narration_cues") or []:
            text = re.sub(r"\[[^\]]*\]", " ", str(cue.get("cue") or "")).strip()
            if text:
                return text
        return ""

    cold = []
    for i, scene in enumerate(scenes[1:], start=2):
        if (scene.get("role") or "").lower() == "recap" or i == len(scenes):
            continue
        opening = " ".join(_first_cue(scene).lower().split()[:7])
        if topic_words and all(w in opening for w in topic_words):
            cold.append(i)
    if cold:
        problems.append(
            f"scenes {', '.join(map(str, cold))} open by restating the topic instead of "
            f"continuing from the previous scene (cold open)"
        )

    anchor = str((storyboard.get("narrative") or {}).get("anchor") or "").strip().lower()
    if anchor:
        anchor_words = [w for w in re.split(r"[^a-z0-9]+", anchor)
                        if len(w) > 3 and w not in topic_words]
        if anchor_words:
            present = 0
            for scene in scenes:
                blob = " ".join(str(c.get("cue") or "").lower()
                                for c in (scene.get("narration_cues") or []))
                blob += " " + " ".join(str(e.get("content") or "").lower()
                                       for e in (scene.get("elements") or []))
                if any(w in blob for w in anchor_words):
                    present += 1
            if present * 2 < len(scenes):
                problems.append(
                    f"the running example ({anchor!r}) appears in only {present}/{len(scenes)} "
                    f"scenes — the anchor must carry through the whole video"
                )
    else:
        problems.append("no narrative.anchor — the scenes share a topic but no running example")

    roles = [(s.get("role") or "").lower() for s in scenes]
    if not any(roles):
        problems.append("no scene roles set — the board is a list of sections, not an arc")
    elif "recap" not in roles:
        problems.append("no scene closes the loop (no 'recap' role)")
    return problems


def normalize_onscreen_language(storyboard, persona, translate_fn):
    """Heal Indic-script on-screen labels to English BEFORE the gate rejects them.

    The narration side is already healed (Devanagari cues → romanized Hinglish, above the
    gate call); on-screen `text`/`math` element content had no such pass, so a model that
    wrote Devanagari headings/axis-labels under hybrid/en tripped `storyboard_shape_problems`
    into a hard 500 with no retry (measured 2026-07-21: 14 element violations, all axis
    labels + titles). This is the mirror of the cue pass for elements — same intent, same
    fail-open-to-the-gate safety: a translation is accepted ONLY if it actually removed the
    Indic script, so a bad/failed heal leaves the original for the gate to still reject
    loudly rather than silently shipping broken text. `translate_fn(list[str]) -> list[str]`
    returns concise English for each label, order-preserving; it may raise (the caller
    swallows and lets the gate fire). Mutates `storyboard` in place; returns count healed.
    """
    if persona not in ("hybrid", "en"):
        return 0
    scenes = storyboard.get("visual_storyboard") or []
    contents, positions = [], []
    for s_idx, scene in enumerate(scenes):
        for e_idx, el in enumerate(scene.get("elements") or []):
            if el.get("type") in ("text", "math"):
                content = str(el.get("content") or "")
                if _INDIC_ANY.search(content):
                    contents.append(content)
                    positions.append((s_idx, e_idx))
    if not contents:
        return 0
    translated = translate_fn(contents)
    if len(translated) != len(contents):
        raise ValueError(
            f"label translation length mismatch: expected {len(contents)}, got {len(translated)}"
        )
    healed = 0
    for idx, (s_idx, e_idx) in enumerate(positions):
        new_val = str(translated[idx] or "").strip()
        # Only accept a heal that genuinely removed the Indic script — otherwise keep the
        # original so the gate still catches it (never trade a loud failure for a silent one).
        if new_val and not _INDIC_ANY.search(new_val):
            scenes[s_idx]["elements"][e_idx]["content"] = new_val
            healed += 1
    return healed


# Bumped when a storyboard PROMPT edit is meant to change the output — it partitions
# the cache so already-generated topics are rewritten instead of served stale.
# 2026-08-14-narrative: the narrative-spine rules (through_line + anchor + scene roles
# + no cold opens), after "there is no story ... all the scenes are disconnected".
PROMPT_VERSION = "2026-08-15-drawn-shapes"

# ── Duration contract (2026-08-15, "vid length issue") ────────────────────────
# Nothing anywhere stated a target length: scene count was an env clamp, actual
# length was whatever narration the model wrote × TTS, and ce/'s computed
# spec["duration"] died at the HTTP boundary (it was never in the request payload).
# The words ARE the runtime — TTS bills and paces by audio duration — so the
# contract is a scene count AND a narration word budget, both derived here in ONE
# place (a twin in the deep path would drift on the next tuning pass).
# Measured, not enforced: an off-budget board still renders; [DURATION] makes the
# drift a number so the prompt guidance can be judged by evidence.
WPM_SPOKEN = 150          # storyboard-stage planning rate; ce/ refines by grade
_SCENE_SECONDS = 18.0     # observed ~per-scene runtime behind "4–6 scenes / 60–90 s"

_LEGACY_DURATION_LINE = ("* Target **4–6 scenes** for a 60–90 second video. "
                         "More than 8 scenes wastes render budget without adding clarity.")


def sanitize_target_duration(value):
    """Clamp a requested duration to the range this pipeline can honour, or None.

    Ceiling 600 s: §6 of the roadmap is the path past ~4 minutes (chapterize, don't
    stretch); a larger single-board request would just produce an off-budget board.
    """
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return max(20, min(600, seconds))


def duration_scene_budget(target_s):
    """(min_scenes, max_scenes, narration_word_budget) for a target length."""
    lo = max(3, min(10, round(target_s / (_SCENE_SECONDS * 1.25))))
    hi = max(lo + 1, min(12, round(target_s / (_SCENE_SECONDS * 0.8))))
    words = int(target_s / 60.0 * WPM_SPOKEN)
    return lo, hi, words


def duration_directive(target_s):
    """The prompt's length-guidance line.

    None returns the legacy line BYTE-IDENTICAL, so a request without a target
    produces the exact prompt (and cache behaviour) that existed before this knob —
    the same cache-preservation rule the deep variant and tech_terms follow.
    """
    if not target_s:
        return _LEGACY_DURATION_LINE
    lo, hi, words = duration_scene_budget(target_s)
    return (f"* Target **{lo}–{hi} scenes** for a ~{target_s}-second video, and keep "
            f"TOTAL narration across all cues near **{words} words** (~{WPM_SPOKEN} wpm "
            f"spoken). The narration length IS the video length — a chattier script is a "
            f"longer video, so cut filler rather than compressing the visuals.")


def narration_word_count(storyboard_data):
    """Total spoken words across every cue of every scene."""
    total = 0
    for scene in storyboard_data.get("visual_storyboard") or []:
        for cue in scene.get("narration_cues") or []:
            total += len(str(cue.get("cue") or "").split())
    return total


def enforce_template_variety(storyboard_data, max_run=2):
    """Reset layout_template on the 3rd+ consecutive scene reusing the same one.

    The NLM pipeline's variety rule ("no archetype more than 2 consecutive slides"),
    enforced in code because prompt advice gets satisfied lazily: a board that stamps
    SplitScreen on every scene reads monotonous however good each scene is. Clearing
    (not swapping) hands the scene back to the zone allocator — code never invents a
    layout the model didn't ask for. Returns the number of scenes reset.
    """
    scenes = storyboard_data.get("visual_storyboard") or []
    run_template, run_len, reset = None, 0, 0
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        template = scene.get("layout_template")
        if template and template == run_template:
            run_len += 1
            if run_len > max_run:
                scene["layout_template"] = None
                reset += 1
        else:
            run_template, run_len = template, 1
    return reset


_STORYBOARD_CACHE_TTL = 48 * 3600  # 48 hours in seconds


class StoryboardCache:
    """Content-addressed storyboard cache under ``<workspace>/cache/storyboard/``.

    Freshness rule: with grounding content, the content hash IS the freshness signal
    (an edit changes the path -> regeneration, no TTL). Without it, a topic-level key
    plus the 48 h TTL governs freshness.
    """

    def __init__(self, cache_dir=None, ttl=_STORYBOARD_CACHE_TTL):
        self.cache_dir = cache_dir or str(_paths.cache("storyboard", create=False))
        self.ttl = ttl

    def path(self, topic, persona, language, style, grade, subject, node_type,
             content_hash="", tech_terms="", variant=""):
        """Deterministic cache file path for a storyboard request.

        tech_terms joined the key on 2026-07-22 (narration term policy changes the
        prompt, so it must change the key) — a one-time invalidation of prior entries.

        PROMPT_VERSION joined it on 2026-08-14 for the same reason: a prompt change is
        a CONTENT change, and without it a 48 h cache keeps serving boards written by
        the old prompt — so a quality fix silently doesn't apply to any topic you have
        already generated, which reads as "the fix didn't work". Bumping it is a
        billing change (every cached topic regenerates once), so bump it only for
        prompt edits that are meant to change output.
        """
        key = [topic, persona, language, style, grade, subject, node_type, content_hash,
               tech_terms, PROMPT_VERSION]
        # `variant` names a different GENERATOR for the same request (today: the deep
        # multi-agent path, DEEP_STORYBOARD=1). Appended only when set, so turning the
        # feature off returns to the exact keys — and therefore the exact cached
        # boards — that existed before it.
        if variant:
            key.append(variant)
        key_str = json.dumps(key, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(key_str.encode()).hexdigest()[:16]
        os.makedirs(self.cache_dir, exist_ok=True)
        return os.path.join(self.cache_dir, f"sb_{digest}.json")

    def read(self, path, ttl=None):
        """Return cached storyboard dict if fresh, else None.

        ttl=None -> use self.ttl (48 h). ttl=float('inf') -> skip the age check
        (content-keyed entries are always fresh; a changed hash yields a new path).
        """
        if ttl is None:
            ttl = self.ttl
        try:
            if not os.path.exists(path):
                return None
            if ttl != float('inf') and time.time() - os.path.getmtime(path) > ttl:
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def write(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass


# Module singleton + back-compat function aliases (generate_storyboard_impl and the
# package re-exports call these bare names).
_CACHE = StoryboardCache()
_storyboard_cache_path = _CACHE.path
_storyboard_cache_read = _CACHE.read
_storyboard_cache_write = _CACHE.write


TECH_TERMS_POLICIES = ("english", "bilingual", "native")


def narration_tech_terms_rule(tech_terms, persona, lang_name):
    """Prompt block governing how technical/STEM terms are SPOKEN in narration.

    Policies (request knob ``tech_terms``, default "english"):
      english   — say each technical term in English only; never give its native-
                  language translation ("point, yaani bindu" is the bug this kills).
      bilingual — native equivalent allowed ONCE at first mention, English-only after.
      native    — prefer the standard native-language term throughout.
    Returns "" for persona "en" (all-English narration has no mixing to govern).
    Unknown policy values fall back to "english".
    """
    if persona == "en":
        return ""
    policy = (tech_terms or "english").strip().lower()
    if policy not in TECH_TERMS_POLICIES:
        policy = "english"
    if policy == "english":
        return (
            f"**TECHNICAL TERMS IN NARRATION — ENGLISH ONLY:** Speak every technical/STEM term "
            f"('coordinate plane', 'point', 'hypotenuse', 'refraction', ...) in English, once per mention. "
            f"NEVER translate a technical term into {lang_name}, and NEVER restate it in {lang_name} "
            f"after saying it in English — 'point, yaani bindu' and "
            f"'coordinate plane, arthaat nirdeshank samtal' are FORBIDDEN patterns. "
            f"{lang_name} carries the explanation and connectives; the technical vocabulary stays English. "
            f"This overrides any no-Latin-script rule above: technical terms are the one exception "
            f"and remain in English/Latin script even inside native-script narration."
        )
    if policy == "bilingual":
        return (
            f"**TECHNICAL TERMS IN NARRATION — BILINGUAL FIRST MENTION:** On the FIRST mention of a "
            f"technical/STEM term, say it in English followed once by its {lang_name} equivalent "
            f"(e.g. 'point, yaani bindu'). Every LATER mention uses the English term only — "
            f"never repeat the {lang_name} translation after the first mention."
        )
    return (
        f"**TECHNICAL TERMS IN NARRATION — NATIVE:** Where a standard {lang_name} term exists for a "
        f"technical/STEM concept, use the {lang_name} term in narration. Keep formulas, symbols, "
        f"numbers, and units as-is. Never say the same term in both languages back-to-back."
    )


LANG_NAMES = {
    "en-IN": "English", "hi-IN": "Hindi", "bn-IN": "Bengali",
    "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "mr-IN": "Marathi", "gu-IN": "Gujarati",
    "pa-IN": "Punjabi", "od-IN": "Odia",
}

_HYBRID_EXAMPLES = {
    "Hindi":    "आज हम gravity के बारे में सीखेंगे, जहाँ F = ma होती है।",
    "Telugu":   "ఈ రోజు మనం gravity గురించి నేర్చుకుందాం, ఇక్కడ F = ma అవుతుంది.",
    "Tamil":    "இன்று நாம் gravity பற்றி கற்போம், இங்கு F = ma ஆகும்.",
    "Bengali":  "আজ আমরা gravity সম্পর্কে শিখব, যেখানে F = ma হয়।",
    "Marathi":  "आज आपण gravity बद्दल शिकू, जिथे F = ma असते.",
    "Gujarati": "આજે આપણે gravity વિશે શીખીશું, જ્યાં F = ma થાય છે.",
    "Kannada":  "ಇಂದು ನಾವು gravity ಬಗ್ಗೆ ಕಲಿಯೋಣ, ಇಲ್ಲಿ F = ma ಆಗಿರುತ್ತದೆ.",
}


# One rule, one place — both the single-call prompt and the per-screen writers state it,
# and a twin would drift on the next edit.
SHAPE_CONTENT_RULE = """**NAME THE OBJECT, NOT THE PRIMITIVE.** A `shape` element's
`content` must say WHAT IT IS in the lesson, never merely what it looks like. The
renderer picks the primitive from the description's head noun, so a bare primitive name
produces a bare primitive — a meaningless ring on an empty canvas.
* WRONG: "circle" · "small circle" · "point" · "rectangle" · "arrow pointing right" ·
  "vertical line"
* RIGHT: "the basketball at the top of its arc" · "the ground line the ball lands on" ·
  "velocity arrow pointing right, constant length" · "the table the ball rolls off"
If the object is a real thing (a ball, a lens, a beaker, a leaf, a magnet), prefer
`svg_icon` with the object's name — the renderer DRAWS it in Manim from that name, so
the more specific the name, the better the drawing."""


def language_rules(persona, language, tech_terms="english"):
    """The narration-language + on-screen-language prompt block.

    Extracted from ``generate_storyboard_impl``'s system prompt (2026-08-15) so the
    per-screen scene writers (``pipeline/scene_writers.py``) speak the *same* language
    contract as the single-call path. Two stages both encoding one rule is exactly the
    twin this repo's roadmap warns about — a persona fix applied to one prompt and not
    the other ships a video half in the wrong language, and the gate downstream would
    reject the whole board for it.
    """
    lang_name = LANG_NAMES.get(language, "Hindi")

    rules = "Write all narration_cue 'cue' strings in standard English."
    if persona == "native":
        rules = (
            f"**NARRATION LANGUAGE — CRITICAL:** Every narration_cue 'cue' string you output MUST be written in "
            f"fluent, conversational {lang_name} using its native script "
            f"(e.g. Devanagari for Hindi, Bengali script for Bengali, Tamil script for Tamil, etc.). "
            f"You MUST TRANSLATE the provided English text/beats into {lang_name}. "
            f"Do NOT write any narration cue in English or Latin script. Do NOT copy the English text verbatim."
        )
    elif persona == "hybrid":
        lang_example = _HYBRID_EXAMPLES.get(
            lang_name,
            f"(Use {lang_name} native script for all non-STEM words, keep STEM words like 'gravity' in English)",
        )
        rules = (
            f"**NARRATION LANGUAGE - CRITICAL:** Every narration_cue 'cue' string you output MUST be in "
            f"a conversational {lang_name}-English code-mixed style. "
            f"{lang_name} words and phrases MUST be written in native script; "
            f"only STEM terms, numbers, and widely-used English loan words stay in Latin script. "
            f"Example for {lang_name}: '{lang_example}' "
            f"You MUST TRANSLATE the provided English text/beats into this mixed style. "
            f"Do NOT write narration cues in plain English. Do NOT copy the English text verbatim."
        )

    # How technical terms are SPOKEN (english/bilingual/native) — appended after the
    # persona rules so its "overrides any no-Latin-script rule above" clause lands.
    tech_rule = narration_tech_terms_rule(tech_terms, persona, lang_name)
    if tech_rule:
        rules += "\n" + tech_rule

    # ON-SCREEN text language is a separate, explicit control from narration.
    # SCREEN_TEXT_LANG=en forces English on screen (labels/titles/captions) while
    # narration keeps the persona rules above; default "match" mirrors the
    # narration language in native script. Math/LaTeX always stays as symbols.
    if os.getenv("SCREEN_TEXT_LANG", "match").lower() == "en" or persona == "en":
        rules += "\n" + (
            "**ON-SCREEN TEXT LANGUAGE:** every element 'content' string (text labels, titles, "
            "captions) MUST be in English. The narration language rules above apply ONLY to "
            "narration_cue 'cue' strings, never to on-screen element content."
        )
    else:
        rules += "\n" + (
            f"**ON-SCREEN TEXT LANGUAGE:** text element 'content' strings should be in {lang_name} "
            f"(native script), kept short and readable. Math elements always stay as LaTeX/English symbols."
        )
    return rules


def generate_storyboard_impl(client, topic, persona, language, style, context=None, speaker="shubh", tts_provider="sarvam", gemini_tts_model="google/gemini-3.1-flash-tts-preview", keys=None, tech_terms="english", target_duration_s=None):
    lang_name = LANG_NAMES.get(language, "Hindi")
    target_duration_s = sanitize_target_duration(target_duration_s)

    grade = context.get("grade", "Classes 9-10") if context else "Classes 9-10"
    subject = context.get("subject", topic) if context else topic
    learning_objective = context.get("learning_objective", "") if context else ""
    node_type = context.get("node_type", "") if context else ""

    tech_terms = (tech_terms or "english").strip().lower()
    if tech_terms not in TECH_TERMS_POLICIES:
        logger.warning("Unknown tech_terms policy %r — falling back to 'english'.", tech_terms)
        tech_terms = "english"

    # ── Storyboard cache ───────────────────────────────────────────────────────
    # Key strategy:
    #   • With grounding content (lesson/chapter chunks) → include a sha256 of
    #     the chunks in the key.  The hash is the freshness signal: if the source
    #     material is edited, the hash changes, the cache path changes, and the
    #     storyboard is regenerated automatically.  No TTL needed.
    #   • Without grounding content → fall back to topic-level key with 48 h TTL.
    _grounding_chunks = (context.get("grounding_chunks") or []) if context else []

    # The deep (multi-agent) path resolves its own sources, so its pack digest is the
    # freshness signal — computed BEFORE the cache lookup for exactly that reason.
    # Ingest is free when the caller passed no source refs and auto-search is off.
    from .pipeline import deep_storyboard as _deep      # local: avoids an import cycle
    _deep_on = _deep.enabled()
    _pack = _deep.build_pack(topic, context) if _deep_on else None
    # Variant components are appended only when active, so a request without them
    # keeps its exact prior cache key (and cached board). A duration changes the
    # prompt, so it must partition the cache — same rule as tech_terms/PROMPT_VERSION.
    _variant_parts = []
    if _deep_on:
        _variant_parts.append(f"deep:{_deep.DEEP_VERSION}")
    if target_duration_s:
        _variant_parts.append(f"dur:{target_duration_s}")
    _variant = ";".join(_variant_parts)

    if _pack is not None and _pack.ok:
        _content_hash = _pack.digest
        _cache_ttl = float('inf')
        logger.debug("Storyboard cache: source-keyed (hash=%s)", _content_hash)
    elif _grounding_chunks:
        _content_hash = hashlib.sha256(
            json.dumps(_grounding_chunks, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        _cache_ttl = float('inf')   # content hash is the freshness signal
        logger.debug("Storyboard cache: content-keyed (hash=%s)", _content_hash)
    else:
        _content_hash = ""
        _cache_ttl = _STORYBOARD_CACHE_TTL  # 48 h
        logger.debug("Storyboard cache: topic-keyed (48 h TTL)")

    _sb_cache_path = _storyboard_cache_path(
        topic, persona, language, style, grade, subject, node_type, _content_hash,
        tech_terms=tech_terms, variant=_variant,
    )
    _cached = _storyboard_cache_read(_sb_cache_path, ttl=_cache_ttl)
    if _cached is not None:
        logger.info(
            "Storyboard cache HIT for topic=%r persona=%s lang=%s (content_keyed=%s)",
            topic, persona, language, bool(_content_hash),
        )
        return _cached
    logger.info(
        "Storyboard cache MISS — generating via LLM (content_keyed=%s).",
        bool(_content_hash),
    )
    # ─────────────────────────────────────────────────────────────────────────

    _node_type_map = {
        "hook":         "You are crafting a HOOK. Your primary goal is to raise curiosity — ask provocative questions, present a surprising phenomenon, and leave the concept deliberately unresolved. Do NOT explain the concept yet. End on a question that makes the student lean forward.",
        "recap":        "You are crafting a RECAP. Synthesize and summarize the core key takeaways from the lesson. Use visuals that echo earlier scenes. Reinforce understanding — do not introduce any new ideas.",
        "misconception":"You are crafting a MISCONCEPTION explainer. Visualize the gap between student intuition and the scientifically correct model. Show the wrong belief first, then contrast it dramatically with reality.",
        "concept":      "You are crafting a CONCEPT explanation. Focus on step-by-step visual derivations. Build understanding incrementally, one idea at a time. Never jump ahead.",
        "explanation":  "You are crafting an EXPLANATION. Focus on step-by-step visual derivations. Build understanding incrementally, one idea at a time.",
        "simulation":   "You are crafting a SIMULATION. Prioritize dynamic, process-driven visuals that show a system evolving over time. Use axes, moving objects, and visible state changes.",
        "reveal":       "You are crafting a REVEAL. Build up to a surprising or counterintuitive truth. Pace the reveal dramatically — hold back the conclusion until the visual evidence is undeniable.",
    }
    _nt_key = (node_type or "").strip().lower()
    _nt_instruction = _node_type_map.get(
        _nt_key,
        f"You are creating a '{node_type}' segment. Design visuals and narration to match its pedagogical purpose." if node_type else ""
    )
    node_type_instruction = f"\n**NODE-TYPE DIRECTIVE ({node_type.upper()}):**\n{_nt_instruction}\n" if _nt_instruction else ""

    
    if persona in ["en", "hybrid"] and language in ["hi-IN", "en-IN"]:
        # Extract parenthesized English term if present (e.g. "à¤…à¤µà¤¨à¤®à¤¨ à¤•à¥‹à¤£ (Angle of Depression)" -> "Angle of Depression")
        match = re.search(r'\(([^)]*[a-zA-Z]{2,}[^)]*)\)', topic)
        if match:
            topic = match.group(1).strip()
            
    # The narrative flow, tone, and language persona are now handled by the upstream Pedagogical Planner Agent.
        
    lang_translation_instruction = language_rules(persona, language, tech_terms)


    system_instruction = f"""
**ROLE:**
You are an expert technical director and spatial reasoning engine for Manim educational animations. Your objective is to map educational concepts to visual elements while strictly maintaining a clean, uncluttered, and non-overlapping 2D canvas.

{lang_translation_instruction}
{node_type_instruction}
**CORE DIRECTIVES:**

**1. AVOID TEXT OVERLAP (RELATIVE POSITIONING IS MANDATORY)**
You must never place explanatory text or labels at the exact absolute coordinates of the geometric shapes they describe. 
* Do NOT use `absolute_position` for text labels. 
* For any text describing a specific point, line, or shape, you MUST use the `relative_positioning` object.
* Choose a logical `direction` (UP, DOWN, LEFT, RIGHT, UP_RIGHT, UP_LEFT, DOWN_RIGHT, DOWN_LEFT) that pushes the text into empty space.
* Example: If a point is at `[0,0]` on an axis, placing text at `[-1, -0.5]` will cause overlap. Instead, anchor the text to the point using `direction: "DOWN_RIGHT"` and a `buffer` of 0.5.

**2. SAFE ZONES FOR STANDALONE TEXT**
If a text element is standalone (e.g., scene titles, main questions, overarching theorems) and is NOT anchored to a specific geometric shape:
* You MUST assign it a valid `safe_zone_alignment`.
* NEVER use `"ORIGIN"` for standalone text, as this places it dead-center and blocks the main visual geometry.
* Use outer zones like `"TOP_CENTER"`, `"BOTTOM_CENTER"`, or `"TOP_LEFT"`.

**3. STRICT LIFECYCLE MANAGEMENT (NO CLUTTER)**
The canvas must remain clean. You are responsible for cleaning up old elements when the narration moves on.
* You are limited to a maximum of TWO explanatory text blocks/labels on screen at any given time.
* Within your `narration_cues`, use `animation_events` (preferred) or the legacy `event` string to FadeOut any text or labels that are no longer the current focus.
* Use `{{"action": "hide", "target": "element_id"}}` in `animation_events` to cleanly exit finished elements.
* Do not leave orphaned axes, labels, or questions on the screen after their relevant scene concludes.

**4. SCENE COUNT & CUE DENSITY (RENDERER BUDGET)**
{duration_directive(target_duration_s)}
* Each `narration_cue` must introduce **at most 2 new elements** in its corresponding `elements` list. Introducing 3+ elements in one cue causes frame crowding. Spread reveals across consecutive cues instead.
* Each scene should have **2–4 narration_cues** — one cue per major visual beat. A cue with no new elements is fine (use `event` for exits/transforms).

**4b. FRAME OCCUPANCY (NO DEAD FRAMES)**
The frame is 16:9 and wide. A scene whose visuals occupy a small patch in the middle while narration runs reads as unfinished — this is the single most common defect measured by the automated frame reviewer.
* Every scene MUST have a **substantial central visual** — a diagram, coordinate system, molecule, or labelled construction that fills the stage — not just a title plus one small shape.
* Aim for **3–6 elements per scene**. Two elements is acceptable only for a deliberate title/transition beat.
* Set `scale` generously for the scene's main visual: **1.0–1.5** for the primary diagram or shape (the default 0.7 is sized for supporting text, not for the thing the scene is about).
* When a scene explains a process (a ray refracting, a force acting, a reaction proceeding), draw the **whole process** — the incoming element, the interaction, AND the outcome — not just the static object it happens to. A glass slab with no ray, a spring with no mass, an axis with no curve are all dead frames.
* Use the width: place supporting labels in the LEFT/RIGHT zones rather than stacking everything in the centre column.

{SHAPE_CONTENT_RULE}

**4c. ONE ELEMENT PER DRAWABLE OBJECT — STRUCTURE IS A FIELD, NOT PROSE**
The renderer draws exactly the elements you declare. Anything you mention only inside another element's
`content` text does not exist and will not appear. Describing a whole sub-diagram in one element is the
single biggest cause of empty-looking frames.
* WRONG (one element, four objects, three of them invisible):
  `{{"id": "split", "type": "shape", "content": "Two branches from 84 to circles containing 12 and 7"}}`
  -> renders as ONE line. The 84, the 12, the 7 and the second branch never exist.
* RIGHT (each object declared, relationships in fields):
  `{{"id": "n84", "type": "shape", "content": "circle containing 84"}}`,
  `{{"id": "n12", "type": "shape", "content": "circle containing 12"}}`,
  `{{"id": "n7",  "type": "shape", "content": "circle containing 7"}}`,
  `{{"id": "b1", "type": "shape", "content": "branch", "connects": ["n84", "n12"]}}`,
  `{{"id": "b2", "type": "shape", "content": "branch", "connects": ["n84", "n7"]}}`
* **`connects: [id_a, id_b]`** — use for EVERY link: tree branches, flowchart arrows, chemical bonds,
  force vectors between bodies. The renderer computes the endpoints from the two shapes, so a connector
  needs NO position of its own; give it neither `safe_zone_alignment` nor `absolute_position`.
  Say "arrow" in its `content` if it should carry an arrowhead.
* **`relative_positioning.relation: "inside"`** — use for the CONTENTS of a container: candies in a tray,
  particles in a box, a label inside a node. Declare each item as its own element anchored to the
  container. The renderer distributes siblings across the container and shrinks them to fit, so a
  container is never drawn empty and its contents never spill out.
  A container whose `content` says "containing twelve slots" but which has no `inside` children
  renders as an empty box — declare the children instead.
* A single value that sits in the middle of a shape can stay inline: `"circle containing 84"` draws the
  84 for you. Use `inside` children when there are SEVERAL items, or when the items are icons/images.

**5. LAYOUT TEMPLATES (optional per scene)**
Set `layout_template` on any `StoryboardScene` to activate structured positioning:
* `"TitleStageCaption"` — first element = title at TOP_CENTER, last element = caption at BOTTOM_CENTER, middle elements fill center stage. Use this for most instructional scenes.
* `"SplitScreen"` — elements without explicit positioning alternate LEFT_CENTER / RIGHT_CENTER halves. Use for compare-contrast scenes (before-vs-after, two diagrams, left graph + right equation).
* `"FullCanvas"` — no template; positioning is fully manual via `safe_zone_alignment` / `relative_positioning` / `absolute_position`.
If omitted, the renderer uses each element's own positioning fields as-is.

**6. COMPOSITION DESCRIPTOR (per scene)**
Every scene MUST include a `composition` string that describes the intended visual arrangement in plain terms.
This is NOT a repetition of element positions — it is the **layout gestalt**: how the scene's elements work together spatially.
* Write 1–2 sentences describing the overall composition, e.g.:
  * "Title banner at top centre, large labelled diagram filling the centre two-thirds, derived formula callout at bottom right."
  * "Full-canvas coordinate plane with animated point moving across grid, step-by-step equation derivation stacked in left column."
  * "Split-screen: gas particle animation on the left, pressure–volume graph on the right with a shared annotation strip at bottom."
* The `composition` field is consumed by the deterministic transpiler to guide zone assignment and screen management.
* Do NOT list every element position — capture the spatial gestalt.

**7. EXAMPLES OF GOOD VS. BAD EXECUTION**

**BAD:** Generating a coordinate plane and placing the origin label using absolute coordinates, then forgetting to remove it.
`VisualElement`: {{"type": "text", "absolute_position": [0,0]}} -> *Result: Overlaps with axes.*
`NarrationCue`: {{"animation_events": [{{"action": "show", "target": "y_axis"}}]}} -> *Result: Clutters screen with previous text still on canvas.*

**GOOD:** Anchoring the label relatively, and explicitly fading out old labels as new ones appear.
`VisualElement`: {{"type": "text", "relative_positioning": {{"relative_to": "origin_dot", "direction": "DOWN_RIGHT", "buffer": 0.5}}}} -> *Result: Perfectly spaced.*
`NarrationCue`: {{"animation_events": [{{"action": "show", "target": "y_axis"}}, {{"action": "hide", "target": "x_axis_label"}}]}} -> *Result: Shows new axis and removes stale label in one beat.*

**GOOD (equation evolution):** Morphing one equation into another using structured transform.
`NarrationCue`: {{"animation_events": [{{"action": "transform", "target": "eq_unbalanced", "to": "eq_balanced"}}]}} -> *Result: Parts that match slide into place; new parts fade in — 3Blue1Brown style.*

**GOOD (emphasis):** Flashing a key term to reinforce recall.
`NarrationCue`: {{"animation_events": [{{"action": "highlight", "target": "ph_label", "color": "YELLOW"}}]}} -> *Result: Indicate pulse draws the eye without adding a new element.*

You are also an expert scientific storyboard creator. Your goal is to translate the provided pedagogical plan into a detailed Manim spatial storyboard.
Strictly adhere to the requested JSON response schema.

**PARTS Framework & Educational Pacing (CRITICAL):**
Your scripting and pacing must align to the target grade: {grade}. The subject is {subject}. The learning objective is: {learning_objective}.
1. **Structure (PARTS):** Organize the pedagogical flow as: Hook -> Scaffolded Core Concept -> Misconception Callout -> Active Recall Challenge -> Summary.

**NARRATIVE SPINE — ONE STORY, NOT A LIST OF SECTIONS (CRITICAL):**
The five PARTS above are the *skeleton*; they are NOT five independent mini-lessons.
A viewer must feel one continuous story. Concretely, and non-negotiably:
- Fill `narrative.through_line`: the single question the whole video answers, phrased so a
  student wants the answer. Fill `narrative.anchor`: ONE concrete running example (a
  specific object/person/situation the viewer can picture — "a basketball thrown at a
  hoop", not "projectile motion").
- **The anchor appears in EVERY scene.** Scene 1 introduces it; each later scene RETURNS
  to it with more detail (same ball, now with its velocity split into components; same
  ball, now with the equation predicting where it lands); the last scene finishes its
  story. Abstract scenes must be attached to the anchor, never floated free.
- **Never open a scene by re-declaring the topic.** Openings like "Projectile Motion ko
  samajhne ke liye…" / "Ab dekhte hain Projectile Motion ke equations" make every scene a
  cold start. Open each scene AFTER the first by continuing from what just happened:
  answer the question the previous scene raised, or raise the one this scene resolves
  ("Ball ka path to dekh liya — lekin usse predict kaise karein?").
- **End each scene on an open thread** the next scene picks up, and make the final scene
  answer the hook's question explicitly, naming the anchor.
- Set each scene's `role` (hook / build / turn / payoff / recap). Exactly one `hook` (the
  first scene) and one `recap` (the last); at least one `turn` where the insight lands.
2. **Pacing Tags:** You MUST inject inline expressive tags into the `cue` strings within `narration_cues`:
   - `[SPEED: SPRINT]`: Use for familiar concepts, stories, or basic instructions.
   - `[SPEED: STROLL]`: Use for new vocabulary, core concepts, or complex formulas.
   - `[PAUSE]`: Insert at the end of a sentence after a complex visual reveal or key takeaway to give cognitive breathing room.
   - `[PAUSE: RECALL]`: Insert immediately after asking an Active Recall question.

Visual Richness — SHOW, DON'T TELL (the single most important quality bar):
- Each scene must VISUALLY DEMONSTRATE the concept. A scene that is only a title plus one line of text or one equation is UNACCEPTABLE — that is a slide, not an animation.
- Give every scene 4-7 elements, including at least 2-3 NON-TEXT visual elements (use type 'shape', 'graph', 'coordinate_system', 'svg_icon', or 'chemical_molecule') that concretely illustrate the idea. Text/math elements are for short labels, titles, and key equations only.
- REAL-WORLD OBJECT HANDLING: Never try to manually draw complex items using primitive geometric shapes or make assumptions about local directory file trees.
- DYNAMIC SEARCH IMPLEMENTATION: When real-world imagery is needed (e.g. vehicles, organs, machinery, plants, everyday objects), utilize `type: "svg_icon"` and output a short, single-word English concept term in the `content` field (e.g. "factory", "neuron", "truck", "leaf"). The rendering engine maps this type explicitly to `fetch_smart_svg(keyword, color, height)`.
- REAL PHOTOGRAPHS & HISTORICAL IMAGERY (type: "image"): For History, Geography, Civics, Economics and any narrative about real people, events, places, monuments, maps or artifacts, use `type: "image"` — the engine fetches an actual photograph/painting/map from Wikimedia Commons and displays it with correct aspect ratio.
  â€¢ `content` = a concise English Wikimedia Commons search query of 2-5 words naming the specific subject (e.g. "Storming of the Bastille painting", "Mahatma Gandhi Salt March 1930", "Mohenjo-daro Great Bath", "spinning jenny textile machine").
  â€¢ Set `scale` to the desired on-screen HEIGHT in scene units: 2.5-4.0 for a scene's primary visual, 1.5-2.0 for a supporting portrait. Aspect ratio is preserved automatically.
  â€¢ One primary image per scene; anchor its caption/labels with `relative_positioning` on the image so they travel together. Prefer "image" over "svg_icon" whenever the subject is a real historical person, event, place or object; keep "svg_icon" for abstract icons and diagrams.
- DYNAMIC SIMULATIONS (type: "simulation"): when the idea IS change over time — a projectile tracing its arc, a wave propagating, particles diffusing, a pendulum swinging, a planet orbiting, a mechanism turning — use `type: "simulation"` instead of drawing a still picture of the moving thing. The engine generates and verifies real animation code for it, and the system plays while the narration explains it.
  â€¢ `content` = ONE precise English sentence naming the system, what moves, and which quantities must be visible (e.g. "a ball launched at 45 degrees tracing a parabolic arc above a ground line, with its velocity arrow shrinking near the top").
  â€¢ At most ONE simulation per scene, and only where motion carries the meaning — a static diagram plus a label is better than a simulation of something that does not move.
  â€¢ Do not add separate elements for the parts inside the simulation; it draws its own system. Put labels around it with `relative_positioning`.
- Translate the abstract concept into concrete domain visuals:
  â€¢ Chemistry: If teaching chemistry, DO NOT attempt to draw molecules manually using lines, text, or basic shapes. Set the element type to "chemical_molecule" and provide ONLY a valid SMILES string in the content field (e.g., "O" for water, "CCO" for ethanol, "C1=CC=CC=C1" for benzene). The backend will automatically generate a perfectly accurate, scientifically colored molecular diagram.
  â€¢ Physics: arrows for forces/vectors/velocity, moving objects, fields, free-body diagrams.
  â€¢ Geometry / Algebra: points, lines, triangles, polygons, and curves on a coordinate system; build constructions step by step.
  â€¢ Biology: labeled diagrams of the structures involved.
- For any PROCESS (balancing, deriving, transforming, solving): show it as a visible before -> transformation -> after, using shapes/diagrams that move and change, NOT a stack of successive text lines.
- Prefer transforming or adding to existing visuals over dumping new blocks of text.

Scientific Accuracy (non-negotiable):
- Every fact, equation, count, and claim MUST be correct. Verify atom/quantity counts and that equations are actually balanced or true before finalizing.
- Never state that a correct equation is wrong (or vice versa). If you present a worked example, the math must check out exactly.

Provided Pedagogical Plan:
- You will receive a pedagogical JSON array of scenes. Use the exact voiceover script provided in each scene.
- Do not alter the educational content or pacing. Map the visual actions accurately to the provided spoken cues.

Layout Constraint:
- You must ensure that no coordinate systems place text, labels, or equations on top of one another or on top of active graphs.
- Use explicit relative offsets or clearly separated coordinates (e.g., place labels at least 1.5 units away from other elements, or use positions that don't collide).
- Coordinate systems in Manim default to the origin (0, 0) being the center of the screen, with width 14.22 and height 8.0 (from -7.11 to 7.11 x, and -4.0 to 4.0 y).
- Make sure text labels and math equations are positioned clearly relative to each other and graphs (e.g. shifting UP/DOWN/LEFT/RIGHT).
- Never use the exact same position for two different elements.

Safe Zone & Aspect Ratio Constraints (Scale & Alignment):
- For every VisualElement, you must populate the `scale` and `safe_zone_alignment` fields.
- Set `scale` to 0.7 or 0.8 for text/math elements to ensure they fit within safe margins and do not clip, especially on vertical displays.
- Set `safe_zone_alignment` to align elements away from boundaries using safe alignments (e.g., '.to_edge(UP, buff=0.6)', '.to_edge(DOWN, buff=0.6)', '.to_edge(LEFT, buff=0.6)', '.to_edge(RIGHT, buff=0.6)', or 'ORIGIN') rather than placing them too close to the borders.

Style Profile:
- Follow a style profile of '{style}'. Define matching hex colors (e.g. #00FFCC for cyan neon) or standard Manim colors.
"""
    prompt = f"Convert the following pedagogical storyboard for the topic '{topic}' into a precise Manim spatial storyboard."
    if context and "pedagogical_plan" in context:
        prompt += f"\n\nPedagogical Storyboard:\n{json.dumps(context['pedagogical_plan'], indent=2)}"
    elif context:
        prompt += f"\n\nContext:\n{json.dumps(context, indent=2)}"

    # Inject grounding context so the storyboard LLM draws on the same material
    # as the pedagogical plan (the resolved tier from storyboard_context.resolve_context).
    if context and context.get("grounding_chunks"):
        grounding_source = context.get("grounding_source", "content_store")
        section_header = (
            "## Reference Transcripts (YouTube)"
            if grounding_source == "youtube"
            else "## Course Material"
        )
        prompt += f"\n\n{section_header}\n" + "\n\n---\n\n".join(context["grounding_chunks"])
    
    # ── Deep (multi-agent) path ────────────────────────────────────────────────
    # sources → screen plan → one writer per screen. Produces the same IR the single
    # call below produces, so everything downstream (transliteration, the shape/language
    # gate, the heal, the cache write) is shared. It stands aside on any failure.
    storyboard_data = None
    if _deep_on:
        try:
            storyboard_data = _deep.generate(
                topic, persona=persona, language=language, style=style,
                tech_terms=tech_terms, context=context, client=client, keys=keys,
                pack=_pack, target_duration_s=target_duration_s,
            )
        except Exception as e:
            logger.warning("[DEEP] pipeline raised (%s) — falling back to the single call.", e)
            storyboard_data = None
        if storyboard_data is None:
            logger.info("[DEEP] standing aside; generating with the single-call storyboard.")

    if storyboard_data is None:
        response = call_llm_with_fallback(
            client,
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=StoryboardResponse,
            task="storyboard",
            keys=keys,
        )

        # Parse the JSON response (lenient: tolerate code fences from fallback models)
        storyboard_data = loads_json_lenient(response.text)

        # One corrected attempt. A parse proves nothing (json_repair closes a truncated answer), and the gate below
        # used to be the only check: a board cut off between scenes failed the whole task at once.
        _first = storyboard_shape_problems(storyboard_data) + reference_problems(storyboard_data)
        if _first:
            logger.warning("Storyboard has %d problem(s), asking once for a corrected board: %s",
                           len(_first), "; ".join(_first[:6]))
            try:
                _retry = call_llm_with_fallback(
                    client,
                    prompt=(prompt + "\n\nYour previous answer was rejected for these reasons:\n- "
                            + "\n- ".join(_first[:8])
                            + "\nWrite the COMPLETE storyboard again, every scene finished, fixing exactly these."),
                    system_instruction=system_instruction,
                    response_schema=StoryboardResponse,
                    task="storyboard",
                    keys=keys,
                )
                _second = loads_json_lenient(_retry.text)
                _second_problems = storyboard_shape_problems(_second) + reference_problems(_second)
                if len(_second_problems) < len(_first):
                    storyboard_data = _second
                    logger.info("Corrected storyboard accepted (%d problem(s) left).", len(_second_problems))
            except Exception as ex:
                logger.warning("Storyboard retry failed (%s); keeping the first answer.", ex)

    if renumber_scenes(storyboard_data):
        logger.info("Renumbered scene_index to 1..n in board order.")

    # Pipeline stage: Transliterate spoken cues to Latin Hinglish if hybrid persona is selected
    if persona == "hybrid":
        scenes = storyboard_data.get("visual_storyboard", [])
        cues_to_transliterate = []
        cue_positions = [] # Store tuple of (scene_idx, cue_idx)
        
        for scene_idx, scene in enumerate(scenes):
            for cue_idx, cue_obj in enumerate(scene.get("narration_cues", [])):
                cue_text = cue_obj.get("cue", "").strip()
                # Check if it contains Devanagari Hindi characters
                if re.search(r"[\u0900-\u097f]", cue_text):
                    cues_to_transliterate.append(cue_text)
                    cue_positions.append((scene_idx, cue_idx))
        
        if cues_to_transliterate:
            logger.info(f"Transliterating {len(cues_to_transliterate)} Devanagari cues to Latin script Hinglish...")
            trans_prompt = (
                "You are an expert Hindi-to-Hinglish transliteration assistant.\n"
                "Convert the provided list of Hindi sentences (written in Devanagari script) into Hinglish (Hindi written using standard Latin script / English alphabet letters only).\n"
                "Rules:\n"
                "1. Translate/Transliterate Hindi words to natural spoken Hinglish using English letters (e.g. 'à¤¨à¤®à¤¸à¥à¤¤à¥‡ à¤¦à¥‹à¤¸à¥à¤¤à¥‹à¤‚' -> 'Namaste dosto', 'à¤Šà¤‚à¤šà¥€' -> 'unchi', 'à¤–à¤¡à¤¼à¥‡ à¤¹à¥ˆà¤‚' -> 'khade hain').\n"
                "2. Do NOT use any Hindi/Devanagari characters in the output. The output must contain ONLY standard English alphabet letters, spaces, and basic punctuation.\n"
                "3. Keep any existing English words (e.g. 'Angle of Depression', 'building', 'ground', 'car') EXACTLY as they are.\n"
                "4. Preserve the exact order and length of the input list.\n"
                + (
                    "5. If a sentence says a technical/STEM term in English AND then gives its Hindi "
                    "translation (or vice versa) — e.g. 'point यानी बिंदु' — keep ONLY the English term "
                    "and drop the redundant Hindi translation of it.\n"
                    if tech_terms == "english" else ""
                )
                + f"\nInput Hindi list:\n{json.dumps(cues_to_transliterate, ensure_ascii=False)}"
            )
            trans_sys = "You are a precise indic transliterator that converts Devanagari to Latin script."
            # Small calls use the cheap "general" chain (Haiku on Anthropic), not the storyboard one (Opus).
            
            try:
                trans_response = call_llm_with_fallback(
                    client,
                    prompt=trans_prompt,
                    system_instruction=trans_sys,
                    response_schema=TransliterationResponse,
                    temperature=0.1,
                    task="general",
                    keys=keys,
                )
                trans_data = loads_json_lenient(trans_response.text)
                trans_list = trans_data.get("transliterated_cues", [])
                
                if len(trans_list) == len(cues_to_transliterate):
                    for idx, (s_idx, c_idx) in enumerate(cue_positions):
                        scenes[s_idx]["narration_cues"][c_idx]["cue"] = trans_list[idx]
                    logger.info("Successfully transliterated all Devanagari cues to Latin script Hinglish.")
                else:
                    logger.warning(f"Transliterated list length mismatch: expected {len(cues_to_transliterate)}, got {len(trans_list)}")
            except Exception as ex:
                logger.warning(f"Failed to transliterate cues: {ex}. Keeping original Devanagari cues.")

    # On-screen labels must be English under hybrid/en (the gate below rejects Indic script
    # in text/math elements). The cue pass above heals narration; do the same for on-screen
    # labels so a model that writes Devanagari headings/axis-labels self-heals instead of
    # hard-500ing. Same LLM tier as the cue pass; only fires when there IS Indic content.
    if persona in ("hybrid", "en"):
        def _translate_labels(labels):
            tr_prompt = (
                "You convert on-screen labels for an educational animation into ENGLISH.\n"
                "Each input item is text shown on screen (a title, axis label, or short caption).\n"
                "Rules:\n"
                "1. Output the natural, concise ENGLISH term (e.g. 'समय' -> 'Time', "
                "'दाब' -> 'Pressure', 'कर्ण (Hypotenuse)' -> 'Hypotenuse').\n"
                "2. If an item is already bilingual (native script + English in parentheses), "
                "return ONLY the English part.\n"
                "3. Preserve any LaTeX/math notation and numbers EXACTLY "
                "(e.g. 'a^2 + b^2 = c^2', '90^\\circ').\n"
                "4. Output ONLY standard Latin-alphabet characters — NO Devanagari or other Indic script.\n"
                "5. Preserve the exact order and length of the input list.\n\n"
                f"Input labels:\n{json.dumps(labels, ensure_ascii=False)}"
            )
            tr_response = call_llm_with_fallback(
                client,
                prompt=tr_prompt,
                system_instruction="You translate short Indic-script UI labels into concise "
                                   "English, preserving math notation.",
                response_schema=LabelTranslationResponse,
                temperature=0.1,
                task="general",
                keys=keys,
            )
            return (loads_json_lenient(tr_response.text) or {}).get("translated_labels", [])

        try:
            _n = normalize_onscreen_language(storyboard_data, persona, _translate_labels)
            if _n:
                logger.info(f"Translated {_n} native-script on-screen label(s) to English "
                            f"(persona={persona}).")
        except Exception as ex:
            logger.warning(f"Failed to translate on-screen labels: {ex}. "
                           f"Leaving originals for the gate to reject.")

    # Gate before the cache write: a degenerate storyboard cached for 48 h would poison
    # every later run of this topic (and re-runs would look "fast" while shipping the
    # same 3-second video). Fail loudly naming the stage instead. With persona, this
    # also rejects language-contract inversions (2026-07-20 Dalton run: English cues +
    # Devanagari on-screen text under hybrid) before they get cached.
    _shape_problems = storyboard_shape_problems(storyboard_data, persona=persona)
    if _shape_problems:
        logger.error("Storyboard rejected (%d problem(s)): %s",
                     len(_shape_problems), "; ".join(_shape_problems[:6]))
        raise RuntimeError(
            "Storyboard stage produced an unusable storyboard (truncated response or "
            "language-contract violation). Problems: " + "; ".join(_shape_problems[:6])
        )

    # Story continuity is MEASURED, not enforced: a weak arc still renders, so
    # rejecting it would spend a whole regeneration on a soft metric. The warnings
    # ride along on the board so the UI can show them and so prompt changes can be
    # judged by evidence (see narrative_problems).
    _narrative_problems = narrative_problems(storyboard_data)
    if _narrative_problems:
        logger.warning("[NARRATIVE] %d continuity problem(s): %s",
                       len(_narrative_problems), "; ".join(_narrative_problems[:4]))
    else:
        logger.info("[NARRATIVE] story spine intact across %d scenes.",
                    len(storyboard_data.get("visual_storyboard") or []))
    storyboard_data["narrative_warnings"] = _narrative_problems
    storyboard_data["reference_warnings"] = reference_problems(storyboard_data)

    # Duration is MEASURED, not enforced (same call as narrative_warnings): an
    # off-budget board still renders, but without the number the prompt's word-budget
    # guidance can't be judged. Estimate = words / wpm; the sidecar's
    # rendered_duration_s closes the loop against the real mp4.
    _words = narration_word_count(storyboard_data)
    _est_s = round(_words / WPM_SPOKEN * 60)
    storyboard_data["narration_words"] = _words
    storyboard_data["duration_estimate_s"] = _est_s
    if target_duration_s:
        storyboard_data["target_duration_s"] = target_duration_s
        _drift = (_est_s - target_duration_s) / float(target_duration_s)
        logger.info("[DURATION] target=%ds est=%ds (%d words, %d scenes, drift %+d%%)",
                    target_duration_s, _est_s, _words,
                    len(storyboard_data.get("visual_storyboard") or []), round(_drift * 100))
        if abs(_drift) > 0.20:
            logger.warning("[DURATION] narration is %+d%% off the %ds target — "
                           "off-budget board accepted (measured, not enforced).",
                           round(_drift * 100), target_duration_s)
    else:
        logger.info("[DURATION] no target set; est=%ds (%d words, %d scenes)",
                    _est_s, _words, len(storyboard_data.get("visual_storyboard") or []))

    _variety_reset = enforce_template_variety(storyboard_data)
    if _variety_reset:
        logger.info("[COMPOSITION] variety rule reset layout_template on %d scene(s) "
                    "(same template on 3+ consecutive scenes).", _variety_reset)

    storyboard_data["non_manim_items"] = extract_non_manim_items(storyboard_data)
    storyboard_data["grounding_source"] = (
        context.get("grounding_source", "none") if context else "none"
    )
    _storyboard_cache_write(_sb_cache_path, storyboard_data)
    return storyboard_data
