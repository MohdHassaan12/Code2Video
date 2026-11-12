"""A drawing is drawn WITH the words: a part comes when the voice reaches it (no render, no model).

A reference lecture beside ours, 2026-10-12 (docs/research/approaches/12): the lecturer's board holds only the triangle
for 53 seconds and each line of the proof comes when it is spoken of; our drawing drew itself in five seconds and held
the whole proof before a word of it. ``harness/sequence.with_words`` plans when each THING of a drawing is drawn;
the renderer holds a part back until its step (tests/integration/test_picture_painted.py films it).
"""
import json

from lessonforge.harness import sequence
from lessonforge.longform import runtime


def part(n, kind, points=None, box=None, length=None, text="", stroke="#000000", fill="", closed=False, dashed=False):
    points = points or []
    if box is None:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        box = [min(xs), min(ys), max(xs), max(ys)]
    if length is None:
        length = sum(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5 for a, b in zip(points, points[1:])) if points else box[2] - box[0]
    return {"n": n, "kind": kind, "points": points, "box": box, "length": round(length, 4), "text": text, "stroke": stroke if kind != "text" else "",
            "fill": fill, "closed": closed, "dashed": dashed, "dash": 0.02 if dashed else 0, "width": 0.003, "opacity": 1}


def line(a, b, steps=24):
    return [[a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps] for i in range(steps + 1)]


def proof():
    """A triangle ABC, the angle marks at B and at A, a dashed line through A with an arrowhead, and the mark of the
    angle between that line and a side: the parts of the lesson's own drawing, in the order an SVG writes them."""
    triangle = line((.2, .9), (.45, .3)) + line((.45, .3), (.9, .9)) + line((.9, .9), (.2, .9))
    return [
        part(1, "stroke", triangle, stroke="#000099", closed=True),
        part(2, "stroke", line((.1, .3), (.9, .3)), stroke="#666666", dashed=True),
        part(3, "fill", [[.70, .29], [.72, .30], [.70, .31], [.70, .29]], stroke="#994c00", fill="#994c00", closed=True),      # its arrowhead
        part(4, "stroke", [[.245, .8], [.27, .82], [.28, .9]], length=.08),                                                 # the arc at B
        part(5, "text", box=[.29, .80, .31, .84], text="2"),
        part(6, "stroke", [[.37, .3], [.375, .36], [.425, .36]], length=.09),                                                # between line and side
        part(7, "text", box=[.35, .35, .37, .39], text="4"),
        part(8, "fill", [[.17, .93], [.2, .93], [.2, .97], [.17, .97], [.17, .93]], fill="#ffffff", stroke="", closed=True),  # the plate under B
        part(9, "text", box=[.175, .935, .195, .965], text=""),
    ]


def test_a_drawings_parts_are_the_things_a_teacher_draws_in_one_go():
    things = sequence.things_of(proof())
    numbers = [sorted(t["numbers"]) for t in things]
    # the triangle with its name letter (and the plate under it); the line with its arrowhead; each angle's arc with its number
    assert numbers == [[1, 8, 9], [2, 3], [4, 5], [6, 7]]
    assert [t["big"] for t in things] == [True, True, False, False]
    said = [sequence._described(t) for t in things]
    assert "closed outline" in said[0] and "dashed line" in said[1] and "arrowhead" in said[1]
    assert "“2”" in said[2] and "“4”" in said[3]


def test_a_row_of_like_marks_belongs_to_its_line_and_a_line_cut_by_its_arrowhead_is_one_thing():
    mirror = part(1, "stroke", line((.1, .8), (.9, .8)))
    hatching = [part(2 + i, "stroke", [[.15 + .1 * i, .8], [.13 + .1 * i, .84]], length=.045, stroke="#999999") for i in range(7)]
    ray = [part(10, "stroke", line((.2, .2), (.35, .5), steps=8), stroke="#000099"),
           part(11, "fill", [[.34, .49], [.36, .5], [.35, .52], [.34, .49]], length=.06, stroke="#000099", fill="#000099", closed=True),
           part(12, "stroke", line((.35, .5), (.5, .8), steps=8), stroke="#000099")]
    things = sequence.things_of([mirror] + hatching + ray)
    assert [sorted(t["numbers"]) for t in things] == [list(range(1, 9)), [10, 11, 12]]


