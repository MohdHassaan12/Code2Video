"""``lessonforge`` — command line for both production paths.

    lessonforge doctor                         what is installed / configured
    lessonforge serve                          engine server + Studio UI (localhost:5000)
    lessonforge spend                          the metered-call ledger against the budget
    lessonforge plan "Trigonometry" --audience "Class 10" -o briefs.json   a chapter → a series of lessons
    lessonforge lesson mend DIR                re-time out-of-step steps, re-render only those chapters
    lessonforge harness BRIEFS.json            brief(s) → script → critic → speech → video → checks → review
    lessonforge card BRIEF.json | "topic"      sources → teaching card for a topic (no video)
    lessonforge script SCRIPT.txt [--check]    a script you wrote → video (your words spoken as written)
    lessonforge feedback [JOB]                 what student reviews say, with the signals worth acting on
    lessonforge stats [--days N]               visitors, lessons, plays, reviews and spend
    lessonforge budget [USD | +USD]            show the spending cap, set it, or raise it — no restart needed
    lessonforge publish [JOB ...] [--all]      finished lessons → Cloudflare R2 for the viewer site (--dry-run)

    lessonforge lesson build DIR               audio → chapters → video → checks → review page
    lessonforge lesson audio|render|assemble|check DIR      the same, one stage at a time
    lessonforge lesson validate DIR            contract errors, before anything is spent
    lessonforge lesson to-board DIR            the lesson as an engine storyboard (JSON)

    lessonforge board transpile BOARD.json     storyboard → Manim source (no model call)
    lessonforge board render BOARD.json        storyboard → verified mp4 through the engine
    lessonforge board to-lesson BOARD.json DIR an engine storyboard as a lesson contract

    lessonforge kits list                      the subject kits and the lesson-visuals components
    lessonforge kits describe NAME             one kit: what it draws, its rules, example figures
    lessonforge kits route "text" [--classes 7,8]   which kit draws each part of a brief (code only, free)
    lessonforge kits run BRIEF.md [--lesson L.json] [--cap USD] [--film]   route, write, check, repair, file, film
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path


def _doctor(_args) -> int:
    from . import paths
    ok = True

    def row(label, good, detail="", required=True):
        nonlocal ok
        ok &= bool(good) or not required
        mark = "ok  " if good else ("MISSING" if required else "absent ")
        print(f"  {mark:8s}{label:26s}{detail}")

    print("Required")
    row("ffmpeg / ffprobe", shutil.which("ffmpeg") and shutil.which("ffprobe"), shutil.which("ffmpeg") or "")
    try:
        import manim
        row("manim", True, manim.__version__)
    except Exception as exc:  # pragma: no cover - environment dependent
        row("manim", False, str(exc))
    print("Recommended")
    row("LaTeX (MathTex)", shutil.which("latex"), shutil.which("latex") or "math falls back to plain text", False)
    row("dvisvgm", shutil.which("dvisvgm"), "", False)
    row("SoX", shutil.which("sox"), shutil.which("sox") or "a stand-in is generated; voice speed changes unavailable", False)
    print("Speech / model providers (each tier degrades to the next)")
    for key in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "SARVAM_AI_KEY"):
        row(key, os.getenv(key), "set" if os.getenv(key) else "", False)
    try:
        import kokoro_onnx  # noqa: F401
        model = os.getenv("KOKORO_MODEL") or str(paths.home() / "models" / "kokoro-v1.0.onnx")
        row("kokoro-onnx", True, "model " + ("found" if os.path.exists(model) else f"NOT at {model}"), False)
    except Exception:
        row("kokoro-onnx", False, "pip install lessonforge[kokoro]", False)
    print(f"Workspace: {paths.home()}")
    return 0 if ok else 1


def _serve(args) -> int:
    os.environ.setdefault("LAB_HOST", args.host)
    os.environ.setdefault("LAB_PORT", str(args.port))
    import uvicorn
    # Localhost by default ON PURPOSE: /api/compile_video executes Python posted by the
    # client. Bind wider only behind authentication.
    uvicorn.run("lessonforge.engine:app", host=args.host, port=args.port, reload=False)
    return 0


def _lesson(args) -> int:
    from .longform import build as B
    from .longform.contract import load_lesson
    root = Path(args.dir).resolve()
    lesson = load_lesson(root)
    if args.action == "validate":
        beats = sum(len(c.beats) for c in lesson.chapters)
        print(f"ok: {lesson.title!r} — {len(lesson.chapters)} chapters, {beats} beats, {lesson.word_count} words")
        scenes = B.find_scenes(root, lesson)
        missing = [c.id for c in lesson.chapters if c.scene_name not in scenes]
        print("scene code: " + ("all chapters" if not missing else f"missing for chapters {missing} (animatics will be used)"))
        return 0
    if args.action == "to-board":
        from .bridge import lesson_to_storyboard
        text = json.dumps(lesson_to_storyboard(lesson, chapter_id=args.chapter, style=args.style), indent=2, ensure_ascii=False)
        Path(args.output).write_text(text, encoding="utf-8") if args.output else print(text)
        return 0
    if args.action == "audio":
        from .longform.audio import BuildOptions, build_audio
        build_audio(lesson, root, args.voice, BuildOptions(granularity=args.granularity, fps=args.fps,
                                                           target_seconds=args.target_seconds))
        return 0
    if args.action == "mend":
        from .longform import sync_repair
        result = sync_repair.mend(root, quality=args.quality, fps=args.fps)
        return 0 if result["accepted"] or not result["chapters"] else 1
    if args.action == "render":
        B.render_chapters(root, lesson, quality=args.quality, fps=args.fps, jobs=args.jobs, only=args.only,
                          renderer=args.renderer)
        return 0
    if args.action in ("assemble", "check"):
        from .longform.review import write_review
        if args.action == "assemble":
            video = B.assemble(root, B.find_clips(root, lesson), lesson)
        else:
            video = root / "output" / f"{B.slugify(lesson.title)}.mp4"
        report = B.run_checks(root, video, lesson, quality=args.quality, fps=args.fps)
        write_review(root, lesson, video)
        return 0 if report["status"] == "technical_checks_passed" else 1
    report = B.build(root, voice=args.voice, quality=args.quality, fps=args.fps, jobs=args.jobs,
                     granularity=args.granularity, target_seconds=args.target_seconds, renderer=args.renderer)
    print(f"{report['status']}: output/{report['video']} ({report['duration_seconds']:.1f}s)")
    return 0 if report["status"] == "technical_checks_passed" else 1


def _board(args) -> int:
    board = json.loads(Path(args.board).read_text(encoding="utf-8"))
    if args.action == "to-lesson":
        from .bridge import storyboard_to_lesson
        out = Path(args.dir)
        out.mkdir(parents=True, exist_ok=True)
        lesson = storyboard_to_lesson(board, language=args.language)
        (out / "lesson.json").write_text(lesson.model_dump_json(indent=2), encoding="utf-8")
        print(f"wrote {out / 'lesson.json'} — build it with: lessonforge lesson build {out}")
        return 0
    from .bridge import transpile
    code = transpile(board, language=args.language, speaker=args.speaker, persona=args.persona,
                     tts_provider=args.tts_provider, style=args.style)
    if args.action == "transpile":
        Path(args.output).write_text(code, encoding="utf-8") if args.output else print(code)
        return 0
    if args.mute:
        os.environ["TTS_MUTE"] = "1"
    from . import engine  # boots the engine (workspace, environment self-healing)
    ok, url, logs = engine.compile_manim_code(code, "STEMAnimation", quality=args.quality, persona=args.persona)
    violations = engine._overlap_violations(logs)
    if not ok:
        print(logs[-3000:])
        print("render FAILED")
        return 1
    print(f"rendered: {engine._video_path(url)}")
    print(f"layout violations: {len(violations)}" + ("" if not violations else "\n  " + "\n  ".join(violations)))
    return 0


def _harness(args) -> int:
    from .harness import batch
    briefs = json.loads(Path(args.briefs).read_text(encoding="utf-8"))
    if isinstance(briefs, dict):
        briefs = [briefs]
    rows = batch.run_batch(briefs, quality=args.quality, voice=args.voice, parallel=args.parallel, out_dir=args.output)
    print(batch.table(rows))
    return 0 if all(r["status"] == "done" for r in rows) else 1


def _card(args) -> int:
    """Sources → teaching card for one brief, printed. Nothing is narrated or rendered."""
    from .harness import card as teaching_card
    source = Path(args.brief)
    if source.is_file():
        brief = json.loads(source.read_text(encoding="utf-8"))
        brief = brief[0] if isinstance(brief, list) else brief
    else:
        brief = {"topic": args.brief, "audience": args.audience or "", "goal": args.goal or "", "language": args.language}
    from .spend import BudgetExceeded
    try:
        made, pack = teaching_card.prepare(brief, refresh=args.refresh)
    except BudgetExceeded as exc:
        print(str(exc))
        return 2
    for s in pack["sources"]:
        print(f"  {s['id']} [{s['kind']}] {s['title'][:90]} ({s['words']} of {s['of_words']} words)")
    for warning in pack["warnings"]:
        print(f"  ! {warning}")
    if not made:
        return 1
    text = teaching_card.markdown(made)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        Path(args.output).with_suffix(".json").write_text(json.dumps(made, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"card written to {args.output}")
    else:
        print("\n" + text)
    return 0


def _script(args) -> int:
    """A video from a script file: the words are narrated as written and a model designs the screen for them."""
    from .harness import batch, scripted
    text = Path(args.script).read_text(encoding="utf-8")
    try:
        view = scripted.preview(text, args.language)
    except ValueError as exc:
        print(exc)
        return 2
    for row in view["summary"]:
        print(f"  {row['label']:9s}{row['value']}")
    for chapter in view["chapters"]:
        print(f"    - {chapter['title']} ({chapter['words']} words): {chapter['opens']}…")
    for note in view["notes"]:
        print(f"  note: {note}")
    if args.check:
        return 0
    brief = {"mode": "script", "script": text, "language": args.language or view["language"],
             "audience": args.audience, "script_edit": "fix" if args.fix else "keep"}
    rows = batch.run_batch([brief], quality=args.quality, voice=args.voice, out_dir=args.output)
    print(batch.table(rows))
    return 0 if all(r["status"] == "done" for r in rows) else 1


def _pack(args) -> int:
    """A video for a unit of a teaching pack: the model writes points and gaps, code draws, fills and checks them."""
    from .harness import batch, pack, writer
    text = Path(args.pack).read_text(encoding="utf-8")
    found = pack.units(text)
    if not args.unit:
        for u in found:
            print(f"  unit {u['number']}: {u['title']} ({len(u['sections'])} sections)")
        return 0
    briefs = [pack.brief_for(text, n, args.language) for n in args.unit]
    if args.check:
        llm = writer.default_llm()
        for brief in briefs:
            lesson = pack.lesson_for(brief, llm)
            out = Path(args.output or ".") / f"pack_unit{brief['unit']}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(lesson, indent=1, ensure_ascii=False), encoding="utf-8")
            print(pack.report(lesson), "->", out)
        return 0
    rows = batch.run_batch(briefs, quality=args.quality, voice=args.voice, out_dir=args.output)
    print(batch.table(rows))
    return 0 if all(r["status"] == "done" for r in rows) else 1


def _mcp(args) -> int:
    """Lessonforge's workbench as an MCP server (stdio, or streamable HTTP with --http)."""
    from . import mcp_server
    mcp_server.main(http=args.http, host=args.host, port=args.port)
    return 0


