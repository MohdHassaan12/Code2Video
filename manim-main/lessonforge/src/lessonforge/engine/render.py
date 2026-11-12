"""Render + repair core (the static-validator + repair-agent stages).

This module is the monkeypatch-cohesive seam: it imports the functions the test harness
patches (repair_code_with_gemini, llm_available, _store_repair_pair) BY NAME, so patching
them on THIS module is what the overlap/repair tests do."""
import os
import re
import sys
import json
import time
import uuid
import shutil
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from lessonforge.engine.dependencies import env_api_keys
from .config import RENDER_DIR, VIDEO_DIR, VIZ_HELPERS_SRC, RENDER_TIMEOUT_SECONDS
from .codegen import (sanitize_generated_code, repair_code_with_gemini, detect_scene_class,
                      validate_python, _strip_mathtex_to_text, ensure_layout)
from .llm import llm_available, get_genai_client
from .rag import _store_repair_pair
from .jobs import _set_job, _write_video_sidecar
from .assets import _collect_asset_elements, probe_asset
from .storyboard import generate_storyboard_impl
from .codegen_pipeline import (generate_asset_blueprint, generate_code_impl,
                               extract_method_from_code)

logger = logging.getLogger(__name__)

def cleanup_render_artifacts(unique_id):
    """Remove the scratch script and media dir for a single completed render."""
    for path in [
        os.path.join(RENDER_DIR, f"scene_{unique_id}.py"),
        os.path.join(RENDER_DIR, f"media_{unique_id}"),
    ]:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Could not clean up {path}: {e}")


def sweep_old_artifacts(max_age_hours=24):
    """Delete scratch scripts/media dirs and served videos older than max_age_hours.

    Keeps the persistent sound assets so they are not regenerated every run.
    """
    cutoff = time.time() - max_age_hours * 3600
    for base in [RENDER_DIR, VIDEO_DIR]:
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if name in ("thud.mp3", "whoosh.mp3", "pop.mp3", "sox", "sox.bat", "viz_helpers.py"):
                continue
            path = os.path.join(base, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
                    logger.info(f"Swept old render artifact: {path}")
            except Exception as e:
                logger.warning(f"Could not sweep {path}: {e}")


_FRAME_ASSERT_SNIPPET = '''
# --- injected layout assertion (bounds report, then auto_fit) ---
try:
    _fw, _fh = config.frame_width / 2, config.frame_height / 2
    _bg = getattr(getattr(self, "camera", None), "background_image", None)
    for _m in list(self.mobjects):
        if _m is _bg:
            continue
        try:
            if (_m.get_right()[0] > _fw + 0.05 or _m.get_left()[0] < -_fw - 0.05 or
                    _m.get_top()[1] > _fh + 0.05 or _m.get_bottom()[1] < -_fh - 0.05):
                print(f"LAYOUT_VIOLATION: {type(_m).__name__} bbox "
                      f"x[{_m.get_left()[0]:.2f},{_m.get_right()[0]:.2f}] "
                      f"y[{_m.get_bottom()[1]:.2f},{_m.get_top()[1]:.2f}] exceeds frame")
        except Exception:
            continue
except Exception as _e:
    print(f"LAYOUT_ASSERT_ERROR: {_e}")
try:
    auto_fit_scene(self)
except Exception as _e:
    print(f"LAYOUT_AUTOFIT_ERROR: {_e}")
'''


# The per-play probe lives in lessonforge/layout_probe.py so the long-form LessonScene
# runtime measures with the SAME code the engine's dry-run injects (one probe, two paths).
from ..layout_probe import PROBE_SNIPPET as _OVERLAP_PROBE_SNIPPET  # noqa: E402


_TTS_STUB_SNIPPET = '''
# --- injected TTS stub (dry-run only): skip audio synthesis ---
try:
    from manim_voiceover import VoiceoverScene as _OvlVOScene
    from contextlib import contextmanager as _ovl_ctx

    class _OvlFakeTracker:
        duration = 0.5
        def get_remaining_duration(self, *a, **k):
            return 0.0

    @_ovl_ctx
    def _ovl_fake_voiceover(self, text=None, **kwargs):
        yield _OvlFakeTracker()

    _OvlVOScene.voiceover = _ovl_fake_voiceover
    _OvlVOScene.set_speech_service = lambda self, *a, **k: None
except Exception:
    pass
'''


def _inject_frame_assertion(code_content):
    """Append the frame-assertion snippet to the end of construct() in the dry-run copy,
    plus the module-level per-play overlap probe (which patches Scene.play at import time,
    so it works regardless of where construct() sits).
    Fails open — if we can't locate construct(), only the probe is added."""
    lines = code_content.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r'^(\s*)def construct\(self\):', ln)
        if not m:
            continue
        body_indent = m.group(1) + "    "
        snippet = "\n".join(
            body_indent + s if s.strip() else s
            for s in _FRAME_ASSERT_SNIPPET.splitlines()
        )
        return (code_content.rstrip() + "\n" + snippet + "\n\n"
                + _OVERLAP_PROBE_SNIPPET + "\n" + _TTS_STUB_SNIPPET + "\n")
    # construct not found — the end-of-construct assertion can't be placed, but the
    # module-level probe still measures per-beat overlap.
    return code_content.rstrip() + "\n\n" + _OVERLAP_PROBE_SNIPPET + "\n" + _TTS_STUB_SNIPPET + "\n"


_LATEX_ERROR_MARKERS = (
    "! LaTeX Error:", "! Undefined control sequence", "! Missing",
    "LaTeX Error:", "dvisvgm: dvi error", "latex compile",
    "latex did not produce", "pdflatex: exit code",
    "xelatex: exit code", "TeX capacity exceeded",
)


# A failing *provider* is not failing *code*. Measured 2026-07-21: an OpenRouter audio
# outage killed a scene, and the runtime self-heal then fed the TTS traceback to the
# code-repair agent, which rewrote a script that was never broken (and re-rendered into
# the same outage). Classify before repairing — "name the failing system, say the fix".
_INFRA_ERROR_MARKERS = (
    "All TTS services failed",
    "audio/speech",
    "OpenRouter TTS failed",
    "No audio content returned",
    "SARVAM_AI_KEY is required",
    "ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError",
    "Temporary failure in name resolution",
    "Max retries exceeded",
    "429 Too Many Requests",
)


def _classify_render_failure(logs):
    """Return the failing SYSTEM for a failed render: 'infra' | 'latex' | 'code'.

    Only 'code' may reach the LLM repair agent — the other classes are things no
    code rewrite can fix (a provider outage, a missing binary), and handing them to
    a rewriter burns a metered call and risks damaging a correct script.
    """
    text = logs or ""
    if any(marker in text for marker in _INFRA_ERROR_MARKERS):
        return "infra"
    if any(marker in text for marker in _LATEX_ERROR_MARKERS):
        return "latex"
    return "code"


