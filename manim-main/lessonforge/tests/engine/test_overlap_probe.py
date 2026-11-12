"""Overlap/clip probe + repair post-pass acceptance harness.

Exercises the per-beat layout probe injected by compile_manim_code's dry-run and
the _repair_overlaps post-pass (with the LLM repair agent stubbed, so no API keys
are needed — every render is real).

Part A (detection, real renders):
  - text drawn over un-faded text from a previous beat  -> 'overlap' violation
  - text partially cut off by the frame edge            -> 'off-frame' violation
  - text parked fully off-screen for a slide-in         -> NOT flagged
  - busy-but-clean scene (Axes, MathTex, arranged text) -> zero violations

Part B (repair state machine, repair agent stubbed):
  - fix that removes the overlap        -> accepted, new video, original deleted
  - fix that doesn't render             -> rejected, original video kept
  - fix that doesn't reduce violations  -> rejected, original kept, candidate deleted
  - OVERLAP_REPAIR=0                    -> post-pass is a no-op

Part C (scene-scoped repair on the parallel path, repair agent stubbed):
  - only the scenes the probe flagged are sent to the repair agent
  - a clean scene's clip is never re-rendered
  - an improved scene swaps its clip; the superseded clip is deleted
  - clips concat before and after repair

Usage:
    python test_overlap_probe.py           # cleans up its rendered mp4s afterwards
    python test_overlap_probe.py --keep    # keep the renders (they show as "Raw" on /timeline)

Exit 0 = all pass, 1 = any fail (CI-friendly). Requires manim + app deps installed.
"""
import os
import sys

KEEP = "--keep" in sys.argv
_PRODUCED = []

import lessonforge.engine as app  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    ok = bool(cond)
    PASS += ok
    FAIL += not ok
    print(f"  {'✓' if ok else '✗'} {name:42s} {'PASS' if ok else 'FAIL  ' + detail}")


HEADER = "from manim import *\nfrom viz_helpers import *\n\n"

OVERLAP = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        t1 = Text("Photosynthesis converts light energy", font_size=36).move_to([0, 1, 0])
        self.play(Write(t1))
        t2 = Text("Chlorophyll absorbs sunlight here", font_size=36).move_to([0, 0.9, 0])
        self.play(Write(t2))
        self.wait(0.5)
'''

CLIPPED = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        t = Text("This label is cut off by the frame edge", font_size=36, safe_width=False)
        t.move_to([6.5, 0, 0])
        self.play(FadeIn(t))
        self.wait(0.5)
'''

PARKED = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        t = Text("Sliding in from the right", font_size=36)
        t.move_to([12, 0, 0])
        self.add(t)
        self.play(Circle().animate.shift(UP))
        self.play(t.animate.move_to([0, 0, 0]))
        self.wait(0.5)
'''

BUSY_CLEAN = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        title = Text("Quadratic Functions", font_size=0.8 * 48).move_to([0, TITLE_Y, 0])
        self.play(Write(title))
        ax = Axes(x_range=[-3, 3, 1], y_range=[0, 9, 3], x_length=6, y_length=4,
                  axis_config={"include_numbers": True}).move_to([-2.5, -0.5, 0])
        graph = ax.plot(lambda x: x ** 2, color=BLUE)
        eq = MathTex(r"y = x^2 + 2x + 1").move_to([3.5, 1, 0])
        pts = VGroup(
            Text("Opens upward", font_size=0.55 * 48),
            Text("Vertex at origin", font_size=0.55 * 48),
        ).arrange(DOWN, buff=0.4, aligned_edge=LEFT).move_to([3.5, -1.5, 0])
        self.play(Create(ax), Create(graph))
        self.play(Write(eq), Write(pts))
        self.wait(0.5)
'''

TEXT_OVER_AXIS = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        # Bug on purpose: formula sits ON the x-axis line (the distance-formula bug)
        ax = Axes(x_range=[-6, 6, 1], y_range=[-3, 3, 1], x_length=12, y_length=6)
        self.play(Create(ax))
        eq = MathTex(r"d = \\\\sqrt{(x_2-x_1)^2 + (y_2-y_1)^2}", font_size=40)
        eq.move_to([0, -0.1, 0])
        self.play(Write(eq))
        self.wait(0.5)
'''

LABEL_IN_BOX = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        # Legit: label grouped with its box; text fully inside an ungrouped circle
        box = VGroup(Rectangle(width=4, height=1.2),
                     Text("Grouped label", font_size=30)).move_to([0, 2, 0])
        self.play(FadeIn(box))
        c = Circle(radius=1.6).move_to([0, -1.5, 0])
        v = Text("A", font_size=30).move_to([0, -1.5, 0])
        self.play(Create(c), Write(v))
        self.wait(0.5)
'''