def _improve(args) -> int:
    """Claude over the API improves a workbench lesson, never spending more than --cap dollars."""
    from .harness import improver, workbench
    lesson_id = args.lesson
    if Path(lesson_id).is_file():
        lesson_id = workbench.add(json.loads(Path(lesson_id).read_text(encoding="utf-8")), Path(lesson_id).stem,
                                  source="file")["lesson_id"]
    result = improver.improve(lesson_id, cap_usd=args.cap, rounds=args.rounds, tier=args.model,
                              escalate=None if args.no_escalate else "sonnet", look=not args.no_look)
    print(json.dumps({k: result[k] for k in ("lesson_id", "spent_usd", "best_version", "best_score", "faults")}, indent=1))
    if args.film:
        print(json.dumps(workbench.film(lesson_id), indent=1))
        print(json.dumps(workbench.review(lesson_id), indent=1))
    return 0


def _kits(args) -> int:
    """The kit pipeline (``harness/kit_pipeline.py``): list, describe, route (all free) and run (a model only under --cap)."""
    from .harness import kit_pipeline as KP

    def err(message: str) -> int:
        print(f"lessonforge kits: {message}", file=sys.stderr)
        return 2

    def text_of(target: str | None) -> str:
        if target:
            try:
                p = Path(target)
                if p.is_file():
                    return p.read_text(encoding="utf-8")
            except OSError:
                pass
        return target or ""

    try:
        if args.what == "list":
            listed = KP.list_kits()
            print(f"kits {'on' if listed['enabled'] else 'OFF'}; mixed lessons {'on' if listed['mixed_lessons'] else 'off'}")
            for k in listed["kits"]:
                print(f"  {k['name']:11s} {','.join(k['figure_kinds']):14s} {'served' if k['served'] else 'legacy':7s} "
                      f"subjects {','.join(k['subjects']) or '-':28s} classes {KP.band(k['classes']) or '-'}")
            for c in listed["components"]:
                print(f"    component {c['id']:16s} {c['subject']:10s} classes {KP.band(c['classes'])}  {c['title']}")
            if listed["components_unavailable"]:
                print(f"  components: not available ({listed['components_unavailable']})")
            return 0
        if args.what == "describe":
            if not args.target:
                return err("describe needs a kit name")
            out = KP.describe_kit(args.target)
            print(json.dumps({k: v for k, v in out.items() if k != "rules"}, indent=1, ensure_ascii=False))
            if out.get("rules"):
                print("\nRULES THE WRITER IS GIVEN:\n" + out["rules"])
            return 0
        if args.what == "route":
            if not args.target:
                return err("route needs the text of a brief (or a file)")
            plan = KP.route(text_of(args.target), args.classes, args.subjects)
            if args.json:
                print(json.dumps(plan.to_dict(), indent=1, ensure_ascii=False))
                return 0
            for b in plan.beats:
                where = (b["kit"] + (f":{b['component']}" if b["component"] else "")) if b["kit"] else "none"
                print(f"{b['beat']:>3}. {where:24s} score {b['score']:<6} {', '.join(b['why'][:4])}\n     {b['text']}")
            print(f"kits: {', '.join(plan.kit_names()) or 'none'}{' (mixed)' if plan.mixed else ''}; classes {KP.band(plan.classes)}")
            for note in plan.notes:
                print(f"note: {note}")
            return 0
        # run
        if not args.target:
            return err("run needs a brief file (or its text)")
        cap = args.cap
        if args.lesson is None and not (cap and cap > 0):
            return err("writing the lesson needs a model: pass --cap USD (the most it may spend), or give a ready lesson with --lesson")
        llm = None
        if cap and cap > 0:
            from .harness import writer
            model = writer.default_llm()
            if model is None:
                return err("--cap was given but no model is configured (no key); run without it to check a --lesson for free")
            llm = KP.ledger_llm(model)
        report = KP.run(text_of(args.target), llm=llm, cap_usd=cap or 0.0, film=args.film, rounds=args.rounds, lesson=args.lesson,
                        classes=args.classes, subjects=args.subjects, preview=args.preview, voice=args.voice,
                        log=lambda m: print(m, file=sys.stderr))
        print(json.dumps(report.to_dict(), indent=1, ensure_ascii=False))
        return 1 if report.faults or not report.lesson_id else 0
    except KP.PipelineError as exc:
        return err(str(exc))