def compile_manim_code(code_content, scene_class, quality="l", aspect_ratio="widescreen", persona="hybrid"):
    code_content = sanitize_generated_code(code_content, persona)
    # Self-healing: If LaTeX is not installed on PATH, compile_tex/MathTex will crash.
    # We dynamically replace MathTex and Tex references with standard Text.
    has_latex = bool(shutil.which("latex") or shutil.which("pdflatex") or shutil.which("xelatex"))
    if not has_latex:
        logger.warning("LaTeX not found on PATH. Performing self-healing: replacing Tex/MathTex with Text.")
        code_content = _strip_mathtex_to_text(code_content)

        # Prepend runtime monkey-patch to handle internal Manim components like Axes/NumberLine
        monkey_patch = """
import sys
import manim

# Force import all submodules to ensure they are in sys.modules
try:
    import manim.mobject.text.tex_mobject
    import manim.mobject.graphing.number_line
    import manim.mobject.graphing.coordinate_systems
    import manim.mobject.text.numbers
except ImportError:
    pass

manim.MathTex = manim.Text
manim.Tex = manim.Text

for mod_name, mod in list(sys.modules.items()):
    if mod_name.startswith("manim"):
        if hasattr(mod, "MathTex"):
            mod.MathTex = mod.Text
        if hasattr(mod, "Tex"):
            mod.Tex = mod.Text
"""
        code_content = monkey_patch + "\n" + code_content

    unique_id = str(uuid.uuid4())[:8]
    script_filename = f"scene_{unique_id}.py"
    script_path = os.path.join(RENDER_DIR, script_filename)

    # Save script to temp_renders folder
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code_content)

    # Make the drawing-helper module importable by the rendered scene (`from viz_helpers import *`).
    # Copy it next to the script so the script's own folder (which manim adds to sys.path) resolves it.
    try:
        if os.path.exists(VIZ_HELPERS_SRC):
            shutil.copy(VIZ_HELPERS_SRC, os.path.join(RENDER_DIR, "viz_helpers.py"))
    except Exception as e:
        logger.warning(f"Could not stage viz_helpers.py for render: {e}")

    # Trust the class actually defined in the code over the caller's hint, so a
    # mismatch (e.g. STEMAnimation vs SlideAnimation) doesn't cause a render miss.
    detected = detect_scene_class(code_content, scene_class)
    if detected != scene_class:
        logger.info(f"Overriding requested scene class '{scene_class}' with detected '{detected}'.")
        scene_class = detected

    media_dir = os.path.join(RENDER_DIR, f"media_{unique_id}")

    # Build manim execution command. Invoke via the *current* interpreter (python -m manim)
    # so it always resolves to the venv's Manim, even when .venv/bin isn't on PATH (run.sh
    # runs python directly, which does not activate the venv).
    # -ql: 480p 15fps, -qm: 720p 30fps, -qh: 1080p 60fps
    # Default quality upgraded to qm (720p) — 480p makes Indic script labels unreadable.
    # Manim cache re-enabled: unchanged scenes reuse cached frames on repair rounds.
    import sys
    _effective_quality = quality if quality else "m"
    cmd = [sys.executable, "-m", "manim", f"-q{_effective_quality}", script_path, scene_class,
           "--media_dir", media_dir]
    if aspect_ratio == "vertical":
        cmd.extend(["-r", "1080,1920", "--format=mp4"])
    logger.info(f"Running manim compile command: {' '.join(cmd)}")

    # Ensure viz_helpers resolves regardless of how manim sets sys.path: add the render
    # dir to PYTHONPATH for the subprocess. The subprocess also RUNS there, so relative
    # asset names in generated code (`self.add_sound("pop.mp3")`) resolve against the
    # workspace instead of whatever directory the server was launched from.
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(RENDER_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    # ── Dry-run pre-flight (measurement layer) ───────────────────────────────
    # Measures LAYOUT_VIOLATION lines (overlap / clipped / text-over-shape) that feed
    # _repair_overlaps. The former "5–30s overhead" was mostly real TTS synthesis —
    # the injected copy now stubs out voiceover audio, so pre-flight is fast and free.
    # DRY_RUN_ENABLED=0 disables it (also disables measured overlap repair).
    _spatial_prefix = ""
    if os.getenv("DRY_RUN_ENABLED", "1") != "0":
        _dry_script_path = os.path.join(RENDER_DIR, f"scene_{unique_id}_dry.py")
        try:
            with open(_dry_script_path, "w", encoding="utf-8") as _f:
                _f.write(_inject_frame_assertion(code_content))
        except Exception as _dry_write_exc:
            logger.warning(f"Could not write dry-run script: {_dry_write_exc}. Using original.")
            _dry_script_path = script_path
        _dry_media = media_dir + "_dry"
        _dry_cmd = [sys.executable, "-m", "manim", "--dry_run", "-ql",
                    _dry_script_path, scene_class, "--media_dir", _dry_media]
        if aspect_ratio == "vertical":
            _dry_cmd.extend(["-r", "480,854", "--format=mp4"])
        logger.info("Running Manim dry-run pre-flight (with frame-assertion)...")
        _dry_logs = ""
        _dry_ok = True
        try:
            _dry_proc = subprocess.Popen(_dry_cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, env=env,
                                         cwd=RENDER_DIR)
            try:
                _dry_out, _ = _dry_proc.communicate(timeout=300)
                _dry_logs = _dry_out or ""
                _dry_ok = (_dry_proc.returncode == 0)
            except subprocess.TimeoutExpired:
                _dry_proc.kill()
                _dry_out, _ = _dry_proc.communicate()
                _dry_logs = (_dry_out or "") + "\n[DRY_RUN] Exceeded 300s timeout and was killed."
                _dry_ok = False
        except Exception as _dry_exc:
            _dry_logs = f"[DRY_RUN] Pre-flight process error: {_dry_exc}"
            _dry_ok = False
        finally:
            shutil.rmtree(_dry_media, ignore_errors=True)
            if _dry_script_path != script_path:
                try:
                    os.remove(_dry_script_path)
                except Exception:
                    pass
        if not _dry_ok and re.search(
                r"unrecognized argument|no such option|invalid choice.*dry", _dry_logs, re.IGNORECASE):
            logger.warning("--dry_run not supported by this Manim version; skipping.")
            _dry_ok = True; _dry_logs = ""
        _spatial_warnings = [ln for ln in _dry_logs.splitlines() if "LAYOUT_VIOLATION:" in ln]
        if _spatial_warnings and os.getenv("LAYOUT_STRICT", "0") == "1":
            _dry_ok = False
            _dry_logs += "\n[LAYOUT_STRICT] Frame violations treated as failure."
            logger.warning(f"LAYOUT_STRICT: {len(_spatial_warnings)} violation(s) promoted to failure.")
        if not _dry_ok:
            shutil.rmtree(media_dir, ignore_errors=True)
            _abort_log = "[DRY_RUN FAILED — full render aborted]\n" + _dry_logs
            if _spatial_warnings:
                _abort_log += "\n[SPATIAL_WARNINGS]\n" + "\n".join(_spatial_warnings)
            return False, None, _abort_log
        if _spatial_warnings:
            _spatial_prefix = "[DRY_RUN SPATIAL_WARNINGS]\n" + "\n".join(_spatial_warnings) + "\n\n"
            logger.warning(f"Dry-run flagged {len(_spatial_warnings)} spatial violation(s).")

    # Run the subprocess with a hard timeout so a hung render can't block forever.
    logs = []
    success = False
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
                                   cwd=RENDER_DIR)
        try:
            stdout, _ = process.communicate(timeout=RENDER_TIMEOUT_SECONDS)
            logs.append(stdout or "")
            print(f"[Manim Compiler]:\n{stdout}")
            success = (process.returncode == 0)
            if not success:
                logger.error(f"Manim compilation failed with exit code: {process.returncode}")
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate()
            logs.append(stdout or "")
            logs.append(f"\nError: Render exceeded the {RENDER_TIMEOUT_SECONDS}s time limit and was terminated.")
            logger.error("Manim render timed out and was killed.")
    except FileNotFoundError:
        logs.append("\nError: the 'manim' executable was not found. Install dependencies with `pip install -r requirements.txt`.")
        logger.error("manim executable not found on PATH.")

    video_url = None
    if success:
        # Scan media_dir to find the output mp4 file
        mp4_files = []
        for root, dirs, files in os.walk(media_dir):
            for file in files:
                if file.endswith(".mp4"):
                    mp4_files.append(os.path.join(root, file))

        if mp4_files:
            dest_filename = f"{scene_class}_{unique_id}.mp4"
            dest_path = os.path.join(VIDEO_DIR, dest_filename)
            shutil.copy(mp4_files[0], dest_path)
            video_url = f"/static/videos/{dest_filename}"
            logger.info(f"Successfully compiled. Served video at: {video_url}")
            # Success: drop the scratch script and the (large) media dir.
            cleanup_render_artifacts(unique_id)
        else:
            success = False
            logs.append("\nError: Compilation finished but no MP4 file was found in media output directories.")
            logger.error("No MP4 file found in media directory.")

    if not success:
        # On failure keep the script for debugging but drop the media dir.
        shutil.rmtree(media_dir, ignore_errors=True)

    return success, video_url, _spatial_prefix + "".join(logs)


