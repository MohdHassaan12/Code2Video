"""The stage frame's own small pieces (no render): what a new lesson is laid out by since 2026-10-10 (longform/look.py).

Whole lessons rendered in it are in tests/integration/test_harness_job.py.
"""
from lessonforge.longform import runtime


def test_a_long_line_of_working_is_cut_before_its_first_arrow_or_relation():
    # the first lesson made end to end in this frame: a word equation fitted to the column on ONE line was unreadable
    equation = r"\text{carbon dioxide}+\text{water}\xrightarrow{\text{sunlight, chlorophyll}}\text{glucose}+\text{oxygen}"
    assert runtime.relation_rows(equation) == [r"\text{carbon dioxide}+\text{water}",
                                               r"\xrightarrow{\text{sunlight, chlorophyll}}\text{glucose}+\text{oxygen}"]
    assert runtime.relation_rows(r"\text{distance}=\text{speed}\times\text{time}") == [r"\text{distance}", r"=\text{speed}\times\text{time}"]
    assert runtime.relation_rows(r"\text{reactants}\rightarrow\text{products}") == [r"\text{reactants}", r"\rightarrow\text{products}"]
    assert runtime.relation_rows(r"\frac{a=b}{c}+\frac{d}{e}") == []          # a relation inside braces is not a place to cut
    assert runtime.relation_rows(r"\begin{aligned} a&=b \\ c&=d \end{aligned}") == []
    assert runtime.relation_rows("x") == [] and runtime.relation_rows("") == []


def lesson():
    drawing = {"kind": "diagram", "manifest": "/somewhere/manifest.json"}
    step = lambda kind, show: {"kind": kind, "show": show, "say": "x"}                      # noqa: E731
    return {"chapters": [
        {"id": 1, "role": "activate", "beats": [{"id": "01", "figure": dict(drawing), "steps": [step("point", "Green leaf")]}]},
        {"id": 2, "role": "model", "beats": [{"id": "02", "figure": dict(drawing), "steps": [step("math", r"a+b\rightarrow c")]},
                                              {"id": "03", "figure": dict(drawing), "steps": [step("point", "Oxygen leaves")]}]},
        {"id": 3, "role": "practice", "beats": [{"id": "04", "figure": dict(drawing), "steps": [step("key", "Leaves A to D")]},
                                                 {"id": "05", "figure": None, "steps": [step("point", "Your turn")]}]}]}


def chapter_scene(made):
    scene = runtime.GuidedChapter.__new__(runtime.GuidedChapter)        # the two rules read the lesson and nothing else
    scene.lesson = made
    return scene


def test_the_pictures_place_is_one_for_the_run_and_the_words_are_each_chapters_own():
    made = lesson()
    scene = chapter_scene(made)
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    # one formula anywhere in the run decides where the picture stands, for every beat that shows it ...
    assert all(scene._run_board(beats[b]) for b in ("01", "02", "03", "04", "05"))
    # ... but only the chapter that has the formula shows its words as a column of working
    assert [scene._working(beats[b]) for b in ("01", "02", "03", "04")] == [False, True, True, False]


def test_what_a_focus_does_is_asked_for_only_when_its_words_are_spoken():
    """A built-up drawing starts the beads on a part's arrows when it is asked for the focus: asked a step early, they ran
    along an arrow that was not drawn yet."""
    asked = []

    class Drawing:
        parts = {}

        def focus_animations(self, name):
            asked.append(name)
            return ["drawn in"]
    scene = chapter_scene(lesson())
    enter, extra = scene._entrance({"focus": "water", "kind": "point", "show": "Water rises"}, runtime.Text("Water rises"), Drawing(), None)
    assert asked == [] and len(extra) == 1 and isinstance(extra[0], runtime.Later)
    assert extra[0].make() == ["drawn in"] and asked == ["water"]
    # no focus, nothing to ask
    assert scene._entrance({"kind": "point", "show": "x"}, runtime.Text("x"), Drawing(), None)[1] == []