def _judge_frames(args) -> int:
    """A vision model judges one frame per spoken sentence of a workbench lesson's newest film."""
    from .harness import frame_judge
    report = frame_judge.judge(args.lesson, cap_usd=args.cap)
    print(json.dumps({k: report[k] for k in ("sentences", "judged", "pass_share", "held_share", "counts", "spent_usd")}, indent=1))
    return 0


def _loop(args) -> int:
    """Film, judge every sentence's frame, let Claude edit, film again: for each lesson, inside per-lesson and batch caps."""
    from .harness import loop, workbench
    ids = []
    for item in args.lessons:
        path = Path(item)
        if path.suffix == ".md" and path.is_file():
            for unit in args.unit:
                ids.append(workbench.draft_pack(str(path), unit)["lesson_id"])
        elif path.is_file():
            ids.append(workbench.add(json.loads(path.read_text(encoding="utf-8")), path.stem, source="file")["lesson_id"])
        else:
            ids.append(item)
    rows = loop.batch(ids, cap_usd=args.cap, batch_cap_usd=args.batch_cap, rounds=args.rounds, passes=args.passes)
    print(json.dumps(rows, indent=1))
    return 0


def _forge(args) -> int:
    """Videos from Lesson Forge: plan a course there (or read a saved plan), build lectures, make each a video here."""
    from . import paths
    from .harness import batch, forge
    out = Path(args.save) if args.save else paths.sub("forge_runs", time.strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    client = forge.Client(args.api, args.user, token=os.getenv("LESSON_FORGE_TOKEN") or None) if args.api else None
    if args.plan:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    elif client and args.topic:
        plan = client.plan(args.topic, args.level, language=args.language, goal=args.goal, depth=args.depth)
        (out / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"planned {plan['title']!r} ({plan.get('cost_usd', 0):.4f} USD): " +
              "; ".join(f"{i}. {lec['title']}" for i, lec in enumerate(plan["lectures"])))
    else:
        print("give a topic and --api/--user, or --plan plan.json")
        return 2
    lectures = args.lectures if args.lectures is not None else list(range(len(plan["lectures"])))
    briefs = []
    for i in lectures:
        if args.words == "writer":           # the plan is the brief; this package's writer writes the words
            briefs.append(forge.writer_brief(plan, i, **({"stop_after": "verify"} if args.check else {})))
            continue
        saved = out / f"built_{i}.json"
        if saved.is_file():
            built = json.loads(saved.read_text(encoding="utf-8"))
        elif client:
            built = client.build(plan, lecture=i)
            saved.write_text(json.dumps(built, indent=1, ensure_ascii=False), encoding="utf-8")
        else:
            print(f"lecture {i} is not built and no --api was given")
            return 2
        briefs.append(forge.brief_from(plan, built, i, **({"stop_after": "verify"} if args.check else {})))
    if args.plan_only:
        print(f"plan and builds kept in {out}")
        return 0
    rows = batch.run_batch(briefs, quality=args.quality, voice=args.voice, out_dir=out)
    print(batch.table(rows))
    return 0 if all(r["status"] == "done" for r in rows) else 1


def _plan(args) -> int:
    from .harness import planner
    llm = planner.default_llm()
    if llm is None:
        print("planning a chapter needs OPENROUTER_API_KEY (or another model key)")
        return 1
    plan = planner.plan_chapter(args.subject, args.audience, llm, language=args.language)
    for lesson in plan["lessons"]:
        needs = ", ".join(str(p) for p in lesson["prerequisites"]) or "—"
        print(f"{lesson['order']:2d}. {lesson['title']}  [{lesson['minutes']} min, {lesson['level']}, after: {needs}]\n"
              f"      {lesson['idea']}")
    print(f"{len(plan['lessons'])} lessons, about {plan['minutes_total']} minutes")
    if args.output:
        Path(args.output).write_text(json.dumps(planner.to_briefs(plan), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"briefs written to {args.output} — generate them with: lessonforge harness {args.output}")
    return 0


def _stats(args) -> int:
    from .harness import analytics
    tz = -(time.altzone if time.daylight and time.localtime().tm_isdst > 0 else time.timezone) // 60
    print(analytics.format_stats(analytics.stats(days=args.days, tz_minutes=tz, include_tests=args.tests,
                                                 outside_server=True)))
    return 0


def _feedback(args) -> int:
    from .harness import feedback
    if args.job:
        summary = feedback.summarize(args.job)
        print(f"{summary['title']} — {summary['count']} review(s)")
    else:
        everything = feedback.summarize_all()
        print(f"{everything['reviews']} review(s) across {len(everything['lessons'])} lesson(s)")
        for row in everything["lessons"]:
            print(f"  {row['job_id']}  {row['count']:3d}  overall {row['overall']}  understood {row['understood']}  "
                  f"sync {row['sync']}  visuals {row['visuals']}  {row['title']}")
        summary = everything["all"]
    for qid, r in summary["ratings"].items():
        if r["n"]:
            print(f"  {r['mean']:.2f} / 5  (n={r['n']})  {r['prompt']}")
    for signal in summary.get("signals", []):
        print(f"  ! [{signal['area']}] {signal['message']}")
    if args.json:
        print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0


def _publish(args) -> int:
    """Finished lessons → Cloudflare R2, for the viewer site on Render (docs/DEPLOY_RENDER_VIEWER.md)."""
    from . import cloud
    if not args.jobs and not args.all:
        print("name the lessons to publish (job ids), or --all for every finished lesson")
        return 2
    if not cloud.configured() and not args.dry_run:
        print("Cloudflare R2 is not set up: " + ", ".join(cloud.missing_r2()) + " missing in .env "
              f"(or set {cloud.ENV_DIR} to a folder for a trial on this machine).")
        return 2
    from .harness import publish
    report = publish.publish(args.jobs, everything=args.all, dry_run=args.dry_run)
    for job_id, why in report["skipped"].items():
        print(f"  skipped {job_id}: {why}")
    where = cloud.describe()["objects"] or "nowhere (dry run without R2)"
    verb = "would publish" if args.dry_run else "published"
    print(f"{verb} {len(report['published'])} lesson(s) to {where}: {report['sent']} sent "
          f"({report['bytes'] / 1e6:.1f} MB), {report['unchanged']} already there"
          + (f", {len(report['removed'])} taken off the site" if report["removed"] else ""))
    return 1 if args.jobs and report["skipped"] else 0


def _spend(args) -> int:
    from . import spend
    if args.json:
        print(json.dumps(spend.summary(), indent=2))
    else:
        print(spend.format_summary())
    return 0


def _budget(args) -> int:
    """Show, set (``20``) or raise (``+10``) the cap. Applies to a running server's next metered call."""
    import re
    from . import spend
    before = spend.budget()
    if args.amount:
        text = args.amount.strip()
        try:
            value = float(text.lstrip("+"))
        except ValueError:
            print(f"not an amount: {args.amount!r} (use 20 to set, +10 to raise)")
            return 2
        amount = spend.set_budget((before or 0.0) + value if text.startswith("+") else value)
        # Keep .env in step, so a later restart or a tool without the workspace agrees.
        env = Path(".env")
        if env.is_file():
            lines = env.read_text(encoding="utf-8")
            line = f"OPENROUTER_BUDGET_USD={amount:g}"
            updated, n = re.subn(r"(?m)^OPENROUTER_BUDGET_USD=.*$", line, lines)
            env.write_text(updated if n else lines.rstrip("\n") + "\n" + line + "\n", encoding="utf-8")
        print(f"budget: ${before:.2f} -> ${amount:.2f}" if before is not None else f"budget: ${amount:.2f}")
    cap, spent = spend.budget(), spend.spent()
    if cap is None:
        print(f"no budget is set; spent ${spent:.2f}")
    else:
        print(f"spent ${spent:.2f} of ${cap:.2f}; ${cap - spent:.2f} left")
    return 0


def _storyflow(args) -> int:
    """Score a lesson's story against good YouTube explainers: a lesson.json, a captions .vtt, or plain text."""
    import json as _json
    import re as _re
    from pathlib import Path as _Path
    from .harness import storyflow
    path = _Path(args.file)
    text = path.read_text(encoding="utf-8")
    duration = None
    if path.suffix == ".json":
        sents = storyflow.lesson_sentences(_json.loads(text))
    elif path.suffix == ".vtt":
        cues = []
        for block in text.split("\n\n"):
            m = _re.search(r"([\d:.]+) --> ([\d:.]+)\n(.+)", block, _re.S)
            if m:
                secs = lambda t: sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.split(":"))))  # noqa: E731
                cues.append({"start": secs(m.group(1)), "end": secs(m.group(2)), "text": " ".join(m.group(3).split())})
        sents, duration = storyflow.sentences_from_cues(cues), (cues[-1]["end"] if cues else None)
    else:
        sents = storyflow.sentences_from_cues([{"start": 0, "end": 0, "text": text}])
    rep = storyflow.report(sents, duration)
    if args.json:
        print(_json.dumps(rep, indent=1, ensure_ascii=False))
        return 0
    print(f"{'measure':28s} {'this':>8} {'good explainers p10 / p50 / p90':>34}")
    for key, row in rep["measures"].items():
        flag = "" if row["where"] == "in range" else f"  <- {row['where']}"
        print(f"{key:28s} {row['value']:>8} {row['p10']:>12} {row['p50']:>9} {row['p90']:>9}{flag}")
    for line in rep["plan_aloud"]:
        print(f"plan said aloud: {line}")
    for line in rep["jumps"]:
        print(f"jumps: {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:  # keys and budget live in .env (gitignored); the server loads it too (LESSONFORGE_NO_DOTENV=1 opts out)
        from dotenv import load_dotenv

        from .env import dotenv_disabled
        if not dotenv_disabled():
            load_dotenv()
    except Exception:  # noqa: BLE001 - optional convenience
        pass
    parser = argparse.ArgumentParser(prog="lessonforge", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check the toolchain and configuration").set_defaults(fn=_doctor)
    sf = sub.add_parser("storyflow", help="score a lesson's story against good YouTube explainers (lesson.json, .vtt or .txt)")
    sf.add_argument("file")
    sf.add_argument("--json", action="store_true", help="print the full report as JSON")
    sf.set_defaults(fn=_storyflow)
    spend_cmd = sub.add_parser("spend", help="what the metered OpenRouter calls have cost so far")
    spend_cmd.add_argument("--json", action="store_true")
    spend_cmd.set_defaults(fn=_spend)
    fb = sub.add_parser("feedback", help="what student reviews say: one lesson, or all of them")
    fb.add_argument("job", nargs="?", help="lesson (job) id; omit for every reviewed lesson")
    fb.add_argument("--json", action="store_true")
    fb.set_defaults(fn=_feedback)

    bd = sub.add_parser("budget", help="show the spending cap, set it (20) or raise it (+10); no restart needed")
    bd.add_argument("amount", nargs="?", help="USD to set, or +USD to add to the current cap")
    bd.set_defaults(fn=_budget)

    pub = sub.add_parser("publish", help="send finished lessons to Cloudflare R2 for the viewer site (docs/DEPLOY_RENDER_VIEWER.md)")
    pub.add_argument("jobs", nargs="*", help="lesson (job) ids")
    pub.add_argument("--all", action="store_true", help="every finished lesson; lessons no longer here leave the site")
    pub.add_argument("--dry-run", action="store_true", help="say what would be sent, send nothing")
    pub.set_defaults(fn=_publish)

    st = sub.add_parser("stats", help="visitors, lessons, plays, reviews and spend")
    st.add_argument("--days", type=int, default=7, help="calendar days to cover; 0 for everything (default 7)")
    st.add_argument("--tests", action="store_true", help="count automated browsers too")
    st.set_defaults(fn=_stats)
    plan = sub.add_parser("plan", help="split a chapter into an ordered series of single-idea lessons")
    plan.add_argument("subject", help='e.g. "Trigonometry"')
    plan.add_argument("--audience", default="", help='e.g. "Class 10, government school"')
    plan.add_argument("--language", default="en-IN", help="en-IN | hinglish | hi-IN | te-IN | ta-IN")
    plan.add_argument("-o", "--output", default=None, help="write one generation brief per lesson to this JSON file")
    plan.set_defaults(fn=_plan)
    harness = sub.add_parser("harness", help="run one brief or a batch of briefs through the generation harness")
    harness.add_argument("briefs", help="JSON: one brief object or a list of briefs (intake fields)")
    harness.add_argument("-q", "--quality", choices=list("lmhpk"), default="m")
    harness.add_argument("--voice", default=None, help="speech spec; default: best configured voice for the language")
    harness.add_argument("--parallel", action="store_true", help="run briefs on the worker pool (cost per lesson approximate)")
    harness.add_argument("-o", "--output", default=None, help="results directory (default <workspace>/bulk_runs/<stamp>)")
    harness.set_defaults(fn=_harness)
    card = sub.add_parser("card", help="gather a topic's sources and write its teaching card (no video)")
    card.add_argument("brief", help="a brief JSON file (intake fields), or a topic in quotes")
    card.add_argument("--audience", default=None, help='who it is for, e.g. "Class 8 students" (the class picks the textbook)')
    card.add_argument("--goal", default=None, help="what they can do afterwards")
    card.add_argument("--language", default="en-IN")
    card.add_argument("--refresh", action="store_true", help="gather the sources again instead of using the library's pack")
    card.add_argument("-o", "--output", default=None, help="write the card here as markdown (and .json beside it)")
    card.set_defaults(fn=_card)
    script = sub.add_parser("script", help="make a video from a script you wrote (your words are spoken as written)")
    script.add_argument("script", help="text file: # starts a part, a blank line a paragraph, [brackets] direct the picture")
    script.add_argument("--check", action="store_true", help="only read it back (length, parts, language): nothing is spent")
    script.add_argument("--language", default=None, help="en-IN | hinglish | hi-IN | te-IN | ta-IN (default: read from the script)")
    script.add_argument("--audience", default="", help='e.g. "Class 8 students"')
    script.add_argument("--fix", action="store_true", help="let the reviewer rewrite sentences it finds wrong (default: keep every word)")
    script.add_argument("-q", "--quality", choices=list("lmhpk"), default="m")
    script.add_argument("--voice", default=None, help="speech spec; default: best configured voice for the language")
    script.add_argument("-o", "--output", default=None, help="results directory (default <workspace>/bulk_runs/<stamp>)")
    script.set_defaults(fn=_script)
    pk = sub.add_parser("pack", help="geometry videos from a teaching pack's units (no hand-writing: code checks every picture)")
    pk.add_argument("pack", help="the pack's Markdown: '# 3. Title' starts a unit, '## A — ...' a section")
    pk.add_argument("--unit", type=int, nargs="*", default=[], help="unit number(s); none lists the units")
    pk.add_argument("--check", action="store_true", help="write and check the lesson only (one model call or a few): nothing is filmed")
    pk.add_argument("--language", default="en-US")
    pk.add_argument("-q", "--quality", choices=list("lmhpk"), default="m")
    pk.add_argument("--voice", default=None, help="speech spec; default: best configured voice for the language")
    pk.add_argument("-o", "--output", default=None, help="results directory")
    pk.set_defaults(fn=_pack)
    kt = sub.add_parser("kits", help="the subject kits: list, describe, route a brief to them, or run the whole pipeline")
    kt.add_argument("what", choices=["list", "describe", "route", "run"])
    kt.add_argument("target", nargs="?", default=None, help="describe: a kit name; route: text or a file; run: the brief file")
    kt.add_argument("--classes", default=None, help="NCERT classes to keep, e.g. 7,8 (default: the brief's, else every class in scope, 1-12)")
    kt.add_argument("--subjects", default=None, help="subjects to keep, e.g. physics,chemistry")
    kt.add_argument("--lesson", default=None, help="run: a ready lesson JSON to check instead of writing one")
    kt.add_argument("--cap", type=float, default=None, help="run: the most dollars a model may cost; required whenever a model would be called")
    kt.add_argument("--rounds", type=int, default=2, help="run: most repair rounds")
    kt.add_argument("--preview", action="store_true", help="run: make the stills (free)")
    kt.add_argument("--film", action="store_true", help="run: film when no fault is left (local voice, free)")
    kt.add_argument("--voice", default=None)
    kt.add_argument("--json", action="store_true", help="route: print the plan as JSON")
    kt.set_defaults(fn=_kits)
    mc = sub.add_parser("mcp", help="the workbench as an MCP server: Claude checks, previews, edits and films lessons")
    mc.add_argument("--http", action="store_true", help="streamable HTTP instead of stdio")
    mc.add_argument("--host", default="127.0.0.1")
    mc.add_argument("--port", type=int, default=8765)
    mc.set_defaults(fn=_mcp)
    im = sub.add_parser("improve", help="Claude over the API improves a lesson in small checked edits, inside a spending cap")
    im.add_argument("lesson", help="a workbench lesson id, or a lesson JSON file to put on the workbench")
    im.add_argument("--cap", type=float, default=0.10, help="most dollars this lesson may cost (default 0.10)")
    im.add_argument("--rounds", type=int, default=3)
    im.add_argument("--model", choices=["haiku", "sonnet", "opus"], default="haiku")
    im.add_argument("--no-escalate", action="store_true", help="never move to a bigger model")
    im.add_argument("--no-look", action="store_true", help="send no contact sheet (cheaper, blind to layout)")
    im.add_argument("--film", action="store_true", help="film the best version afterwards (local voice, free)")
    im.set_defaults(fn=_improve)
    jf = sub.add_parser("judge-frames", help="a vision model judges one frame per spoken sentence of a lesson's newest film")
    jf.add_argument("lesson")
    jf.add_argument("--cap", type=float, default=0.03)
    jf.set_defaults(fn=_judge_frames)
    lp = sub.add_parser("loop", help="film, judge frames, edit, film again, for many lessons inside spending caps")
    lp.add_argument("lessons", nargs="+", help="workbench ids, lesson JSON files, or a pack .md with --unit")
    lp.add_argument("--unit", type=int, nargs="*", default=[])
    lp.add_argument("--cap", type=float, default=0.05, help="most dollars one lesson may cost")
    lp.add_argument("--batch-cap", type=float, default=1.0, help="most dollars the whole run may cost")
    lp.add_argument("--rounds", type=int, default=2, help="edit rounds per pass")
    lp.add_argument("--passes", type=int, default=1, help="film-judge-edit passes per lesson")
    lp.set_defaults(fn=_loop)
    fg = sub.add_parser("forge", help="videos from Lesson Forge plans (lesson-board /api/forge/v1): plan, build, review, film")
    fg.add_argument("topic", nargs="?", default="")
    fg.add_argument("--api", default=os.getenv("LESSON_FORGE_URL", ""), help="the lesson-board server, e.g. http://localhost:8000")
    fg.add_argument("--user", default=os.getenv("LESSON_FORGE_USER", ""), help="a learner id there (LESSON_FORGE_TOKEN for its token)")
    fg.add_argument("--level", default="Class 8")
    fg.add_argument("--language", default="en")
    fg.add_argument("--goal", default="")
    fg.add_argument("--depth", default="short", choices=["short", "standard", "deep"])
    fg.add_argument("--plan", default=None, help="a plan.json kept from an earlier run (no new plan is paid for)")
    fg.add_argument("--lectures", type=int, nargs="*", default=None, help="which lectures to make (default: all)")
    fg.add_argument("--save", default=None, help="folder for plan.json, built_N.json and results (built lectures there are reused)")
    fg.add_argument("--plan-only", action="store_true", help="plan and build, make nothing")
    fg.add_argument("--check", action="store_true", help="stop each lesson after its script review: read lesson.json first")
    fg.add_argument("--words", choices=["forge", "writer"], default="forge",
                    help="forge: Forge builds each part and its words are reviewed and filmed; "
                         "writer: Forge's plan is the brief and the script writer here writes for video")
    fg.add_argument("--voice", default=None)
    fg.add_argument("-q", "--quality", choices=list("lmhpk"), default="m")
    fg.set_defaults(fn=_forge)

    serve = sub.add_parser("serve", help="run the engine server and Studio UI")
    serve.add_argument("--host", default=os.getenv("LAB_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.getenv("LAB_PORT", "5000")))
    serve.set_defaults(fn=_serve)

    lesson = sub.add_parser("lesson", help="audio-first long-form lessons")
    lesson.add_argument("action", choices=["build", "validate", "audio", "render", "assemble", "check", "mend", "to-board"])
    lesson.add_argument("dir", help="lesson directory (contains lesson.json)")
    lesson.add_argument("--voice", default="silent",
                        help="silent | kokoro[:voice@speed] | gtts[:lang] | gemini:flash|lite/Voice[|instructions] "
                             "| engine:provider/locale/speaker")
    lesson.add_argument("--granularity", choices=["beat", "sentence"], default="beat",
                        help="synthesize whole beats (default) or one sentence at a time")
    lesson.add_argument("--target-seconds", type=float, default=None,
                        help="aim for this length; refused if it needs more than ±10%% retiming")
    lesson.add_argument("-q", "--quality", choices=list("lmhpk"), default="h")
    lesson.add_argument("--fps", type=int, default=30)
    lesson.add_argument("--jobs", type=int, default=4, help="chapters rendered in parallel")
    lesson.add_argument("--only", type=int, nargs="*", help="render only these chapter ids")
    lesson.add_argument("--renderer", choices=["manim", "ts"], default=None,
                        help="chapter renderer: manim (default) or ts (TypeScript/Revideo)")
    lesson.add_argument("--chapter", type=int, default=None, help="to-board: a single chapter")
    lesson.add_argument("--style", default="3blue1brown", help="to-board: engine style profile")
    lesson.add_argument("-o", "--output", default=None)
    lesson.set_defaults(fn=_lesson)

    board = sub.add_parser("board", help="engine storyboards (the IR)")
    board.add_argument("action", choices=["transpile", "render", "to-lesson"])
    board.add_argument("board", help="storyboard JSON")
    board.add_argument("dir", nargs="?", help="to-lesson: output lesson directory")
    board.add_argument("--language", default="en-IN")
    board.add_argument("--speaker", default="shubh")
    board.add_argument("--persona", default="en", help="en | hybrid | native (on-screen/narration language policy)")
    board.add_argument("--tts-provider", default="sarvam")
    board.add_argument("--style", default="")
    board.add_argument("-q", "--quality", choices=list("lmhk"), default="l")
    board.add_argument("--mute", action="store_true", help="render: no speech synthesis (TTS_MUTE=1)")
    board.add_argument("-o", "--output", default=None)
    board.set_defaults(fn=_board)

    args = parser.parse_args(argv)
    if getattr(args, "action", None) == "to-lesson" and not args.dir:
        parser.error("board to-lesson needs an output directory")
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