def _overlap_violations(logs):
    """Extract the per-beat measured violations (text overlap / clipped text /
    text struck through by a diagram) from compile logs."""
    return [ln for ln in (logs or "").splitlines()
            if "LAYOUT_VIOLATION: overlap" in ln
            or "LAYOUT_VIOLATION: off-frame" in ln
            or "LAYOUT_VIOLATION: text-over-shape" in ln]


def _shape_overlap_lines(logs):
    """Shape-on-shape collisions measured by the probe.

    Kept OUT of _overlap_violations on purpose (note that the substring
    "LAYOUT_VIOLATION: overlap" does not match "…: shape-overlap", so the counted
    set is unaffected): this class is new, so it is reported into the sidecar and
    graded on real runs before it is ever allowed to trigger a repair round."""
    return [ln.strip() for ln in (logs or "").splitlines()
            if "LAYOUT_VIOLATION: shape-overlap" in ln]


def _tts_degraded_lines(logs):
    """Voice-degradation markers printed by viz_helpers in the manim subprocess
    (`TTS_DEGRADED: <tier> <detail>`). A video that shipped on a fallback voice must
    never look clean in the sidecar."""
    return [ln.strip() for ln in (logs or "").splitlines() if "TTS_DEGRADED:" in ln]


def _tts_was_muted(logs):
    """True when this render deliberately synthesized no speech (`TTS_MUTE=1`).

    Recorded separately from `voice_degraded` because the two mean opposite things:
    degradation is a provider problem to investigate, muting is a choice made to
    save money while iterating on visuals. Both must be visible — a silent video
    that looks clean in the sidecar is the failure mode TTS_SILENT_FALLBACK was
    kept default-off to avoid."""
    return any("TTS_DEGRADED: muted" in ln for ln in _tts_degraded_lines(logs))


def _video_path(video_url):
    """Absolute path of a /static/videos/<name>.mp4 URL."""
    return os.path.join(VIDEO_DIR, os.path.basename(video_url)) if video_url else None


def _discard_video(video_url, keep=()):
    """Delete a render that lost (a rejected repair candidate, a superseded original,
    or a scene clip already folded into the concat).

    Every compile_manim_code success copies its mp4 into VIDEO_DIR, so without this the
    losers pile up there as sidecar-less "Raw" rows on /timeline. Never touches a URL in
    `keep` — the currently accepted artifact — and an already-missing file is fine.
    """
    if not video_url or video_url in keep:
        return
    path = _video_path(video_url)
    try:
        os.remove(path)
        logger.info(f"Discarded superseded render {os.path.basename(path)}")
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning(f"Could not remove superseded render {path}: {e}")
    try:
        os.remove(path + ".json")  # sidecar, if one was ever written
    except OSError:
        pass


def _repair_preserves_assets(prev_code, candidate):
    """A repair candidate must keep every pre-resolved real image and simulation.

    The overlap probe deliberately ignores ImageMobjects, so an LLM rewrite that
    swaps a fetch_real_image(<local path>) for an icon or drops it entirely can
    never worsen the violation count — measured live 2026-07-31 (t02 Mohenjo-daro:
    all photos silently became fetch_smart_svg icons across 4 accepted repair
    rounds). Deterministic guard, same spirit as never-lose-a-verified-artifact.

    Generated simulations and drawings are guarded by the same rule for the same
    structural reason, generalized: **every asset the verifier cannot see needs its own
    deterministic preservation guard.** A `simulation(...)` group costs an LLM call plus
    a verification run to produce, and deleting its `sim_play(...)` line removes all the
    motion while leaving a perfectly still, perfectly legal frame — the cheapest
    possible way for a repair round to "improve" the video.

    Measured 2026-08-15, one round after `simulation(`/`sim_play(` were added here and
    `drawing(` was not: a repair pass silently swapped four `drawing(<path>)` calls for
    `fetch_smart_svg`/native fallbacks in ONE scene of a shipped video (siblings kept
    14/14, that scene rendered 10). The frame went from a drawn player, hoop and ball to
    a labelled grey box — and the violation count went DOWN, so it was accepted. Adding
    the call here is not a special case; it is the rule applied to the newest asset.
    """
    for call in ("fetch_real_image(", "simulation(", "sim_play(", "drawing("):
        if candidate.count(call) < prev_code.count(call):
            return False
    return True


def _overlap_error_report(violations):
    """The repair-agent brief for measured layout violations. Shared by the whole-video
    (_repair_overlaps) and scene-scoped (_repair_scenes_parallel) repair paths."""
    return (
        "The scene renders successfully, but the listed text objects OVERLAP each other, "
        "are CLIPPED by the frame edge, or are STRUCK THROUGH by a diagram (an axis line, "
        "circle, or arrow crossing the text) on screen (each measured immediately after the "
        "given play() beat — 'play#7' means the 7th self.play call). Fix ONLY these issues:\n"
        "- Stale text from a previous beat still on screen: FadeOut it, or call "
        "clear_canvas(self) between beats.\n"
        "- Related text placed with absolute coords: put it in VGroup(...).arrange(DOWN/RIGHT, "
        "buff=0.4) instead.\n"
        "- Title/body collisions: keep titles at [0, TITLE_Y, 0] and body at [0, BODY_Y, 0].\n"
        "- Clipped/off-frame text: keep text centered (x=0) or shrink it — the safe region "
        "is x in [-6.4, 6.4], y in [-3.4, 3.4].\n"
        "- Text crossed by a diagram (text-over-shape): move the text into empty space — "
        "next_to the diagram with buff>=0.4, to a corner, or to the caption band — or shift "
        "the axes/diagram to one side and keep text on the other.\n"
        "Do NOT change the narration, voiceover blocks, or educational flow.\n"
        "Do NOT remove, replace, or substitute any fetch_real_image(...) call — these are "
        "pre-resolved licensed photographs the video must keep; reposition them if needed "
        "(.to_edge/.move_to) but never swap them for icons, shapes, or text.\n\n"
        + "\n".join(violations)
    )