def test_the_plan_is_made_to_agree_with_the_drawing():
    things = sequence.things_of(proof())
    # as one plan had it: the triangle held back to the fifth step, the angle between line and side BEFORE the line
    settled = sequence.settle(things, {1: 5, 2: 7, 3: 2, 4: 3})
    assert settled[1] == 1                       # the first big thing is what the lesson starts from
    assert settled[4] == 7                       # a mark is not drawn before the line it is drawn on
    assert settled[3] == 2                       # ... and a mark that rests only on what is there keeps its step
    # a thing the plan left out goes with the thing nearest to it; what shows an answer waits for the answer
    assert sequence.settle(things, {1: 1, 2: 6, 3: 1})[4] == 6
    assert sequence.settle(things, {1: 1, 2: 4, 3: 2, 4: 5}, answers={3: 9})[3] == 9
    # a card is never empty: with nothing planned for the first step, what comes first is there at the start
    loose = [t for t in things if not t["big"]]
    assert min(sequence.settle(loose, {1: 4, 2: 6}).values()) == 1


def test_three_lines_that_meet_in_a_point_do_not_wait_for_each_other():
    mirror = {"main": part(1, "stroke", line((.1, .8), (.9, .8))), "marks": [], "labels": [], "big": True}
    normal = {"main": part(2, "stroke", line((.5, .8), (.5, .2)), dashed=True), "marks": [], "labels": [], "big": True}
    dot = {"main": part(3, "fill", [[.495, .795], [.505, .795], [.505, .805], [.495, .805], [.495, .795]], fill="#000000", closed=True),
           "marks": [], "labels": [], "big": False}
    assert sequence._rests_on(dot, mirror) and not sequence._rests_on(dot, normal)       # on the mirror; at the normal's END
    assert sequence._rests_on(normal, mirror) and not sequence._rests_on(mirror, normal)


def lesson(folder):
    figure = {"kind": "picture", "file": str(folder / "whole.png")}
    step = lambda say, show, **more: {"say": say, "show": show, "kind": "point", **more}                  # noqa: E731
    return {"title": "Angles", "chapters": [
        {"id": 1, "beats": [{"id": "01", "narration": "A triangle has fifty degrees at B. What could angle A be?", "figure": dict(figure),
                             "steps": [step("A triangle has", "B = 50 degrees", focus="2"), step("What could angle", "Angle A?")]}]},
        {"id": 2, "beats": [{"id": "02", "narration": "Draw a line through A, parallel to the base. The angle beside it equals B.", "figure": dict(figure),
                             "steps": [step("Draw a line", "Line through A"), step("The angle beside", "Equals B", focus="4")]},
                            {"id": "03", "narration": "Now try it on paper.", "steps": [step("Now try", "Your turn")]}]}]}


def the_drawing(tmp_path, monkeypatch):
    from PIL import Image
    folder = tmp_path / "a_triangle-0123456789"
    folder.mkdir()
    Image.new("RGB", (400, 300), "white").save(folder / "whole.png")
    made = {"version": sequence.VERSION, "of": "x", "width": 1280, "height": 960, "parts": proof()}
    monkeypatch.setattr(sequence, "sequence", lambda where, log=print: made)
    monkeypatch.setenv("HARNESS_DRAW_WITH_WORDS", "1")           # off in every other test (tests/conftest.py): a stub answers here
    return folder


