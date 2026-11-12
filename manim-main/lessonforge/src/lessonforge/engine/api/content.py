"""Routes: /api/generate_student_slides, /api/generate_sim."""
import logging
from fastapi import APIRouter, Depends, HTTPException

from lessonforge.engine.dependencies import APIKeys, resolve_api_keys
from ..llm import (get_genai_client, call_llm_with_fallback, describe_gemini_error,
                   strip_code_fences, loads_json_lenient)
from ..codegen import detect_scene_class, validate_and_repair, ensure_layout, LAYOUT_RULES
from ..assets import determine_background
from ..schemas import StudentSlidesRequest, SimRequest, StudentCourseResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/generate_student_slides")
def generate_student_slides(body: StudentSlidesRequest, keys: APIKeys = Depends(resolve_api_keys)):
    try:
        client = get_genai_client(keys)
        topic = body.topic.strip()
        interest = body.interest.strip()
        style = body.style.strip()
        language = body.language.strip()
        speaker = body.speaker.strip()
        tts_provider = body.tts_provider.strip()
        gemini_tts_model = body.gemini_tts_model.strip()
        background = body.background.strip()

        # If background is default, try to infer one dynamically
        if background == "default":
            background = determine_background(style, interest)

        if background != "default":
            bg_slide_rule = f'      - Canvas Background (Core requirement): You MUST set a realistic background by calling `set_realistic_background(self, "{background}", dim=0.5)` at the very beginning of the `construct(self)` method (right after initializing the speech service). Do NOT write raw background image loading boilerplate.'
            if background in ["white_canvas", "whiteboard.jpg", "notebook_paper.jpg"]:
                bg_slide_rule += " MUST USE CONTRASTING COLOR: The background canvas is white/light, so you MUST NOT use WHITE or light colors for text, math, shapes, or SVGs. Set them to dark contrasting colors like BLACK, dark blue, or red so they are visible."
        else:
            bg_slide_rule = '      - Canvas Background: Do NOT call `set_realistic_background`. Use standard Manim dark background.'

        if not topic or not interest:
            raise HTTPException(status_code=400, detail="Topic and Interest are required")

        system_instruction = f"""
You are an expert STEM educator and slide deck developer. Your goal is to generate educational slide decks personalized for a student based on their topic of study and personal interests.
Adhere strictly to the requested JSON response schema.

Generate exactly 3 sequential slides (indexes 1, 2, 3) illustrating different stages of the concept.
For each slide, you must supply:
1. slide_index (integer)
2. title (string)
3. hook: Direct correlation explaining the STEM concept through the lens of the student's interest (e.g. if interest is Minecraft, use creepers, redstone logic gates, or blocks).
4. explanation: The standard STEM explanation (clear, simple, mathematically sound).
5. hook_simulation: A concept/ruleset for a simple simulation demonstrating the hook.
6. narration_cues: Array of synchronized speech lines and visual events mapping the explanation to the video (Temporal Contiguity).
7. image_prompt: A beautiful DALL-E / Midjourney prompt to render an illustration.
8. manim_video_prompt: Detailed prompt on what animation should be rendered.
9. manim_code: A complete, fully runnable, self-contained Python script defining exactly `class STEMAnimation(VoiceoverScene):` that renders the animation described.
   - It MUST import everything: `from manim import *`, `from manim_voiceover import VoiceoverScene`, `from viz_helpers import *`.
   - It MUST initialize the voiceover service: `self.set_speech_service(UniversalTTSService(language="{language}", speaker="{speaker}", tts_provider="{tts_provider}", gemini_tts_model="{gemini_tts_model}"))`.
   - It MUST follow the Layout Constraint: ensure text labels, mathematical formulas, and graphs do not overlap.
   - It MUST wrap animations in `with self.voiceover(text=...) as tracker` using the narration_cues. To perfectly synchronize visual timing with speech, you MUST pass `run_time=tracker.duration` to the animations. If there are multiple `self.play()` calls in the block, divide `tracker.duration` among them (e.g. `run_time=tracker.duration * 0.5`) so their sum equals exactly `tracker.duration`. Do NOT leave any `self.play()` without an explicit `run_time` inside the block.
   - You MUST be extremely careful to close all parentheses, brackets, and quotes. Example:
     ```python
     with self.voiceover(text="Explanation text") as tracker:
         self.play(Write(some_mobject), run_time=tracker.duration)
     ```
     Double check that every opening parenthesis is matched with a closing parenthesis.
   - Position labels using relative position methods (e.g., `label.next_to(axis, DOWN)`) and separate items clearly.
   - Style the animation based on the '{style}' profile.
     - Use the `Text` class for prose and labels (Unicode sub/superscripts like â‚, â‚‚, Â², Â³ are fine). For equations/formulas PREFER `MathTex` with isolated parts, and animate changes with `TransformMatchingTex` (the exact part-isolation syntax is in the LAYOUT RULES appended below). Do NOT use `MarkupText` XML sub tags — they cause Pango parsing errors. Keep LaTeX inside `MathTex` well-formed and valid.
     - SHOW, DON'T TELL: the animation must visually demonstrate the concept with real mobjects tied to the student's interest — not just a title and a line of text. Add `from viz_helpers import *` after the manim imports and compose the provided helpers (atom(symbol,color), molecule(*atoms), count_row(make_item,n), vector(start,end,color,label), labeled(mobject,text), fetch_smart_svg(keyword,color,height), fetch_molecule_svg(smiles_string,height)) plus raw Manim shapes (Dot, Line, Polygon, Axes). Animate processes by transforming/moving mobjects. The science must be factually correct. If you need icons or custom illustrations (e.g. car, flask, gear, tree), use fetch_smart_svg("keyword") which dynamically downloads the SVG icon from the Iconify API on the fly. If drawing molecules/chemical structures, DO NOT draw them manually; use fetch_molecule_svg(smiles_string, height) to render a scientifically colored molecular diagram directly from a valid SMILES string (e.g. 'O' for water, 'CCO' for ethanol).
     - Safe Zone Bounding Box & Aspect Ratio: In `manim_code`, all text and math elements must be scaled down using `.scale(0.7)` or `.scale(0.8)`. Use a safety margin of at least `buff=0.6` when positioning elements near edges (e.g., using `.to_edge(UP, buff=0.6)`). This ensures code compatibility with both vertical and widescreen displays without screen clipping.
     - Sound Trigger Timing: If playing a sound (e.g., using `self.add_sound("thud.mp3")` or `self.add_sound("whoosh.mp3")`), call the `self.add_sound(...)` method immediately before the corresponding `self.play(...)` statement to keep the audio cues perfectly aligned.
     - Code must be raw, executable Python (no markdown wrapping).
     - {bg_slide_rule}
"""
        system_instruction += "\n\n" + LAYOUT_RULES
        prompt = f"Create a personalized course with 3 slides on the topic '{topic}' contextualized around the student's interest in '{interest}'."
        
        response = call_llm_with_fallback(
            client,
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=StudentCourseResponse,
            keys=keys,
        )
        
        slides_data = loads_json_lenient(response.text)

        # Clean fences, detect the real scene class, and syntax-validate/repair each slide.
        for slide in slides_data.get("slides", []):
            code = strip_code_fences(slide.get("manim_code", ""))
            sc = detect_scene_class(code, "SlideAnimation")
            code, valid, validation_error = validate_and_repair(client, code, sc, keys=keys, persona="hybrid")
            # Generator-Critic: dedicated spatial-layout fixing pass on valid code.
            if valid:
                code = ensure_layout(client, code, sc, keys=keys, persona="hybrid")
            slide["manim_code"] = code
            slide["scene_class"] = sc
            slide["code_valid"] = valid

        return slides_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate student slides")
        msg, status = describe_gemini_error(e)
        raise HTTPException(status_code=status, detail=msg)