def _repair_overlaps(client, keys, code, scene_class, quality, aspect_ratio, persona,
                     video_url, logs, progress=None):
    """Post-pass for renders that SUCCEEDED but where the dry-run measured text overlap.

    Asks the repair agent to fix only the measured overlaps and re-renders. The original
    video is kept as fallback — a repaired version is accepted only if it renders AND
    reduces the overlap count, so this pass can never lose a video, only improve it.
    Each round's loser is deleted so rejected candidates don't leak into VIDEO_DIR.

    Returns (code, video_url, logs, rounds_used).
    """
    violations = _overlap_violations(logs)
    if not violations or os.getenv("OVERLAP_REPAIR", "1") != "1":
        return code, video_url, logs, 0
    if not llm_available(client, keys):
        logger.warning(f"{len(violations)} overlap violation(s) measured but no LLM available to repair.")
        return code, video_url, logs, 0

    max_rounds = int(os.getenv("OVERLAP_REPAIR_ROUNDS", "2"))
    rounds = 0
    while violations and rounds < max_rounds:
        rounds += 1
        logger.warning(f"Render OK but {len(violations)} text-overlap violation(s) measured; "
                       f"overlap-repair round {rounds}/{max_rounds}...")
        if progress:
            progress(f"Fixing {len(violations)} text overlap(s), round {rounds}...")
        error_report = _overlap_error_report(violations)
        try:
            _prev_code = code
            repaired = repair_code_with_gemini(client, code, error_report, scene_class, keys=keys)
            repaired = sanitize_generated_code(repaired, persona)
        except Exception as e:
            logger.warning(f"Overlap repair round {rounds} crashed: {e}")
            break
        if not repaired or repaired == code:
            break
        if not _repair_preserves_assets(_prev_code, repaired):
            logger.warning("Overlap repair dropped a fetch_real_image asset; rejecting candidate.")
            break
        ok, new_url, new_logs = compile_manim_code(repaired, scene_class, quality, aspect_ratio, persona)
        if not ok:
            logger.warning("Overlap-repaired code failed to render; keeping previous video.")
            _discard_video(new_url, keep=(video_url,))
            break
        new_violations = _overlap_violations(new_logs)
        if len(new_violations) < len(violations):
            _store_repair_pair("\n".join(violations), _prev_code, repaired, scene_class)
            superseded = video_url
            code, video_url, logs, violations = repaired, new_url, new_logs, new_violations
            _discard_video(superseded, keep=(video_url,))
        else:
            logger.warning("Overlap repair did not reduce violations; keeping previous video.")
            _discard_video(new_url, keep=(video_url,))
            break

    if violations:
        logger.warning(f"{len(violations)} text-overlap violation(s) remain after {rounds} repair round(s).")
    elif rounds:
        logger.info(f"All text overlaps resolved after {rounds} repair round(s).")
    return code, video_url, logs, rounds


def _vision_error_report(findings):
    """Repair-agent brief for Vision-QA findings (same shape as _overlap_error_report,
    so repair_code_with_gemini consumes either brief unchanged)."""
    return (
        "The scene renders successfully, but a frame-level visual review flagged the "
        "issues below (each line: vision-<class> t=<seconds into the video>). Fix ONLY "
        "these issues:\n"
        "- clipped-text: keep text inside x in [-6.4, 6.4], y in [-3.4, 3.4]; shrink or recenter.\n"
        "- colliding-text / crowding: FadeOut stale objects, or arrange related text in "
        "VGroup(...).arrange(DOWN, buff=0.4); call clear_canvas(self) between beats.\n"
        "- unreadable-text: scale the text UP (or shorten it) — do not drop content.\n"
        "- dead-frame: bring the scene's main visual on earlier or enlarge it to fill the stage.\n"
        "- low-contrast: switch the element to a high-contrast color (WHITE/YELLOW on dark).\n"
        "- broken-hierarchy: make the single most important element visibly larger/brighter "
        "than its supporting elements.\n"
        "Do NOT change the narration, voiceover blocks, or educational flow.\n\n"
        + "\n".join(findings)
    )


def _run_vision_qa(code, video_url, logs, scene_class, quality, aspect_ratio, persona,
                   allow_repair, progress=None):
    """Vision-QA measurement + (optionally) accept-if-better repair rounds.

    Returns (code, video_url, logs, findings, rounds_used). Non-fatal by contract
    (a stage improves or stands aside): any internal failure returns the inputs
    unchanged with no findings, and the incumbent video is never lost.

    Acceptance for a vision-repair candidate is stricter than the overlap loop's,
    because vision findings and geometric violations are separate measurements:
    the candidate must (a) render, (b) NOT increase geometric violations vs. the
    incumbent's logs, and (c) strictly reduce vision findings on a fresh critique
    (a metered re-measurement — VISION_QA_REPAIR_ROUNDS therefore defaults to 1).
    """
    try:
        from .pipeline.vision_qa import VisionQAStage
        stage = VisionQAStage()
        if not stage.enabled() or not video_url:
            return code, video_url, logs, [], 0
        findings = stage.critique(_video_path(video_url))
        if not findings or not allow_repair or os.getenv("VISION_QA_REPAIR", "1") != "1":
            return code, video_url, logs, findings, 0
        keys = env_api_keys()
        client = get_genai_client(keys)
        if not llm_available(client, keys):
            logger.warning("%d vision finding(s) measured but no LLM available to repair.",
                           len(findings))
            return code, video_url, logs, findings, 0
        baseline_geo = len(_overlap_violations(logs))
        max_rounds = int(os.getenv("VISION_QA_REPAIR_ROUNDS", "1"))
        rounds = 0
        while findings and rounds < max_rounds:
            rounds += 1
            logger.warning("Vision QA: %d finding(s); vision-repair round %d/%d...",
                           len(findings), rounds, max_rounds)
            if progress:
                progress(f"Fixing {len(findings)} visual issue(s), vision round {rounds}...")
            try:
                _prev_code = code
                repaired = repair_code_with_gemini(client, code, _vision_error_report(findings),
                                                  scene_class, keys=keys)
                repaired = sanitize_generated_code(repaired, persona)
            except Exception as e:
                logger.warning("Vision repair round %d crashed: %s", rounds, e)
                break
            if not repaired or repaired == code:
                break
            if not _repair_preserves_assets(_prev_code, repaired):
                logger.warning("Vision repair dropped a fetch_real_image asset; rejecting candidate.")
                break
            ok, new_url, new_logs = compile_manim_code(repaired, scene_class, quality,
                                                       aspect_ratio, persona)
            if not ok:
                logger.warning("Vision-repaired code failed to render; keeping previous video.")
                _discard_video(new_url, keep=(video_url,))
                break
            if len(_overlap_violations(new_logs)) > baseline_geo:
                # Never trade a geometric regression for a vision improvement.
                logger.warning("Vision repair added geometric violations; keeping previous video.")
                _discard_video(new_url, keep=(video_url,))
                break
            new_findings = stage.critique(_video_path(new_url))
            if len(new_findings) < len(findings):
                _store_repair_pair("\n".join(findings), _prev_code, repaired, scene_class)
                superseded = video_url
                code, video_url, logs, findings = repaired, new_url, new_logs, new_findings
                _discard_video(superseded, keep=(video_url,))
            else:
                logger.warning("Vision repair did not reduce findings; keeping previous video.")
                _discard_video(new_url, keep=(video_url,))
                break
        if findings:
            logger.warning("%d vision finding(s) remain after %d vision round(s).",
                           len(findings), rounds)
        elif rounds:
            logger.info("All vision findings resolved after %d vision round(s).", rounds)
        return code, video_url, logs, findings, rounds
    except Exception as e:
        logger.warning("Vision QA pass stood aside (%s).", e)
        return code, video_url, logs, [], 0