def test_the_steps_are_given_the_parts_they_bring_and_the_plan_reads_our_tags_not_the_drawings_numbers(tmp_path, monkeypatch):
    folder = the_drawing(tmp_path, monkeypatch)
    made, asked = lesson(folder), []

    def look(prompt, system, image):
        asked.append(prompt)
        # the line of the proof at S3, the angle beside it too early (S2: before the line it is drawn on)
        return {"questions": [{"asked_at": "S2", "asks": "what angle A is", "shown_by": [], "answered_at": "S4"}],
                "things": {"#1": ["the triangle ABC", "S1"], "#2": ["the line through A", "S3"], "#3": ["the angle at B", "S1"],
                           "#4": ["the angle beside the line", "S2"]}}
    summary = sequence.with_words(made, look=look, log=lambda *a: None)
    assert summary == {"drawings": 1, "planned": 1, "steps": 1}
    steps = {(b["id"], i): s.get("draw") for c in made["chapters"] for b in c["beats"] for i, s in enumerate(b["steps"])}
    # the line, its arrowhead, and the mark that needs the line come at "Line through A"; nothing else is held back
    assert steps == {("01", 0): None, ("01", 1): None, ("02", 0): [2, 3, 6, 7], ("02", 1): None, ("03", 0): None}
    # every beat that shows the drawing says which taking-apart of it the numbers are of (and so stays ONE figure)
    marks = [b["figure"].get("planned") for c in made["chapters"] for b in c["beats"] if b.get("figure")]
    assert marks == [f"{sequence.VERSION}:x:"] * 2
    # the planner is shown OUR tags with a hash sign (a drawing prints numbers of its own) and which label a step marks
    assert "#3: " in asked[0] and "S3, when the voice says “Draw a line”" in asked[0] and "(it marks the printed label “2”)" in asked[0]
    # asked once: a lesson whose steps already bring parts is left as it is
    assert sequence.with_words(made, look=look, log=lambda *a: None)["planned"] == 0 and len(asked) == 1


def test_a_cheap_model_is_asked_several_times_and_each_thing_comes_at_the_middle_answer(tmp_path, monkeypatch):
    """The owner, 2026-10-12: "use cheap models and improve the harness". One answer of a small model held a ray back to
    the end, another brought it at the start; three answers put together by code (the MEDIAN step for each thing, an
    answer held back only when most say so) cost half a cent against three for the large model's one."""
    from lessonforge.harness import vision_review
    folder = the_drawing(tmp_path, monkeypatch)
    made, built = lesson(folder), []
    answers = [{"things": {"#1": ["the triangle", "S1"], "#2": ["the line through A", "S3"], "#3": ["the angle at B", "S1"], "#4": ["the angle beside", "S3"]},
                "questions": [{"asked_at": "S1", "asks": "what angle A is", "shown_by": ["#3"], "answered_at": "S4"}]},     # only this look holds #3 back
               {"things": {"#1": ["the triangle", "S1"], "#2": ["the line", "S4"], "#3": ["the angle at B", "S1"], "#4": ["the angle beside", "S4"]}},  # late
               {"things": {"#1": ["the triangle", "S1"], "#2": ["the line", "S3"], "#3": ["the angle at B", "S1"], "#4": ["the angle beside", "S3"]}}]

    def judge(models=(), temperature=0.0, max_tokens=0):
        built.append((models, temperature))
        return lambda prompt, system, image, n=len(built) - 1: answers[n]
    monkeypatch.setattr(vision_review, "default_judge", judge)
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    said = []
    summary = sequence.with_words(made, log=said.append)
    assert summary["planned"] == 1 and [t for _, t in built] == [0.0, 0.3, 0.3] and built[0][0] == (sequence.PLAN_MODEL,)
    steps = {(b["id"], i): s.get("draw") for c in made["chapters"] for b in c["beats"] for i, s in enumerate(b["steps"])}
    # the line and the mark on it at S3 (two of three), not at S4; the angle at B is there from the start (one look in three held it back)
    assert steps == {("01", 0): None, ("01", 1): None, ("02", 0): [2, 3, 6, 7], ("02", 1): None, ("03", 0): None}
    assert any("3 looks at the drawing: they agree on 2 of 4 thing(s)" in line for line in said)
    # one look that names too little of the drawing is one look less, not no plan
    answers[1] = {"things": {"#1": ["the triangle", "S1"]}}
    again, built[:] = lesson(folder), []
    assert sequence.with_words(again, log=lambda *a: None)["planned"] == 1
    monkeypatch.setenv("HARNESS_PLAN_VOTES", "1")                           # ... and the number of looks can be set
    once, built[:] = lesson(folder), []
    sequence.with_words(once, log=lambda *a: None)
    assert len(built) == 1


