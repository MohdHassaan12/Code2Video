"""What a lesson's preview stills say, in numbers (no render here: tests/integration previews a whole lesson)."""
from lessonforge.longform import preview


def result(**over):
    still = {"file": "c01_b01_003_end.jpg", "chapter": 1, "beat": "01", "what": "end", "layout": {"frame": "stage", "mode": "side", "words": "pinned"},
             "picture": {"kind": "scene", "share": 0.31, "fill": 1.0},
             "lines": [{"kind": "point", "show": "Square each side", "points": 40.0, "page": 0}, {"kind": "math", "show": "3^2 + 4^2", "points": 44.0, "page": 0}]}
    made = {"folder": "/nowhere", "timing": "estimated from the words", "failed": [], "notes": [], "bounds": [], "layout": [],
            "stills": [{"file": "c01_b01_000_step.jpg", "chapter": 1, "beat": "01", "what": "step"}, still]}
    made.update(over)
    return made


def test_a_sound_preview_has_no_fault_and_no_finding():
    assert preview.faults(result()) == 0 and preview.measure(result()) == []


def test_what_must_not_get_worse_when_a_look_is_tried():
    worse = result(failed=[3], notes=["chapter 03: LESSON_NOTE: figure 'scene' could not be built"],
                   bounds=[{"chapter": 2, "beat": "02", "type": "VGroup", "bbox": [0, 1, 2, 3]}],
                   layout=[{"chapter": 2, "beat": "02", "kind": "overlap", "detail": "Text('a') x Text('b')", "counted": True},
                           {"chapter": 2, "beat": "02", "kind": "near", "detail": "close", "counted": False}])
    assert preview.faults(worse) == 4                       # the collision that is only reported is not a fault
    kinds = [f["kind"] for f in preview.measure(worse)]
    assert kinds == ["outside", "overlap"] and all(f["fix"] == "compact" for f in preview.measure(worse))


def test_type_too_small_for_a_phone_is_a_finding_with_the_beat_it_is_in():
    small = result()
    small["stills"][1]["lines"] = [{"kind": "math", "show": "u(x,t) = 100 sin(pi x) e^{-0.04 pi^2 t}", "points": 20.0},
                                   {"kind": "point", "show": "Boundary values", "points": 26.0}, {"kind": "point", "show": "ok", "points": 40.0}]
    found = preview.measure(small)
    assert [(f["kind"], f["severity"], f["beat"]) for f in found] == [("unreadable", "high", "01"), ("small", "medium", "01")]
    assert "20 points" in found[0]["what"] and "6 on a phone" in found[0]["what"] and found[0]["fix"] == "split"
    # the size a phone shows: a 30-point line is under ten points there
    assert 9 < 30 * preview.PHONE_POINTS < 10


def test_a_picture_left_a_thumbnail_beside_its_words_is_a_finding():
    lonely = result()
    lonely["stills"][1]["picture"] = {"kind": "scene", "share": 0.03, "fill": 0.24}
    assert [(f["kind"], f["beat"], f["fix"]) for f in preview.measure(lonely)] == [("thumbnail", "01", "enlarge")]
    # a strip of fraction bars is thin by nature: 6% of the frame's area, and from one side of its room to the other
    strip = result()
    strip["stills"][1]["picture"] = {"kind": "bars", "share": 0.06, "fill": 1.0}
    assert preview.measure(strip) == []
    lonely["stills"][1]["lines"] = []                        # a picture on its own is as large as it was drawn: nothing to split
    assert preview.measure(lonely) == []


def _with_label(points, **picture):
    made = result()
    made["stills"][1]["picture"] = {"kind": "component", "share": 0.45, "fill": 1.0, "type_points": points, **picture}
    return made


def test_small_writing_inside_a_figure_is_a_small_label_finding_and_never_a_fault():
    medium = _with_label(22.4)
    (found,) = preview.measure(medium)
    assert (found["kind"], found["severity"], found["beat"], found["chapter"], found["fix"]) == ("small_label", "medium", "01", 1, "")
    assert found["what"] == "smallest label 22.4 points (7.2 on a phone) in the component picture"
    (high,) = preview.measure(_with_label(21.0))
    assert (high["kind"], high["severity"]) == ("small_label", "high") and "21.0 points (6.7 on a phone)" in high["what"]
    assert [f["kind"] for f in preview.measure(_with_label(22.0))] == ["small_label"] and preview.measure(_with_label(22.0))[0]["severity"] == "medium"
    assert preview.measure(_with_label(30.0)) == [] and preview.measure(_with_label(28.0)) == []          # 28 is not under 28
    assert preview.faults(medium) == preview.faults(result()) == 0       # compose.settle's fill-or-kept choice cannot change
    assert preview.faults(_with_label(21.0)) == 0


def test_no_type_points_no_small_label_and_other_findings_are_unchanged():
    assert preview.measure(result()) == []                                # the fixture has no type_points
    assert preview.measure(_with_label(None)) == []
    both = _with_label(24.0)
    both["stills"][1]["lines"][0]["points"] = 20.0
    assert [f["kind"] for f in preview.measure(both)] == ["unreadable", "small_label"]    # beside, not instead of, the others
    only_end = _with_label(10.0)
    only_end["stills"][1]["what"] = "step"
    assert preview.measure(only_end) == []                                # read from the end-of-beat still only