def _render_scenes_parallel(scene_scripts, scene_class, quality, aspect_ratio, persona):
    """
    Render N per-scene scripts simultaneously.

    Returns (success, clip_urls, per_scene_logs) — one entry per scene, index-aligned
    with scene_scripts. Clips are deliberately left in VIDEO_DIR: the caller concats
    them, and when the probe measured violations it first repairs the offending scenes
    in place (see _repair_scenes_parallel) so only those scenes are re-rendered.
    On any scene failure the caller should fall back to the sequential single-script path.
    """
    n = len(scene_scripts)
    max_par = min(n, int(os.getenv("PARALLEL_RENDER_WORKERS", "4")))
    results = [None] * n

    def _render_one(idx):
        return idx, compile_manim_code(scene_scripts[idx], scene_class, quality, aspect_ratio, persona)

    with ThreadPoolExecutor(max_workers=max_par) as _ex:
        futs = {_ex.submit(_render_one, i): i for i in range(n)}
        for fut in as_completed(futs):
            try:
                idx, triple = fut.result()
                results[idx] = triple
            except Exception as _e:
                results[futs[fut]] = (False, None, str(_e))

    clip_urls = [(r[1] if r else None) for r in results]
    per_scene_logs = [(r[2] if r else "") for r in results]

    if not all(r and r[0] for r in results):
        logger.warning("Parallel render: %d/%d scene(s) failed.",
                       sum(1 for r in results if not (r and r[0])), n)
        # The scenes that DID render are dead weight once we fall back to the
        # sequential path — drop them instead of leaking them into /timeline.
        for _u in clip_urls:
            _discard_video(_u)
        return False, clip_urls, per_scene_logs

    return True, clip_urls, per_scene_logs