PLANE_BACKDROP = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        # Legit: text over a NumberPlane grid backdrop is normal
        plane = NumberPlane(x_range=[-7, 7, 1], y_range=[-4, 4, 1])
        self.play(Create(plane))
        t = Text("Text over a grid is fine", font_size=36).move_to([0, 1, 0])
        self.play(Write(t))
        self.wait(0.5)
'''

CLEAN_FIX = HEADER + '''class STEMAnimation(Scene):
    def construct(self):
        t1 = Text("Photosynthesis converts light energy", font_size=36).move_to([0, 1, 0])
        self.play(Write(t1))
        self.play(FadeOut(t1))
        t2 = Text("Chlorophyll absorbs sunlight here", font_size=36).move_to([0, 0.9, 0])
        self.play(Write(t2))
        self.wait(0.5)
'''

BROKEN_FIX = "this is not python at all ("


def _track(url):
    if url:
        _PRODUCED.append(url)
    return url


def _videos_snapshot():
    """Filenames currently in static/videos — used to prove a rejected repair
    candidate leaves nothing behind."""
    return {f for f in os.listdir(app.VIDEO_DIR) if f.endswith(".mp4")}


def _video_exists(url):
    return bool(url) and os.path.exists(os.path.join(app.VIDEO_DIR, os.path.basename(url)))


def _cleanup():
    if KEEP:
        print(f"\n--keep: leaving {len(_PRODUCED)} test render(s) in static/videos")
        return
    for url in _PRODUCED:
        try:
            os.remove(os.path.join(app.VIDEO_DIR, os.path.basename(url)))
        except OSError:
            pass
    print(f"\nCleaned up {len(_PRODUCED)} test render(s)")


def main():
    print("\nPart A — detection through compile_manim_code (real renders)\n")
    res = {}
    for name, code in [("overlap", OVERLAP), ("clipped", CLIPPED),
                       ("parked", PARKED), ("busy_clean", BUSY_CLEAN),
                       ("text_over_axis", TEXT_OVER_AXIS), ("label_in_box", LABEL_IN_BOX),
                       ("plane_backdrop", PLANE_BACKDROP)]:
        ok, url, logs = app.compile_manim_code(code, "STEMAnimation", quality="l")
        _track(url)
        res[name] = (ok, url, logs, app._overlap_violations(logs))

    ok, _, logs, v = res["overlap"]
    check("overlap scene renders", ok, logs[-300:] if not ok else "")
    check("overlap flagged", any("overlap" in ln for ln in v), str(v))
    ok, _, logs, v = res["clipped"]
    check("clipped scene renders", ok, logs[-300:] if not ok else "")
    check("clipped text flagged as off-frame", any("off-frame" in ln for ln in v), str(v))
    ok, _, _, v = res["parked"]
    check("parked scene renders", ok)
    check("parked off-screen text NOT flagged", not any("off-frame" in ln for ln in v), str(v))
    ok, _, logs, v = res["busy_clean"]
    check("busy clean scene renders", ok, logs[-300:] if not ok else "")
    check("busy clean scene: zero violations", not v, str(v))
    ok, _, logs, v = res["text_over_axis"]
    check("text-over-axis scene renders", ok, logs[-300:] if not ok else "")
    check("axis-struck formula flagged", any("text-over-shape" in ln for ln in v), str(v))
    ok, _, _, v = res["label_in_box"]
    check("grouped/inside labels NOT flagged", not any("text-over-shape" in ln for ln in v), str(v))
    ok, _, _, v = res["plane_backdrop"]
    check("NumberPlane backdrop NOT flagged", not any("text-over-shape" in ln for ln in v), str(v))

    print("\nPart B — _repair_overlaps state machine (stubbed repair agent)\n")
    # app.py is now the app/ package; the render/repair core lives in app.render and
    # resolves repair_code_with_gemini / llm_available / _store_repair_pair in ITS own
    # namespace (imported by name). Patch them on app.render so the internal callers see
    # the stubs. The CALLED functions (app._repair_overlaps, app._overlap_violations, …)
    # stay on `app` — they are re-exports of the same render functions.
    app.render.llm_available = lambda client, keys=None: True
    app.render._store_repair_pair = lambda *a, **k: None
    base_url, base_logs = res["overlap"][1], res["overlap"][2]

    # Rejection cases run first so they share one base video; the accepting case
    # runs last because it deletes that base (superseded-artifact cleanup).
    app.render.repair_code_with_gemini = lambda client, code, err, sc, keys=None: BROKEN_FIX
    code3, url3, _, _ = app._repair_overlaps(
        None, None, OVERLAP, "STEMAnimation", "l", "widescreen", "hybrid", base_url, base_logs)
    check("broken fix: original code kept", code3 == OVERLAP)
    check("broken fix: original video kept", url3 == base_url, f"{url3}")

    # A non-improving candidate DOES render, so it is the leak case: its mp4 must be
    # deleted, leaving static/videos exactly as it was before the round.
    before = _videos_snapshot()
    app.render.repair_code_with_gemini = lambda client, code, err, sc, keys=None: OVERLAP + "\n# retry\n"
    _, url4, _, rounds4 = app._repair_overlaps(
        None, None, OVERLAP, "STEMAnimation", "l", "widescreen", "hybrid", base_url, base_logs)
    check("non-improving fix: original video kept", url4 == base_url and rounds4 == 1,
          f"url={url4} rounds={rounds4}")
    leaked = _videos_snapshot() - before
    check("rejected candidate leaves no mp4", not leaked, f"leaked={sorted(leaked)}")

    os.environ["OVERLAP_REPAIR"] = "0"
    called = []
    app.render.repair_code_with_gemini = lambda *a, **k: called.append(1) or CLEAN_FIX
    _, url5, _, rounds5 = app._repair_overlaps(
        None, None, OVERLAP, "STEMAnimation", "l", "widescreen", "hybrid", base_url, base_logs)
    check("OVERLAP_REPAIR=0: no-op", rounds5 == 0 and not called and url5 == base_url)
    os.environ["OVERLAP_REPAIR"] = "1"

    app.render.repair_code_with_gemini = lambda client, code, err, sc, keys=None: CLEAN_FIX
    code2, url2, logs2, rounds = app._repair_overlaps(
        None, None, OVERLAP, "STEMAnimation", "l", "widescreen", "hybrid", base_url, base_logs)
    _track(url2)
    check("good fix: accepted", code2 != OVERLAP and rounds == 1, f"rounds={rounds}")
    check("good fix: new video", url2 and url2 != base_url, f"{url2}")
    check("good fix: violations gone", not app._overlap_violations(logs2))
    check("good fix: superseded original deleted", not _video_exists(base_url), f"{base_url}")

    print("\nPart C — scene-scoped repair on the parallel path (stubbed repair agent)\n")
    scripts = [OVERLAP, BUSY_CLEAN]
    ok_par, clips, scene_logs = app._render_scenes_parallel(
        scripts, "STEMAnimation", "l", "widescreen", "hybrid")
    for c in clips:
        _track(c)
    check("parallel render: both scenes render", ok_par and all(clips), f"{clips}")
    check("parallel render: per-scene logs are scene-scoped",
          bool(app._overlap_violations(scene_logs[0])) and not app._overlap_violations(scene_logs[1]),
          f"s1={len(app._overlap_violations(scene_logs[0]))} s2={len(app._overlap_violations(scene_logs[1]))}")

    concat_url, cerr = app._concat_scene_clips(clips)
    _track(concat_url)
    check("clips concat into one video", concat_url and _video_exists(concat_url), f"{cerr}")

    sent = []
    app.render.repair_code_with_gemini = lambda client, code, err, sc, keys=None: sent.append(code) or CLEAN_FIX
    superseded = clips[0]
    scripts2, clips2, logs2b, rounds_c, fixed = app._repair_scenes_parallel(
        None, None, scripts, clips, scene_logs, "STEMAnimation", "l", "widescreen", "hybrid")
    for c in clips2:
        _track(c)
    check("only the flagged scene is repaired", len(sent) == 1 and sent[0] == OVERLAP, f"sent={len(sent)}")
    check("clean scene's clip untouched", clips2[1] == clips[1] and scripts2[1] == BUSY_CLEAN)
    check("flagged scene's clip swapped", clips2[0] and clips2[0] != superseded, f"{clips2[0]}")
    check("scene repair accounting", rounds_c == 1 and fixed == 1, f"rounds={rounds_c} fixed={fixed}")
    check("scene violations resolved", not app._overlap_violations(logs2b[0]), str(logs2b[0][-200:]))
    check("superseded scene clip deleted", not _video_exists(superseded), f"{superseded}")

    reconcat_url, cerr2 = app._concat_scene_clips(clips2)
    _track(reconcat_url)
    check("repaired clips re-concat", reconcat_url and _video_exists(reconcat_url), f"{cerr2}")

    os.environ["OVERLAP_REPAIR"] = "0"
    sent2 = []
    app.render.repair_code_with_gemini = lambda *a, **k: sent2.append(1) or CLEAN_FIX
    _, clips3, _, rounds3, fixed3 = app._repair_scenes_parallel(
        None, None, scripts, clips2, scene_logs, "STEMAnimation", "l", "widescreen", "hybrid")
    check("OVERLAP_REPAIR=0: scene repair is a no-op",
          rounds3 == 0 and fixed3 == 0 and not sent2 and clips3 == clips2)
    os.environ["OVERLAP_REPAIR"] = "1"

    _cleanup()
    print(f"\n{'ALL PASSED' if not FAIL else 'FAILED'} — {FAIL} failure(s) / {PASS + FAIL} total")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