def test_working_stays_under_one_line_of_words_and_goes_on_to_a_new_screen_instead_of_being_shrunk():
    """A beat that works something out (``look``: ``working: pinned``): the formula lines stay, the words come one at a
    time above them. Until 2026-10-10 evening every line of both stood in one column of 30-point type, and a column
    that did not fit was shrunk as a whole."""
    scene = chapter_scene(lesson())
    block = lambda kind, height: {"kind": kind, "show": "x", "_mob": runtime.Rectangle(width=3.0, height=height)}      # noqa: E731
    steps = [block("point", .6), block("math", 1.2), block("math", 1.2), block("key", 1.2), block("math", 1.2),
             block("math", 1.2), block("math", 1.2), block("math", 1.2)]
    scene._pin(steps, 4.9, 6.6, (4.0, 0.0, 0))
    words = [s for s in steps if s["kind"] != "math"]
    working = [s for s in steps if s["kind"] == "math"]
    # nothing was made smaller: what does not fit goes on to a second screen
    assert [round(s["_mob"].height, 3) for s in steps] == [.6, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2]
    assert [s["_page"] for s in working] == [0, 0, 0, 1, 1, 1] and all(s["_pinned"] for s in working)
    assert not any(s["_pinned"] for s in words)
    # every line of words owns the SAME place, standing on the working, and each screen of working begins under it
    feet = {round(float(s["_mob"].get_bottom()[1]), 3) for s in words}
    assert len(feet) == 1
    first, second = working[0]["_mob"], working[3]["_mob"]
    assert round(float(first.get_top()[1]), 3) == round(float(second.get_top()[1]), 3) < min(feet)
    assert all(round(float(s["_mob"].get_left()[0]), 3) == round(4.0 - 4.9 / 2, 3) for s in steps)
    # no line of one screen reaches into the next line
    tops = [float(s["_mob"].get_top()[1]) for s in working[:3]]
    assert all(a - 1.2 > b for a, b in zip(tops, tops[1:]))
    # only a single line taller than all the room there is gets smaller
    tall = [block("point", .6), block("math", 9.0)]
    scene._pin(tall, 4.9, 6.6, (4.0, 0.0, 0))
    assert tall[1]["_mob"].height < 6.6 and tall[1]["_page"] == 0
    # a beat with working and no words at all: the working has the whole column
    alone = [block("math", 1.2), block("math", 1.2)]
    scene._pin(alone, 4.9, 6.6, (4.0, 0.0, 0))
    assert [s["_page"] for s in alone] == [0, 0] and round(float(alone[0]["_mob"].get_top()[1]), 3) == round((1.2 * 2 + .45) / 2, 3)


def test_a_strip_above_a_wide_picture_shows_one_line_at_a_time_even_in_a_chapter_that_works_something_out():
    """ "Why Water Pushes Up" (2026-10-12): a beat with no picture of its own, under a wide scene, in a chapter whose
    NEXT beat has a formula, had its three lines fitted into the strip as a column of 15-point type. A strip has room
    for one line, so its lines are there one at a time whatever the chapter works out elsewhere."""
    step = lambda kind, show: {"kind": kind, "show": show, "say": "x"}                      # noqa: E731
    made = {"chapters": [
        {"id": 6, "role": "practice", "beats": [{"id": "11", "figure": {"kind": "scene", "description": "a ball in water"},
                                                 "steps": [step("point", "The ball sinks")]}]},
        {"id": 7, "role": "practice", "beats": [
            {"id": "12", "figure": None, "steps": [step("point", "Three quick checks"), step("point", "Which force is larger?"),
                                                   step("key", "What equals upthrust?")]},
            {"id": "13", "figure": {"kind": "picture", "file": "/somewhere/whole.png"}, "steps": [step("math", "a=b")]}]}]}
    scene = chapter_scene(made)
    beat = made["chapters"][1]["beats"][0]
    assert scene._working(beat)                         # the chapter does work something out, on another picture

    class Wide:                                         # the scene the beat takes over, already in its place above
        _plan = {"mode": "top", "picture": (11.0, 4.6, (0.0, -1.2, 0)), "words": (13.3, 1.25, (0.0, 2.3, 0))}
    plan = scene._staged(beat["steps"], Wide(), beat)
    assert plan["caption"] and not plan["board"] and not plan["pinned"]
    assert min(min(runtime.type_points(s["_mob"])) for s in beat["steps"]) >= 44
    assert {tuple(round(float(v), 2) for v in s["_mob"].get_center()[:2]) for s in beat["steps"]} == {(0.0, 2.3)}


def test_a_line_of_working_grows_out_of_a_copy_and_is_never_padded():
    """``TransformFromCopy(last, line)`` transformed the LINE, and a Transform pads what it changes with copies of its own
    parts: a two-row formula ended holding three "Total distance" rows, one on another (speed and velocity, 2026-10-20)."""
    scene = chapter_scene(lesson())
    last = runtime.VGroup(runtime.MathTex("a"), runtime.MathTex("b"), runtime.MathTex("c"))
    line = runtime.VGroup(runtime.MathTex(r"\text{Total}"), runtime.MathTex("= 1 + 2"))
    enter, _ = scene._entrance({"kind": "math", "show": "x"}, line, None, last)
    assert isinstance(enter, runtime.ReplacementTransform) and enter.mobject is not line and enter.target_mobject is line