def _concat_scene_clips(clip_urls):
    """ffmpeg-concat per-scene clips (stream copy) into one mp4.
    Returns (video_url, error) — video_url is None on failure."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None, "[PARALLEL] ffmpeg not found on PATH."

    abs_video_dir = os.path.abspath(VIDEO_DIR)
    video_files = [os.path.join(abs_video_dir, os.path.basename(u)) for u in clip_urls]

    concat_id = str(uuid.uuid4())[:8]
    list_path = os.path.join(RENDER_DIR, f"concat_list_{concat_id}.txt")
    try:
        with open(list_path, "w", encoding="utf-8") as _lf:
            for vf in video_files:
                _lf.write(f"file '{vf}'\n")
    except Exception as _le:
        return None, f"[PARALLEL] Could not write concat list: {_le}"

    concat_name = f"STEMAnimation_concat_{concat_id}.mp4"
    concat_path = os.path.join(abs_video_dir, concat_name)
    try:
        _proc = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", concat_path],
            capture_output=True, text=True, timeout=180,
        )
        if _proc.returncode != 0:
            return None, f"[PARALLEL ffmpeg FAILED]\n{_proc.stderr}"
    except Exception as _fe:
        return None, f"[PARALLEL ffmpeg ERROR] {_fe}"
    finally:
        try:
            os.remove(list_path)
        except OSError:
            pass

    return f"/static/videos/{concat_name}", None


def _repair_scenes_parallel(client, keys, scene_scripts, clip_urls, per_scene_logs,
                            scene_class, quality, aspect_ratio, persona, progress=None):
    """Scene-scoped overlap repair for the parallel render path.

    Same accept-if-better contract as _repair_overlaps, applied per scene: only the
    scenes whose probe measured violations are sent to the repair agent, and a repaired
    scene replaces its clip only if it renders AND reduces *that scene's* violation
    count. A clean scene is never re-rendered (an N-scene video no longer pays N scene
    renders to fix one), and a losing candidate never displaces a good clip.

    Returns (scene_scripts, clip_urls, per_scene_logs, rounds_used, scenes_improved).
    """
    offending = [i for i, lg in enumerate(per_scene_logs) if _overlap_violations(lg)]
    if not offending or os.getenv("OVERLAP_REPAIR", "1") != "1":
        return scene_scripts, clip_urls, per_scene_logs, 0, 0

    total = sum(len(_overlap_violations(lg)) for lg in per_scene_logs)
    if not llm_available(client, keys):
        logger.warning(f"{total} overlap violation(s) across {len(offending)} scene(s) "
                       f"measured but no LLM available to repair.")
        return scene_scripts, clip_urls, per_scene_logs, 0, 0

    scene_scripts = list(scene_scripts)
    clip_urls = list(clip_urls)
    per_scene_logs = list(per_scene_logs)
    max_rounds = int(os.getenv("OVERLAP_REPAIR_ROUNDS", "2"))
    rounds_used = 0
    scenes_improved = 0

    logger.warning(f"Render OK but {total} layout violation(s) measured in "
                   f"{len(offending)}/{len(scene_scripts)} scene(s); repairing scene-scoped.")

    for idx in offending:
        violations = _overlap_violations(per_scene_logs[idx])
        rounds = 0
        improved = False
        while violations and rounds < max_rounds:
            rounds += 1
            rounds_used += 1
            logger.warning(f"Scene {idx + 1}: {len(violations)} violation(s); "
                           f"repair round {rounds}/{max_rounds}...")
            if progress:
                progress(f"Fixing {len(violations)} layout issue(s) in scene {idx + 1}, "
                         f"round {rounds}...")
            try:
                _prev_code = scene_scripts[idx]
                repaired = repair_code_with_gemini(
                    client, _prev_code, _overlap_error_report(violations), scene_class, keys=keys)
                repaired = sanitize_generated_code(repaired, persona)
            except Exception as e:
                logger.warning(f"Scene {idx + 1} overlap repair round {rounds} crashed: {e}")
                break
            if not repaired or repaired == _prev_code:
                break
            if not _repair_preserves_assets(_prev_code, repaired):
                logger.warning(f"Scene {idx + 1}: repair dropped a fetch_real_image asset; "
                               "rejecting candidate.")
                break

            ok, new_url, new_logs = compile_manim_code(
                repaired, scene_class, quality, aspect_ratio, persona)
            if not ok:
                logger.warning(f"Scene {idx + 1}: repaired code failed to render; keeping its clip.")
                _discard_video(new_url, keep=tuple(clip_urls))
                break

            new_violations = _overlap_violations(new_logs)
            if len(new_violations) < len(violations):
                _store_repair_pair("\n".join(violations), _prev_code, repaired, scene_class)
                superseded = clip_urls[idx]
                scene_scripts[idx], clip_urls[idx], per_scene_logs[idx] = repaired, new_url, new_logs
                violations = new_violations
                improved = True
                _discard_video(superseded, keep=tuple(clip_urls))
            else:
                logger.warning(f"Scene {idx + 1}: repair did not reduce violations; keeping its clip.")
                _discard_video(new_url, keep=tuple(clip_urls))
                break
        if improved:
            scenes_improved += 1

    remaining = sum(len(_overlap_violations(lg)) for lg in per_scene_logs)
    if remaining:
        logger.warning(f"{remaining} layout violation(s) remain after {rounds_used} "
                       f"scene-scoped repair round(s).")
    elif rounds_used:
        logger.info(f"All layout violations resolved after {rounds_used} scene-scoped repair round(s).")
    return scene_scripts, clip_urls, per_scene_logs, rounds_used, scenes_improved


def _attribute_vision_findings(findings, clip_urls):
    """Map concat-timeline vision findings back to the scene that produced them.

    Returns {scene_index: [scene-local finding lines]} or None when clip durations
    can't be measured (in which case the caller must stay report-only rather than
    guess a scene to rewrite). Timestamps are rebased to scene-local time so the
    repair agent sees seconds that match the script it is editing.
    """
    try:
        from .pipeline.vision_qa import _probe_duration  # one duration impl (P5)
        offsets, total = [], 0.0
        for url in clip_urls:
            path = _video_path(url)
            if not path or not os.path.exists(path):
                return None
            offsets.append(total)
            total += _probe_duration(path)
        if total <= 0:
            return None
    except Exception as e:
        logger.warning("Vision attribution unavailable (%s); staying report-only.", e)
        return None

    per_scene = {}
    for line in findings:
        m = re.search(r"\bt=([0-9.]+)s", line)
        if not m:
            continue
        t = float(m.group(1))
        idx = 0
        for i, start in enumerate(offsets):
            if t >= start:
                idx = i
        local = round(t - offsets[idx], 2)
        per_scene.setdefault(idx, []).append(
            re.sub(r"\bt=[0-9.]+s", f"t={local}s", line, count=1))
    return per_scene


def _repair_scenes_vision(client, keys, scene_scripts, clip_urls, per_scene_logs,
                          concat_url, findings, scene_class, quality, aspect_ratio,
                          persona, progress=None):
    """Scene-scoped vision repair for the parallel path.

    Work is scene-scoped (only flagged scenes are rewritten and re-rendered), but
    ACCEPTANCE is artifact-level: a vision critique is a metered call, so instead of
    re-critiquing every candidate clip we re-concat once and re-critique the whole
    video, accepting only if total findings strictly drop. Each individual scene
    candidate must additionally not increase that scene's own (free) geometric
    violation count — never trade a probe regression for a vision improvement.

    Returns (scene_scripts, clip_urls, per_scene_logs, concat_url, findings, rounds).
    On any failure everything comes back exactly as it went in (P1).
    """
    try:
        from .pipeline.vision_qa import VisionQAStage
        stage = VisionQAStage()
        if not findings or not stage.enabled() or os.getenv("VISION_QA_REPAIR", "1") != "1":
            return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0
        if not llm_available(client, keys):
            logger.warning("%d vision finding(s) measured but no LLM available to repair.",
                           len(findings))
            return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0

        attributed = _attribute_vision_findings(findings, clip_urls)
        if not attributed:
            logger.warning("Vision findings could not be attributed to scenes; "
                           "reporting without repair.")
            return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0

        new_scripts, new_clips = list(scene_scripts), list(clip_urls)
        new_logs = list(per_scene_logs)
        repaired_any = 0
        logger.warning("Vision QA: %d finding(s) across %d/%d scene(s); repairing scene-scoped.",
                       len(findings), len(attributed), len(scene_scripts))

        for idx, scene_findings in sorted(attributed.items()):
            if progress:
                progress(f"Fixing {len(scene_findings)} visual issue(s) in scene {idx + 1}...")
            try:
                candidate = repair_code_with_gemini(
                    client, new_scripts[idx], _vision_error_report(scene_findings),
                    scene_class, keys=keys)
                candidate = sanitize_generated_code(candidate, persona)
            except Exception as e:
                logger.warning("Scene %d vision repair crashed: %s", idx + 1, e)
                continue
            if not candidate or candidate == new_scripts[idx]:
                continue
            if not _repair_preserves_assets(new_scripts[idx], candidate):
                logger.warning("Scene %d: vision repair discarded assets; rejected.", idx + 1)
                continue
            ok, cand_url, cand_logs = compile_manim_code(
                candidate, scene_class, quality, aspect_ratio, persona)
            if not ok:
                logger.warning("Scene %d: vision-repaired code failed to render.", idx + 1)
                _discard_video(cand_url, keep=tuple(new_clips) + tuple(clip_urls))
                continue
            if len(_overlap_violations(cand_logs)) > len(_overlap_violations(per_scene_logs[idx])):
                logger.warning("Scene %d: vision repair added geometric violations; rejected.",
                               idx + 1)
                _discard_video(cand_url, keep=tuple(new_clips) + tuple(clip_urls))
                continue
            new_scripts[idx], new_clips[idx], new_logs[idx] = candidate, cand_url, cand_logs
            repaired_any += 1

        if not repaired_any:
            return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0

        cand_concat, cerr = _concat_scene_clips(new_clips)
        if not cand_concat:
            logger.warning("Vision repair re-concat failed (%s); keeping the original video.", cerr)
            for i, u in enumerate(new_clips):
                if u != clip_urls[i]:
                    _discard_video(u, keep=tuple(clip_urls))
            return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0

        new_findings = stage.critique(_video_path(cand_concat))
        if len(new_findings) < len(findings):
            logger.info("Vision repair accepted: %d → %d finding(s) across %d scene(s).",
                        len(findings), len(new_findings), repaired_any)
            for i, u in enumerate(clip_urls):
                if u != new_clips[i]:
                    _discard_video(u, keep=tuple(new_clips))
            _discard_video(concat_url, keep=(cand_concat,))
            return new_scripts, new_clips, new_logs, cand_concat, new_findings, repaired_any

        logger.warning("Vision repair did not reduce findings (%d → %d); keeping the original video.",
                       len(findings), len(new_findings))
        _discard_video(cand_concat, keep=tuple(clip_urls) + (concat_url,))
        for i, u in enumerate(new_clips):
            if u != clip_urls[i]:
                _discard_video(u, keep=tuple(clip_urls) + (concat_url,))
        return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0
    except Exception as e:
        logger.warning("Scene-scoped vision repair stood aside (%s).", e)
        return scene_scripts, clip_urls, per_scene_logs, concat_url, findings, 0


def _run_render_job(job_id, code, scene_class, quality, aspect_ratio, persona="hybrid",
                    scene_scripts=None):
    _set_job(job_id, state="running")
    try:
        # ── Parallel fast-path: render scenes simultaneously, ffmpeg-concat ───
        # Falls back to the sequential single-script path on any scene failure.
        if scene_scripts and len(scene_scripts) > 1 and os.getenv("PARALLEL_RENDER", "1") != "0":
            logger.info("Parallel render: attempting %d scenes.", len(scene_scripts))
            _t_par = time.time()
            p_ok, clip_urls, scene_logs = _render_scenes_parallel(
                scene_scripts, scene_class, quality, aspect_ratio, persona
            )
            p_url = None
            if p_ok:
                p_url, _cerr = _concat_scene_clips(clip_urls)
                if not p_url:
                    logger.warning("Parallel concat failed: %s", _cerr)
                    for _u in clip_urls:
                        _discard_video(_u)
                    p_ok = False
            if p_ok:
                # Repair the scenes the probe flagged, then re-concat. The pre-repair
                # concat stays on disk until a strictly better one exists.
                keys = env_api_keys()
                client = get_genai_client(keys)
                scene_scripts, clip_urls, scene_logs, _ov_rounds, _fixed = _repair_scenes_parallel(
                    client, keys, scene_scripts, clip_urls, scene_logs,
                    scene_class, quality, aspect_ratio, persona,
                    progress=lambda msg: _set_job(job_id, progress=msg),
                )
                if _fixed:
                    _new_url, _cerr2 = _concat_scene_clips(clip_urls)
                    if _new_url:
                        _discard_video(p_url, keep=(_new_url,))
                        p_url = _new_url
                    else:
                        logger.warning("Re-concat after scene repair failed (%s); "
                                       "keeping the pre-repair video.", _cerr2)
                # Vision QA on the shipped concat, then SCENE-SCOPED repair: only the
                # scenes whose frames were flagged are rewritten and re-rendered, and
                # the re-concat is accepted only if total findings strictly drop.
                # NOTE the ordering: the clips must still be on disk here — attribution
                # probes their durations and repair re-concats them. Discarding them
                # before this point silently reduced vision repair to report-only.
                _, _, _, _vision, _ = _run_vision_qa(
                    None, p_url, "\n".join(scene_logs), scene_class, quality,
                    aspect_ratio, persona, allow_repair=False,
                )
                if _vision:
                    (scene_scripts, clip_urls, scene_logs, p_url, _vision,
                     _v_scenes) = _repair_scenes_vision(
                        client, keys, scene_scripts, clip_urls, scene_logs, p_url,
                        _vision, scene_class, quality, aspect_ratio, persona,
                        progress=lambda msg: _set_job(job_id, progress=msg),
                    )
                    _fixed += _v_scenes

                # Clips have served their purpose in every branch above.
                for _u in clip_urls:
                    _discard_video(_u, keep=(p_url,))

                p_logs = "\n".join(f"[Scene {i + 1}]\n{lg}" for i, lg in enumerate(scene_logs))
                _par_dur = round(time.time() - _t_par, 1)
                _bbox_par = [ln for ln in p_logs.splitlines() if "[BBOX_WARNING]" in ln]
                anim_beats = sum(len(re.findall(r'\bself\.play\b', s)) for s in scene_scripts)
                logger.info("Parallel render complete: %d scenes merged in %.1fs → %s",
                            len(scene_scripts), _par_dur, os.path.basename(p_url))
                _degraded_par = _tts_degraded_lines(p_logs)
                _write_video_sidecar(
                    p_url, job_id=job_id, repair_rounds=_ov_rounds,
                    violations_remaining=len(_overlap_violations(p_logs)),
                    animation_beats=anim_beats, scenes_repaired=_fixed,
                    vision_findings=len(_vision), voice_degraded=len(_degraded_par),
                    shape_overlaps=len(_shape_overlap_lines(p_logs)),
                    voice_muted=_tts_was_muted(p_logs),
                )
                _set_job(job_id, state="done", success=True, video_url=p_url, logs=p_logs,
                         repair_rounds=_ov_rounds, render_duration_seconds=_par_dur,
                         animation_beats=anim_beats, bbox_warnings=_bbox_par,
                         vision_report=_vision, voice_degraded=_degraded_par)
                return
            logger.warning("Parallel render failed; falling back to sequential single-script render.")

        _t0 = time.time()
        success, video_url, logs = compile_manim_code(code, scene_class, quality, aspect_ratio, persona)
        render_duration = round(time.time() - _t0, 1)

        repair_rounds = 0
        failure_class = _classify_render_failure(logs) if not success else None
        if failure_class == "infra":
            # Nothing a code rewrite can fix. Fail loudly and name the system, so the
            # operator retries the render instead of paying for a pointless repair.
            logger.error("Render failed in EXTERNAL INFRASTRUCTURE (TTS/network), not in the "
                         "generated code — skipping the code-repair agent. Retry the render "
                         "once the provider recovers; the shared TTS cache makes the retry cheap.")
            _set_job(job_id, progress="Render failed: external service (TTS/network) unavailable.")
        if not success and failure_class == "code":
            logger.warning("Compilation failed. Attempting self-healing runtime repair...")
            keys = env_api_keys()
            client = get_genai_client(keys)
            if llm_available(client, keys):
                max_rounds = 2
                while not success and repair_rounds < max_rounds:
                    repair_rounds += 1
                    try:
                        _prev_error = logs
                        _prev_code = code
                        repaired_code = repair_code_with_gemini(client, code, logs, scene_class, keys=keys)
                        repaired_code = sanitize_generated_code(repaired_code, persona)
                        if repaired_code and repaired_code != code:
                            if not _repair_preserves_assets(_prev_code, repaired_code):
                                logger.warning(f"Self-healing runtime repair round {repair_rounds} discarded assets; rejected.")
                                break
                            code = repaired_code
                            _t0 = time.time()
                            success, video_url, logs = compile_manim_code(code, scene_class, quality, aspect_ratio, persona)
                            render_duration = round(time.time() - _t0, 1)
                            if success:
                                _store_repair_pair(_prev_error, _prev_code, repaired_code, scene_class)
                        else:
                            break
                    except Exception as e:
                        logger.warning(f"Self-healing runtime repair round {repair_rounds} crashed: {e}")
                        break

        # Render succeeded, but the dry-run may have measured text overlaps — repair
        # them while keeping the already-good video as fallback.
        if success:
            keys = env_api_keys()
            client = get_genai_client(keys)
            _t0 = time.time()
            code, video_url, logs, overlap_rounds = _repair_overlaps(
                client, keys, code, scene_class, quality, aspect_ratio, persona,
                video_url, logs,
            )
            if overlap_rounds:
                repair_rounds += overlap_rounds
                render_duration += round(time.time() - _t0, 1)

        # Vision QA on the final artifact — full accept-if-better repair on this
        # (sequential single-script) path.
        vision_findings = []
        if success:
            _t0 = time.time()
            code, video_url, logs, vision_findings, _v_rounds = _run_vision_qa(
                code, video_url, logs, scene_class, quality, aspect_ratio, persona,
                allow_repair=True, progress=lambda msg: _set_job(job_id, progress=msg),
            )
            if _v_rounds:
                repair_rounds += _v_rounds
                render_duration += round(time.time() - _t0, 1)

        animation_beats = len(re.findall(r'\bself\.play\b', code))
        # [BBOX_WARNING] lines come from the transpiler-injected bounds check (remote feature).
        _bbox_warnings = [ln for ln in (logs or "").splitlines() if "[BBOX_WARNING]" in ln]
        _degraded = _tts_degraded_lines(logs)
        if success and video_url:
            _write_video_sidecar(
                video_url, job_id=job_id, repair_rounds=repair_rounds,
                violations_remaining=len(_overlap_violations(logs)),
                animation_beats=animation_beats, vision_findings=len(vision_findings),
                voice_degraded=len(_degraded),
                shape_overlaps=len(_shape_overlap_lines(logs)),
                voice_muted=_tts_was_muted(logs),
            )
        _set_job(job_id, state="done", success=success, video_url=video_url, logs=logs,
                 repair_rounds=repair_rounds, render_duration_seconds=render_duration,
                 animation_beats=animation_beats, bbox_warnings=_bbox_warnings,
                 vision_report=vision_findings, voice_degraded=_degraded,
                 error=(f"Render failed in external infrastructure (TTS/network) — not in the "
                        f"generated code. Retry when the provider recovers."
                        if failure_class == "infra" else None))
    except Exception as e:
        logger.exception("Render job crashed")
        _set_job(job_id, state="error", success=False, video_url=None, logs=str(e), error=str(e))


def _run_batch_render_job(job_id, nodes, style, persona, language, speaker, background, quality, aspect_ratio, skip_layout_review, tts_provider="sarvam", gemini_tts_model="google/gemini-3.1-flash-tts-preview", tech_terms="english"):
    # total_steps = len(nodes) codegen tasks + len(nodes) compile tasks
    _set_job(job_id, state="running", current_step=0, total_steps=len(nodes) * 2,
             progress="Initializing batch pipeline...")
    rendered_videos = []

    try:
        keys = env_api_keys()
        client = get_genai_client(keys)

        global_blueprint = generate_asset_blueprint({"nodes": nodes}, keys=keys)

        # --- Phase 1: Parallel storyboard + codegen ---
        _set_job(job_id, progress=f"Generating storyboards and code for {len(nodes)} node(s) in parallel...")
        logger.info(f"Batch job {job_id}: starting parallel codegen for {len(nodes)} nodes.")

        def _codegen_node(idx, node):
            node_title = node.get("content", {}).get("heading") or node.get("id") or f"Node_{idx+1}"
            context = {
                "node_type": node.get("type", "concept"),
                "ncert_content": node.get("content", {}),
                "language": language,
                "speaker": speaker,
                "video_spec": {"style": style, "persona": persona, "needed": True},
            }
            storyboard = generate_storyboard_impl(client, node_title, persona, language, style, context, speaker=speaker, tts_provider=tts_provider, gemini_tts_model=gemini_tts_model, keys=keys, tech_terms=tech_terms)
            code_res = generate_code_impl(
                client=client, storyboard=storyboard, style=style, background=background,
                persona=persona, language=language, speaker=speaker,
                tts_provider=tts_provider, gemini_tts_model=gemini_tts_model,
                skip_layout_review=skip_layout_review,
                scene_index=idx,
                global_blueprint=global_blueprint,
                keys=keys,
            )
            return node_title, code_res["code"], code_res["scene_class"], storyboard

        codegen_workers = min(len(nodes), int(os.getenv("CODEGEN_WORKERS", "3")))
        codegen_results = {}  # idx â†’ (node_title, code, scene_class) or Exception

        with ThreadPoolExecutor(max_workers=codegen_workers) as codegen_pool:
            future_to_idx = {
                codegen_pool.submit(_codegen_node, idx, node): idx
                for idx, node in enumerate(nodes)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                node_label = nodes[idx].get("content", {}).get("heading") or nodes[idx].get("id") or f"Node_{idx+1}"
                try:
                    codegen_results[idx] = future.result()
                    done = len(codegen_results)
                    _set_job(job_id, current_step=done,
                             progress=f"Codegen: {done}/{len(nodes)} nodes ready...")
                    logger.info(f"Codegen complete for '{node_label}' ({done}/{len(nodes)}).")
                except Exception as e:
                    logger.error(f"Codegen failed for '{node_label}': {e}")
                    codegen_results[idx] = e

        # --- Phase 2: Assembly & Single Compilation (Shared Dictionary Pattern) ---
        total_repair_rounds = 0
        total_render_duration = 0.0
        total_missing = 0
        total_fallback = 0

        methods = []
        for idx in range(len(nodes)):
            result = codegen_results.get(idx)
            node_label = nodes[idx].get("content", {}).get("heading") or nodes[idx].get("id") or f"Node_{idx+1}"

            if isinstance(result, Exception) or result is None:
                err_msg = f"Halted: Codegen failed for node '{node_label}'."
                logger.error(err_msg)
                _set_job(job_id, state="error", success=False, progress=err_msg, logs=str(result))
                return

            node_title, node_code, scene_class, storyboard = result
            
            non_manim = storyboard.get("non_manim_items", [])
            total_missing += len(non_manim)
            
            assets = _collect_asset_elements(storyboard)
            for asset in assets:
                res = probe_asset(asset["type"], asset["keyword"])
                if res.get("status") == "fallback":
                    total_fallback += 1

            method_code = extract_method_from_code(node_code, f"build_scene_{idx}")
            methods.append(method_code)

        _set_job(job_id, progress="Assembling master script...")
        
        master_code = f"from manim import *\nfrom manim_voiceover import VoiceoverScene\nfrom viz_helpers import *\n\nclass STEMAnimation(VoiceoverScene):\n    def construct(self):\n        self.set_speech_service(UniversalTTSService(language=\"{language}\", speaker=\"{speaker}\", tts_provider=\"{tts_provider}\", gemini_tts_model=\"{gemini_tts_model}\"))\n"
        if background != "default":
            master_code += f'        set_realistic_background(self, "{background}", dim=0.5)\n'
        
        master_code += "        self.shared_objects = {}\n"
        
        for idx in range(len(nodes)):
            master_code += f"        self.build_scene_{idx}()\n"
        master_code += "        auto_fit_scene(self)\n"

        for m_code in methods:
            if m_code:
                indented_m = "\n".join("    " + line for line in m_code.split("\n"))
                master_code += "\n" + indented_m + "\n"

        _set_job(job_id, progress="Compiling master script...", current_step=len(nodes) + 1)
        _t0 = time.time()
        success, video_url, logs = compile_manim_code(master_code, "STEMAnimation", quality, aspect_ratio, persona)
        total_render_duration += round(time.time() - _t0, 1)
        
        repair_rounds = 0
        batch_failure = _classify_render_failure(logs) if not success else None
        if not success and batch_failure == "code":
            logger.warning("Master script compilation failed (code error). Attempting self-healing repair...")
            if llm_available(client, keys):
                max_rounds = 2
                while not success and repair_rounds < max_rounds:
                    repair_rounds += 1
                    _set_job(job_id, progress=f"Self-healing repair round {repair_rounds}...")
                    try:
                        _prev_error = logs
                        _prev_code = master_code
                        repaired_code = repair_code_with_gemini(client, master_code, logs, "STEMAnimation", keys=keys)
                        repaired_code = sanitize_generated_code(repaired_code, persona)
                        if repaired_code and repaired_code != master_code:
                            if not _repair_preserves_assets(_prev_code, repaired_code):
                                logger.warning(f"Self-healing repair round {repair_rounds} discarded assets; rejected.")
                                break
                            master_code = repaired_code
                            _t0 = time.time()
                            success, video_url, logs = compile_manim_code(master_code, "STEMAnimation", quality, aspect_ratio, persona)
                            total_render_duration += round(time.time() - _t0, 1)
                            if success:
                                _store_repair_pair(_prev_error, _prev_code, repaired_code, "STEMAnimation")
                        else:
                            break
                    except Exception as e:
                        logger.warning(f"Self-healing repair round {repair_rounds} crashed: {e}")
                        break
        total_repair_rounds += repair_rounds

        if not success:
            err_msg = "Halted: Master script compilation failed after self-healing attempts."
            logger.error(err_msg)
            _set_job(job_id, state="error", success=False, progress=err_msg, logs=logs)
            return

        # Post-pass: fix measured text overlaps, keeping the rendered video as fallback.
        _t0 = time.time()
        master_code, video_url, logs, _overlap_rounds = _repair_overlaps(
            client, keys, master_code, "STEMAnimation", quality, aspect_ratio, persona,
            video_url, logs, progress=lambda msg: _set_job(job_id, progress=msg),
        )
        if _overlap_rounds:
            total_repair_rounds += _overlap_rounds
            total_render_duration += round(time.time() - _t0, 1)
        _write_video_sidecar(
            video_url, job_id=job_id, repair_rounds=total_repair_rounds,
            violations_remaining=len(_overlap_violations(logs)),
            animation_beats=sum(c.count("self.play") for c in methods if c),
        )

        actual_duration = 0.0
        if video_url:
            filename = os.path.basename(video_url)
            local_path = os.path.join(VIDEO_DIR, filename)
            try:
                import subprocess
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", local_path]
                probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
                actual_duration = float(probe_res.stdout.strip())
            except Exception as e:
                logger.warning(f"Failed to extract duration with ffprobe: {e}")

        scorecard = {
            "asset_fallbacks": total_fallback,
            "asset_missing": total_missing,
            "repair_rounds": total_repair_rounds,
            "duration_seconds": round(actual_duration, 1),
            "animation_beats": sum(code.count("self.play") for code in methods if code)
        }

        final_url = video_url if success else None
        _set_job(job_id, state="done", success=True, video_url=final_url,
                 progress="Completed successfully!", scorecard=scorecard, logs=logs,
                 render_duration_seconds=round(total_render_duration, 1),
                 node_count=len(nodes))
        logger.info(f"Batch render completed successfully! Final video: {final_url}")

    except Exception as e:
        logger.exception("Batch render job crashed")
        _set_job(job_id, state="error", success=False, progress=f"Failed: {str(e)}", logs=str(e))
