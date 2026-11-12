"""Video-quality plan S3: an angle's number and a sum line appear where the voice says them (look key ``values``).

Pure hint-plan tests: no render, no voice. ``values="named"`` (every lesson made before 2026-11-09) is the old plan, event for
event; ``spoken`` splits the arc and its letters (the name) from the number (the word that says it)."""
from lessonforge.longform import shape_figure as SF
from lessonforge.longform import shape_hints as H

SPEC = {"kind": "shape", "points": {"A": [1.2, 2.3], "B": [0, 0], "C": [5, 0], "D": [-1.5, 2.3]}, "polygon": "ABC",
        "angles": [{"at": "A", "from": "D", "to": "B", "role": "given"}, "B", "C"], "segments": ["AD"], "angle_sum": True}


def build():
    fig = SF.build(SPEC)
    return fig, fig.info["angle_deg"]


def sentence(text, start, duration=6.0):
    return {"text": text, "start": start, "duration": duration}


def events(sentences, info, spoken):
    return [(round(e["t"], 3), e["kind"], tuple(e["parts"])) for e in H.plan(sentences, info, None, spoken)]


def test_named_is_the_old_plan_event_for_event():
    fig, deg = build()
    s = [sentence(f"Look at angle DAB. It is {deg['DAB']} degrees. Then angle B is {deg['B']}.", 0.0)]
    old = events(s, fig.info, False)
    assert old == events(s, fig.info, None)            # the default is the old plan
    assert [k for _, k, _ in old] == ["angle", "angle"]
    assert old[0][2] == ("angle_DAB", "angle_DAB_value") and old[1][2] == ("angle_B", "angle_B_value")


def test_spoken_draws_the_arc_at_the_name_and_the_number_at_the_word_that_says_it():
    fig, deg = build()
    s = [sentence(f"Look at angle DAB. It is {deg['DAB']} degrees, a good start.", 0.0, 8.0)]
    named = [e for e in H.plan(s, fig.info, None, False) if e["kind"] == "angle"][0]
    out = H.plan(s, fig.info, None, True)
    arc = next(e for e in out if e["parts"] == ["angle_DAB"])
    value = next(e for e in out if e["parts"] == ["angle_DAB_value"])
    assert arc["kind"] == "angle" and abs(arc["t"] - named["t"]) < 1e-9           # the arc waits for the NAME as before
    toks = dict((tok, t) for tok, t in H.tokens(s[0]))
    assert value["kind"] == "value" and abs(value["t"] - toks[str(deg["DAB"])]) < 1e-9
    assert value["t"] > arc["t"] + 1.0                                              # not at "DAB": at the number
    assert not any("angle_DAB_value" in e["parts"] for e in out if e["kind"] == "angle")


def test_a_number_said_in_the_next_sentence_counts_but_one_said_much_later_does_not():
    fig, deg = build()
    near = [sentence("Look at angle DAB.", 0.0, 2.0), sentence(f"It is {deg['DAB']} degrees.", 2.0, 2.0)]
    value = next(e for e in H.plan(near, fig.info, None, True) if e["parts"] == ["angle_DAB_value"])
    assert 2.0 <= value["t"] < 4.0
    far = [sentence("Look at angle DAB.", 0.0, 2.0), sentence("Now think.", 2.0, 2.0), sentence(f"It is {deg['DAB']} degrees.", 4.0, 2.0)]
    value = next(e for e in H.plan(far, fig.info, None, True) if e["parts"] == ["angle_DAB_value"])
    assert value["t"] < 2.0                          # out of reach: the name's own moment, as before


def test_no_number_word_falls_back_to_the_name_so_nothing_disappears():
    fig, _ = build()
    s = [sentence("Look at angle DAB, the angle at the top left, and angle B.", 0.0)]
    out = H.plan(s, fig.info, None, True)
    arc = next(e for e in out if e["parts"] == ["angle_DAB"])
    value = next(e for e in out if e["parts"] == ["angle_DAB_value"])
    assert abs(value["t"] - arc["t"]) < 1e-9
    # and the number of ANOTHER angle is not taken for it
    other = [sentence(f"Look at angle DAB and angle C. Angle C is {SF.build(SPEC).info['angle_deg']['C']} degrees.", 0.0)]
    out = H.plan(other, fig.info, None, True)
    dab = next(e for e in out if e["parts"] == ["angle_DAB_value"])
    c = next(e for e in out if e["parts"] == ["angle_C_value"])
    assert dab["t"] < c["t"]


def test_the_sum_line_waits_for_the_word_that_says_the_total():
    fig, deg = build()
    total = fig.info["band_total"]
    text = f"Now add the angles. {deg['DAB']} plus {deg['B']} plus {deg['C']} makes {total} degrees."
    s = [sentence(text, 0.0, 10.0)]
    band_old = [e for e in H.plan(s, fig.info, None, False) if "band" in e["parts"]]
    assert band_old == []                              # "add" and "makes" are not verdict words: the old plan never held it
    band = [e for e in H.plan(s, fig.info, None, True) if "band" in e["parts"]]
    assert len(band) == 1
    toks = dict(H.tokens(s[0]))
    assert abs(band[0]["t"] - toks["makes"]) < 1e-9