def test_printed_words_that_tell_a_questions_answer_wait_for_the_answer():
    """"F₁ (Lower)" stood beside the first of two cases while the lesson asked on which of them the reading is lower
    (Friction, 2026-10-12). Code finds the questions a lesson stops on and their right answers; one small question is
    asked about every printed word (one decision per word: asked for a list, the small model answered one time in three);
    words the voice has already spoken were taught, not given away."""
    beats = [{"id": "03", "narration": "A brick is pulled over a wooden floor and then over sand paper.", "steps": [{"show": "Brick"}, {"show": "Two floors"}]},
             {"id": "04", "narration": "On which surface is the reading bigger?", "thinking_pause_seconds": 5,
              "quiz": {"question": "Which surface shows the bigger reading?", "options": ["Wooden floor", "Sand paper"], "answer_index": 1}, "steps": [{"show": "Bigger where?"}]},
             {"id": "05", "narration": "Yes, on sand paper. Is the floor really smooth?", "steps": [{"show": "Sand paper"}, {"show": "Smooth?"}]},
             {"id": "06", "narration": "It has tiny bumps.", "steps": [{"show": "Bumps"}]}]
    at = {1: ("03", 0), 2: ("03", 1), 3: ("04", 0), 4: ("05", 0), 5: ("05", 1), 6: ("06", 0)}
    asked = sequence.asked_over(beats, at)
    assert [(q["asks"], q["answer"], q["answered_at"]) for q in asked] == [("Which surface shows the bigger reading?", "Sand paper", 4)]
    assert "sand" in asked[0]["heard"] and "bumps" not in asked[0]["heard"]         # beat 05 ends on a question but does not STOP for it
    label = lambda n, words: {"main": {"n": n, "kind": "text", "text": words, "box": [0, 0, .1, .1]}, "marks": [], "labels": [], "big": False, "numbers": [n]}     # noqa: E731
    line = {"main": part(1, "stroke", line_ := [[.1, .8], [.9, .8]]), "marks": [], "labels": [{"n": 9, "kind": "text", "text": "Wooden floor"}], "big": True, "numbers": [1, 9]}
    things = [line, label(2, "Sand paper"), label(3, "F₁ (Lower)"), label(4, "F₂ (Higher)")]
    seen, said = [], []

    def tells(prompt, system):
        seen.append((prompt, system))
        return {"q1": {"#1": "names", "#2": "tells", "#3": "tells", "#4": "tells", "#7": "tells"}}
    held = sequence.printed_tells(things, asked, tells=tells, log=said.append)
    assert held == {3: 4, 4: 4}                           # "Sand paper" was spoken before the question: taught, not told; #7 is no thing
    assert seen[0][1] is sequence.TELLS_SYSTEM and "(right answer: “Sand paper”)" in seen[0][0] and "#3: “F₁ (Lower)”" in seen[0][0]
    assert "“F₁ (Lower)” until S4" in said[0]
    assert sequence.printed_tells(things, asked, tells=lambda *a: {"q1": ["#3"]}) == {3: 4}          # a list of the telling tags is read too
    assert sequence.printed_tells(things, asked, tells=None) == {} and sequence.printed_tells(things, [], tells=tells) == {}

    def nobody(prompt, system):
        raise RuntimeError("no model")
    assert sequence.printed_tells(things, asked, tells=nobody, log=lambda *a: None) == {}             # no answer, nothing held


def test_a_printed_name_that_stands_alone_waits_for_the_thing_it_stands_beside():
    # one plan brought the words "Reflected ray" eight steps before the ray (2026-10-12)
    ray = {"main": part(1, "stroke", line((.5, .8), (.9, .3))), "marks": [], "labels": [], "big": True, "numbers": [1]}
    mirror = {"main": part(2, "stroke", line((.1, .8), (.9, .8))), "marks": [], "labels": [], "big": True, "numbers": [2]}
    name = {"main": {"n": 3, "kind": "text", "text": "Reflected ray", "box": [.86, .22, .98, .27]}, "marks": [], "labels": [], "big": False, "numbers": [3]}
    far = {"main": {"n": 4, "kind": "text", "text": "Figure 1", "box": [.02, .02, .12, .06]}, "marks": [], "labels": [], "big": False, "numbers": [4]}
    settled = sequence.settle([mirror, ray, name, far], {1: 1, 2: 6, 3: 2, 4: 2})
    assert settled[3] == 6 and settled[4] == 2             # beside the ray: with it; a caption far from everything keeps its step
    assert sequence.settle([mirror, ray, name, far], {1: 1, 2: 3, 3: 5, 4: 2})[3] == 5      # a name may come LATER than its thing


