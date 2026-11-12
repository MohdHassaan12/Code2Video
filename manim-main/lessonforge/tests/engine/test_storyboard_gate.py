"""Storyboard shape + language gate — no manim, no server, no keys.

Pins `storyboard_shape_problems`, the gate that runs before the storyboard
cache write. Two failure families, both measured on real 2026-07-20/21 Dalton
runs:

- Truncation shapes: json_repair closes a cut-off model response into VALID
  JSON, so "it parsed" proves nothing — an empty narration_cues list or a cue
  ending mid-pacing-tag must be rejected before it poisons the cache for 48 h.
- Language inversion: the shipped Dalton video had 8/8 cues in plain English
  and 7 on-screen elements in Devanagari under persona 'hybrid' — the exact
  inverse of the contract (Hinglish narration, English screen). The gate must
  reject both halves, and must NOT fire on legitimate output: romanized
  Hinglish cues (the gate runs post-transliteration, so valid hybrid cues are
  Latin-script), native persona Devanagari, or a single Hinglish cue among
  English ones.

Also pins `narration_tech_terms_rule` (2026-07-22): the tech_terms policy that
stops narration from saying a technical term in English and then re-saying it
in the native language ("point, yaani bindu"). english/bilingual/native must
emit distinguishable rules, persona 'en' gets none, unknown values fall back
to english, and the policy must partition the storyboard cache key.

Run: .venv/bin/python stem_animation_lab/test_storyboard_gate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lessonforge.engine import storyboard_shape_problems  # noqa: E402

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def board(scenes):
    return {"visual_storyboard": scenes}


def scene(cues, elements=None):
    return {
        "narration_cues": [{"cue": c} for c in cues],
        "elements": elements or [],
    }


HINGLISH = "Aaj hum gravity ke baare mein seekhenge, chalo shuru karte hain!"
ENGLISH = "Today we will learn about gravity and how it works."
DEVANAGARI = "आज हम गुरुत्वाकर्षण के बारे में सीखेंगे।"

# ── Truncation shapes (persona-independent) ─────────────────────────────────
check("empty storyboard is rejected",
      storyboard_shape_problems(board([])))
check("scene with no cues is rejected",
      storyboard_shape_problems(board([scene([])])))
check("cue ending mid-pacing-tag is rejected",
      storyboard_shape_problems(board([scene(["Hey there! [SPEED: SPRINT"])])))
check("empty cue is rejected",
      storyboard_shape_problems(board([scene(["  "])])))
check("well-formed storyboard passes with no persona",
      not storyboard_shape_problems(board([scene([ENGLISH])])))

# ── Language gate: on-screen elements ───────────────────────────────────────
dev_el = [{"id": "title", "type": "text", "content": "कुल दबाव का क्या होता है?"}]
en_el = [{"id": "title", "type": "text", "content": "What is total pressure?"}]

check("Devanagari text element under hybrid is rejected",
      storyboard_shape_problems(board([scene([HINGLISH], dev_el)]), persona="hybrid"))
check("Devanagari text element under en is rejected",
      storyboard_shape_problems(board([scene([ENGLISH], dev_el)]), persona="en"))
check("Devanagari element under native is ALLOWED",
      not storyboard_shape_problems(board([scene([DEVANAGARI], dev_el)]), persona="native"))
check("English elements pass under hybrid",
      not storyboard_shape_problems(board([scene([HINGLISH], en_el)]), persona="hybrid"))
shape_el = [{"id": "box", "type": "shape", "content": "डिब्बा"}]
check("non-text/math element content is not language-gated",
      not storyboard_shape_problems(board([scene([HINGLISH], shape_el)]), persona="hybrid"))

# ── Language gate: narration cues (hybrid only) ─────────────────────────────
check("all-English cues under hybrid are rejected (the Dalton inversion)",
      any("plain English" in p for p in
          storyboard_shape_problems(board([scene([ENGLISH]), scene([ENGLISH])]), persona="hybrid")))
check("romanized Hinglish cues pass under hybrid (post-transliteration form)",
      not storyboard_shape_problems(board([scene([HINGLISH])]), persona="hybrid"))
check("Devanagari cues pass under hybrid (pre-transliteration form)",
      not storyboard_shape_problems(board([scene([DEVANAGARI])]), persona="hybrid"))
check("one Hinglish cue among English ones passes (conservative gate)",
      not storyboard_shape_problems(board([scene([ENGLISH, HINGLISH])]), persona="hybrid"))
check("all-English cues under en persona pass (English is the contract there)",
      not storyboard_shape_problems(board([scene([ENGLISH])]), persona="en"))

# The exact shipped-Dalton shape: English cues + Devanagari elements → both named.
problems = storyboard_shape_problems(
    board([scene([ENGLISH], dev_el), scene([ENGLISH])]), persona="hybrid")
check("Dalton inversion reports BOTH the element and the cue violation",
      any("native-script" in p for p in problems) and any("plain English" in p for p in problems))

# ── On-screen label healing (normalize_onscreen_language; LLM stubbed) ───────
# The gate rejects Devanagari on-screen labels; this pass translates them to English
# BEFORE the gate so a non-compliant model self-heals instead of hard-500ing. A heal is
# accepted ONLY if it removed the Indic script — a bad heal must leave the gate to fire.
from lessonforge.engine import normalize_onscreen_language  # noqa: E402


def _stub_translator(labels):
    m = {"समय": "Time", "दाब": "Pressure", "कुल दबाव का क्या होता है?": "What is total pressure?"}
    return [m.get(x, "Translated") for x in labels]


heal_board = board([scene([HINGLISH], [{"id": "title", "type": "text", "content": "समय"}])])
check("board with a Devanagari label is rejected BEFORE healing",
      storyboard_shape_problems(heal_board, persona="hybrid"))
check("healing reports 1 element healed",
      normalize_onscreen_language(heal_board, "hybrid", _stub_translator) == 1)
check("healed content is the English translation",
      heal_board["visual_storyboard"][0]["elements"][0]["content"] == "Time")
check("healed board now PASSES the gate",
      not storyboard_shape_problems(heal_board, persona="hybrid"))

check("native persona is never healed (Devanagari on-screen is legitimate there)",
      normalize_onscreen_language(
          board([scene([DEVANAGARI], [{"id": "t", "type": "text", "content": "समय"}])]),
          "native", _stub_translator) == 0)

# A translation that STILL contains Indic script must be rejected — never trade a loud
# failure for a silent one.
bad_board = board([scene([HINGLISH], [{"id": "t", "type": "text", "content": "दाब"}])])
check("a still-Indic translation heals nothing",
      normalize_onscreen_language(bad_board, "hybrid", lambda labels: ["दाब units"]) == 0)
check("board with a rejected heal still FAILS the gate",
      storyboard_shape_problems(bad_board, persona="hybrid"))

_mismatch_raised = False
try:
    normalize_onscreen_language(
        board([scene([HINGLISH], [{"id": "t", "type": "text", "content": "समय"}])]),
        "hybrid", lambda labels: [])
except ValueError:
    _mismatch_raised = True
check("translator length mismatch raises (caller then fails open to the gate)", _mismatch_raised)

check("shape element with Indic content is NOT sent for translation",
      normalize_onscreen_language(
          board([scene([HINGLISH], [{"id": "box", "type": "shape", "content": "डिब्बा"}])]),
          "hybrid", _stub_translator) == 0)
check("math element with Indic content is healed, notation preserved by translator",
      normalize_onscreen_language(
          board([scene([HINGLISH], [{"id": "m", "type": "math", "content": "दाब = P"}])]),
          "hybrid", lambda labels: ["Pressure = P"]) == 1)

# ── Narration technical-terms policy (narration_tech_terms_rule + cache key) ─
# The knob that kills "point, yaani bindu": tech_terms selects how STEM terms are
# spoken. english = never translated/restated; bilingual = native equivalent once at
# first mention; native = translated. Prompt-only lever, so pin the rule text's
# distinguishing phrases and the cache-key separation (different policy ⇒ different
# storyboard ⇒ different cache entry).
from lessonforge.engine import narration_tech_terms_rule  # noqa: E402
from lessonforge.engine.storyboard import _CACHE  # noqa: E402

_en_rule = narration_tech_terms_rule("english", "hybrid", "Hindi")
check("english policy forbids translating/restating tech terms",
      "NEVER translate" in _en_rule and "yaani bindu" in _en_rule)
check("english policy under native persona carves out Latin script for tech terms",
      "overrides any no-Latin-script rule" in narration_tech_terms_rule("english", "native", "Hindi"))
check("bilingual policy allows the native equivalent ONCE at first mention",
      "FIRST mention" in narration_tech_terms_rule("bilingual", "hybrid", "Hindi"))
check("native policy prefers the native-language term",
      "NATIVE" in narration_tech_terms_rule("native", "hybrid", "Hindi"))
check("persona en gets no rule (nothing to mix)",
      narration_tech_terms_rule("english", "en", "Hindi") == "")
check("unknown policy falls back to english",
      narration_tech_terms_rule("hinglish-max", "hybrid", "Hindi") == _en_rule)

_key_args = ("Gravity", "hybrid", "hi-IN", "style", "9", "Science", "concept", "")
check("cache key separates tech_terms policies",
      _CACHE.path(*_key_args, tech_terms="english") != _CACHE.path(*_key_args, tech_terms="native"))
check("cache key is stable for the same tech_terms policy",
      _CACHE.path(*_key_args, tech_terms="english") == _CACHE.path(*_key_args, tech_terms="english"))

failed = [n for n, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
if failed:
    sys.exit(1)