@router.post("/api/generate_sim")
def generate_sim(body: SimRequest, keys: APIKeys = Depends(resolve_api_keys)):
    """Generate a self-contained interactive HTML simulation widget for a slide.

    The returned document is rendered client-side inside a sandboxed iframe, so it
    cannot touch the parent page, cookies, or storage. We still pin a strict CSP and
    instruct the model to inline everything / make no network calls.
    """
    try:
        client = get_genai_client(keys)
        topic = body.topic.strip()
        interest = body.interest.strip()
        hook_simulation = body.hook_simulation.strip()

        if not hook_simulation and not topic:
            raise HTTPException(status_code=400, detail="A topic or hook_simulation description is required")

        system_instruction = """
You are an expert front-end engineer who builds small, self-contained, interactive
educational simulation widgets. Output ONE complete HTML document and nothing else.

Hard requirements:
- Return raw HTML only (start with <!DOCTYPE html>). No markdown fences, no commentary.
- Everything inline: a single <style> and a single <script>. NO external resources, NO
  network/fetch/XHR calls, NO CDNs, NO imports. Use only vanilla JS, the DOM, SVG, and Canvas.
- Include this exact CSP meta inside <head>:
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;">
- The widget must be genuinely interactive: at least one slider, button, or drag control that
  visibly updates the visualization in real time, demonstrating the concept.
- Dark theme to match the host app: background #020205, accent cyan #00FFCC, secondary purple
  #8b5cf6, amber #f59e0b, text #e5e7eb. Use a clean sans-serif font.
- Design for a compact embed roughly 100% wide and ~300px tall. Keep margins tight; no scrollbars.
- Keep it lightweight and robust — it must run standalone with no errors when opened directly.
"""
        prompt = (
            f"Build an interactive simulation widget that teaches this concept.\n"
            f"Topic: {topic or 'general STEM'}\n"
            f"Student interest (theme the visuals around this): {interest or 'none'}\n"
            f"Simulation idea to implement: {hook_simulation or topic}"
        )

        response = call_llm_with_fallback(
            client,
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.4,
            task="code",
            keys=keys,
        )

        html = strip_code_fences(response.text)
        # Best-effort: guarantee a CSP even if the model omitted it.
        if "Content-Security-Policy" not in html and "<head>" in html:
            csp = ('<meta http-equiv="Content-Security-Policy" content="default-src '
                   "'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;\">")
            html = html.replace("<head>", "<head>" + csp, 1)

        return {"html": html}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate interactive sim")
        msg, status = describe_gemini_error(e)
        raise HTTPException(status_code=status, detail=msg)