def test_no_plan_is_no_change(tmp_path, monkeypatch):
    folder = the_drawing(tmp_path, monkeypatch)
    for answer in (None, {}, {"things": {"#1": ["the triangle", "S1"]}},                       # nothing, or too little of it
                   {"things": {f"#{n}": ["a thing", "S1"] for n in range(1, 5)}}):            # the words begin with all of it
        made = lesson(folder)
        was = json.dumps(made, sort_keys=True)
        assert sequence.with_words(made, look=lambda *a: answer, log=lambda *a: None)["planned"] == 0
        assert json.dumps(made, sort_keys=True) == was

    def fails(*a):
        raise RuntimeError("no model")
    made = lesson(folder)
    assert sequence.with_words(made, look=fails, log=lambda *a: None)["planned"] == 0
    monkeypatch.setenv("HARNESS_DRAW_WITH_WORDS", "0")
    assert sequence.with_words(lesson(folder), look=fails, log=lambda *a: None) == {"drawings": 0, "planned": 0, "steps": 0}


def test_steps_written_again_keep_the_parts_they_brought(tmp_path):
    folder = tmp_path / "d"
    was = lesson(folder)
    was["chapters"][1]["beats"][0]["steps"][0]["draw"] = [2, 3]
    was["chapters"][1]["beats"][0]["steps"][1]["draw"] = [6, 7]
    now = json.loads(json.dumps(was))
    now["chapters"][1]["beats"][0]["steps"] = [{"say": "Draw a line", "show": "One parallel line", "kind": "point"}]     # a repair's rewrite
    assert sequence.keep_draws(now, was) == 2
    assert now["chapters"][1]["beats"][0]["steps"][0]["draw"] == [2, 3, 6, 7]
    assert sequence.keep_draws(now, was) == 0                                              # nothing left to give back


def test_a_chapter_knows_what_the_chapters_before_it_drew(tmp_path):
    """A chapter is a render of its own: what is held back when a beat begins is worked out from the whole lesson."""
    made = lesson(tmp_path / "d")
    made["chapters"][0]["beats"][0]["steps"][1]["draw"] = [4, 5]
    made["chapters"][1]["beats"][0]["steps"][0]["draw"] = [2, 3]
    made["chapters"][1]["beats"][0]["steps"][1]["draw"] = [6, 7]
    scene = runtime.GuidedChapter.__new__(runtime.GuidedChapter)
    scene.lesson = made
    first, second = made["chapters"][0]["beats"][0], made["chapters"][1]["beats"][0]
    assert scene._drawn_later(first["figure"], first) == {2, 3, 4, 5, 6, 7}
    assert scene._drawn_later(second["figure"], second) == {2, 3, 6, 7}           # the arc at B was drawn in chapter one
    assert scene._drawn_later({"kind": "picture", "file": "/another/whole.png"}, second) == set()
    assert scene._drawn_later({"kind": "diagram", "manifest": "/m.json"}, second) == set()


def test_a_shape_is_what_a_viewer_sees_of_it_when_it_is_drawn_through_a_clip_path():
    """A typesetter draws a shaded sector as a whole disc clipped by the triangle it sits in. Drawn by their own outlines,
    three corners of a triangle were three discs lying over it (a lesson of 2026-10-12)."""
    import math
    disc = [[.5 + .2 * math.cos(2 * math.pi * i / 60), .5 + .2 * math.sin(2 * math.pi * i / 60)] for i in range(61)]
    # the clip as a browser gives it: a point every few pixels along each edge, rounded, so the straight runs wobble
    corner = [(.5, .5), (.9, .5), (.9, .9)]
    edge = lambda a, b: [[round(a[0] + (b[0] - a[0]) * i / 20 + (1e-4 if i % 2 else 0), 4), round(a[1] + (b[1] - a[1]) * i / 20, 4)] for i in range(20)]   # noqa: E731
    clip = edge(corner[0], corner[1]) + edge(corner[1], corner[2]) + edge(corner[2], corner[0])
    assert len(sequence._corners(clip)) <= 4 and sequence._convex(sequence._corners(clip))
    wedge = {"points": disc, "closed": True, "box": [.3, .3, .7, .7], "length": 1.26, "fill": "#000099", "stroke": "", "clips": [clip]}
    free = {"points": disc, "closed": True, "box": [.3, .3, .7, .7], "length": 1.26, "fill": "#000099", "stroke": ""}
    shapes, cannot = sequence.clipped([wedge, free])
    assert cannot == 0 and shapes[1] is free
    x0, y0, x1, y1 = shapes[0]["box"]
    assert x0 >= .499 and y0 >= .499 and x1 <= .701 and y1 <= .701 and shapes[0]["length"] < .9      # an eighth of the disc
    # what this cannot follow is counted, so the drawing is not left standing as pen-work
    line = {"points": [[.1, .1], [.9, .9]], "closed": False, "box": [.1, .1, .9, .9], "length": 1.13, "fill": "", "stroke": "#000000", "clips": [clip]}
    notch = {**wedge, "clips": [[[.4, .4], [.8, .4], [.6, .5], [.8, .8], [.4, .8]]]}                # a clip outline that is not convex
    assert sequence.clipped([line])[1] == 1 and sequence.clipped([notch])[1] == 1 and sequence.clipped([{**wedge, "clips": ["many"]}])[1] == 1