def test_the_old_verdict_word_still_lights_the_sum_if_nothing_else_comes():
    fig, deg = build()
    s = [sentence("Check the sum of the angles carefully.", 0.0, 6.0)]
    band = [e for e in H.plan(s, fig.info, None, True) if "band" in e["parts"]]
    assert band and band[0]["kind"] == "verdict"       # "check" is an equation word here, so it is the first of them
    s = [sentence("Look at the sum of the angles carefully now.", 0.0, 6.0)]
    old = [e for e in H.plan(s, fig.info, None, False) if "band" in e["parts"]]
    new = [e for e in H.plan(s, fig.info, None, True) if "band" in e["parts"]]
    assert [round(e["t"], 3) for e in old] == [round(e["t"], 3) for e in new] and new      # no equation word: the old moment


def test_the_total_number_alone_triggers_the_sum_line_when_no_equation_word_is_said():
    fig, deg = build()
    s = [sentence(f"Together they come to {fig.info['band_total']:g} degrees.", 0.0, 6.0)]
    # "together" is not an equation word; the total as a number is
    band = [e for e in H.plan(s, fig.info, None, True) if "band" in e["parts"]]
    assert len(band) == 1 and band[0]["t"] > 3.0


def test_the_figure_reads_the_flag_the_runtime_sets():
    fig, deg = build()
    s = [sentence(f"Look at angle DAB. It is {deg['DAB']} degrees.", 0.0, 6.0)]
    old = fig.hint_plan(s)
    fig.values_spoken = True
    new = fig.hint_plan(s)
    assert any("angle_DAB_value" in e["parts"] for e in old if e["kind"] == "angle")
    assert any(e["kind"] == "value" for e in new) and not any("angle_DAB_value" in e["parts"] for e in new if e["kind"] == "angle")


def test_a_verdict_band_is_never_held_for_the_equation():
    spec = {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [4, 4], "D": [0, 4]}, "polygon": "ABCD", "verdict": True,
            "angles": list("ABCD"), "angle_sum": True}
    fig = SF.build(spec)
    assert fig.info["band_verdict"] and fig.info["band_eq"]
    s = [sentence("The shape is convex. The four angles make 360 degrees.", 0.0, 8.0)]
    old = [e["t"] for e in H.plan(s, fig.info, None, False) if "band" in e["parts"]]
    new = [e["t"] for e in H.plan(s, fig.info, None, True) if "band" in e["parts"]]
    assert old == new


def test_the_runtime_holds_each_label_until_its_own_moment():
    """What the film does: ``_hold_back_named`` waits each held part for its first event (scene seconds)."""
    from types import SimpleNamespace

    from lessonforge.longform import runtime
    fig, deg = build()
    total = fig.info["band_total"]
    s = [sentence(f"Look at angle DAB and think. Now it is {deg['DAB']} degrees. Next add the angles. "
                  f"{deg['DAB']} plus {deg['B']} plus {deg['C']} makes {total} degrees.", 0.0, 16.0)]
    when = {}
    for spoken in (False, True):
        fig, _ = build()
        fig.values_spoken = spoken
        stub = SimpleNamespace(current={"sentences": s}, beat_start=0.0, _beat_layout={})
        runtime.GuidedChapter._hold_back_named(stub, fig, None, 0.0)
        when[spoken] = {name: round(item["at"], 2) for name, item in fig._late.items()}
    assert when[False]["angle_DAB_value"] == when[False]["angle_DAB"] or "angle_DAB" in when[False]
    assert when[True]["angle_DAB_value"] > when[False]["angle_DAB_value"] + 2.0      # the number came later than the name
    toks = H.tokens(s[0])
    first = next(t for tok, t in toks if tok == str(deg["DAB"]))              # the first time it is said
    assert abs(when[True]["angle_DAB_value"] - (first - runtime.CUE_LEAD)) < 0.01
    toks = dict(toks)
    assert abs(when[True]["band"] - (toks["makes"] - runtime.CUE_LEAD)) < 0.01
    assert "band" not in when[False]                       # the old plan never held a sum line that no verdict word names


def test_a_number_the_next_triangle_writes_differently_is_new_not_carried():
    """The second triangle's 75 must not take the first one's 70 at once: it waits for its word (spoken mode only)."""
    from types import SimpleNamespace

    from lessonforge.longform import runtime
    first = SF.build(SPEC)
    other = dict(SPEC, points={"A": [1.0, 2.6], "B": [0, 0], "C": [5, 0], "F": [6.8, 0]})
    deg = SF.build(other).info["angle_deg"]
    assert deg["B"] != first.info["angle_deg"]["B"]
    s = [sentence(f"Here is a new triangle. Angle B is {deg['B']} degrees.", 0.0, 10.0)]
    late = {}
    for spoken in (False, True):
        fig = SF.build(other)
        fig.values_spoken = spoken
        stub = SimpleNamespace(current={"sentences": s}, beat_start=0.0, _beat_layout={})
        runtime.GuidedChapter._hold_back_named(stub, fig, first, 0.0)
        late[spoken] = set(fig._late)
    assert "angle_B_value" not in late[False]                  # as before: a part the carried shape had is simply there
    assert "angle_B_value" in late[True]
    same = SF.build(SPEC)
    same.values_spoken = True
    stub = SimpleNamespace(current={"sentences": [sentence("Angle B is again here.", 0.0, 4.0)]}, beat_start=0.0, _beat_layout={})
    runtime.GuidedChapter._hold_back_named(stub, same, first, 0.0)
    assert "angle_B_value" not in same._late                    # the very same number stays where it was