def test_a_drawing_a_pen_cannot_follow_is_drawn_at_once(tmp_path, monkeypatch):
    folder = the_drawing(tmp_path, monkeypatch)
    made = {"version": sequence.VERSION, "of": "x", "width": 1280, "height": 960, "parts": proof(), "faithful": False}
    monkeypatch.setattr(sequence, "sequence", lambda where, log=print: made)
    said = []
    lesson_made = lesson(folder)
    assert sequence.with_words(lesson_made, look=lambda *a: 1 / 0, log=said.append)["planned"] == 0      # nobody is asked
    assert any("a pen cannot follow" in line for line in said)


def test_a_wash_is_filled_as_pale_as_it_is_drawn():
    from lessonforge.longform import figures
    assert figures.PictureFigure._fill_opacity({"fill_opacity": 0.3, "opacity": 1.0}) == 0.3       # a pale fill under a solid edge
    assert figures.PictureFigure._fill_opacity({"opacity": 0.5}) == 0.5                            # a sequence kept before today
    assert figures.PictureFigure._fill_opacity({}) == 1.0


def test_a_plan_made_for_another_taking_apart_of_the_drawing_holds_nothing_back(tmp_path):
    """A plan names parts by their numbers. When the drawing is taken apart again by another rule the numbers are other
    parts: the wrong lines would wait for the wrong words, silently. Then the drawing is drawn at once, as before."""
    from PIL import Image
    from lessonforge.longform import figures
    file = tmp_path / "whole.png"
    Image.new("RGB", (400, 300), "white").save(file)
    made = {"version": "sequence-x", "of": "abc", "named": "n1", "parts": proof()}
    fig = figures.PictureFigure(file, sequence=made)
    assert fig.sequence_id == sequence.identity(made) == "sequence-x:abc:n1"
    assert fig.hold_back([2, 3], planned="sequence-w:abc:n1") is False and not fig._staged          # another taking-apart
    assert fig.hold_back([], planned=fig.sequence_id) is False                                     # nothing to hold back
    assert fig.hold_back([2, 3], planned=fig.sequence_id) is True and fig._hidden == {2, 3}
    assert figures.PictureFigure(file, sequence=made).hold_back([2, 3]) is True                    # a plan made before the mark existed


def test_a_code_drawn_figure_is_not_asked_to_hold_anything_back():
    """The renderer asks a figure whether it can be drawn with the words by the NAME of a method. The first name chosen
    was one a code-drawn ``Figure`` already has (``stage``: "this group of parts is drawn next"), so every right triangle
    was handed a set of numbers as a group of parts to draw, and its chapter stopped (an integration test caught it)."""
    from lessonforge.longform import figures
    drawn = figures.build({"kind": "right_triangle", "a": 3, "b": 4, "unknown": "c"})
    assert drawn is not None and not hasattr(drawn, "hold_back") and not hasattr(drawn, "paint")
    # ... nor to take a hand's marks (harness/annotate.py): the renderer asks for those by name too
    assert not any(hasattr(drawn, name) for name in ("annotate", "prepare_marks", "clear_gesture", "sweep", "pen_seconds"))
    assert all(isinstance(how, str) for how, _ in drawn.build)
