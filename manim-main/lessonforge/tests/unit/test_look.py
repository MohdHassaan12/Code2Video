"""A lesson's look: decided when it is made, written in its lesson.json, read back by every render of it."""
import json

from lessonforge.longform import look


def lesson(*kinds, said=None):
    made = {"chapters": [{"id": 1, "beats": [{"id": f"{n:02}", **({"figure": {"kind": kind}} if kind else {})}
                                              for n, kind in enumerate(kinds, 1)]}]}
    if said is not None:
        made["look"] = said
    return made


def test_a_lesson_that_says_nothing_renders_as_every_lesson_did_before():
    assert look.of(lesson("diagram"), environ={}) == {"frame": "columns", "captions": "band", "page": "night", "pictures": "kept",
                                                      "working": "column", "drawings": "shown", "joins": "cut", "math": "serif",
                                                      "values": "named", "staging": "whole", "craft": "plain"}
    assert look.of(None, environ={}) == look.BEFORE and look.of({"look": "stage"}, environ={}) == look.BEFORE
    # a value nobody knows is not a look: that part stays as before
    assert look.of(lesson(said={"frame": "stage", "captions": "outside", "page": "sepia"}), environ={})["page"] == "night"


def test_a_lesson_keeps_the_look_it_was_made_with():
    said = {"frame": "stage", "captions": "outside", "page": "paper", "pictures": "fill", "working": "pinned", "drawings": "painted",
            "joins": "carried", "math": "sans", "values": "spoken", "staging": "steps", "craft": "crafted"}
    assert look.of(lesson("diagram", said=said), environ={}) == said
    # what new lessons get now does not reach a lesson that already has a look
    assert look.of(lesson("diagram", said=said), environ={"HARNESS_FRAME": "columns"}) == said
    # a lesson made in the stage frame on the morning of 2026-10-10 says nothing of the two things added that evening:
    # it keeps its column of working and its pictures at the size they had
    morning = look.of(lesson("diagram", said={"frame": "stage", "captions": "outside", "page": "paper"}), environ={})
    assert (morning["pictures"], morning["working"]) == ("kept", "column")


def test_a_trial_may_override_one_render_without_touching_the_lesson():
    said = {"frame": "stage", "captions": "outside", "page": "paper", "pictures": "kept", "working": "column", "drawings": "shown",
            "joins": "cut", "math": "serif", "values": "named", "staging": "whole", "craft": "plain"}
    assert look.of(lesson(said=said), environ={"LESSONFORGE_FRAME": "columns"}) == {**said, "frame": "columns", "captions": "band"}
    assert look.of(lesson(), environ={"LESSONFORGE_FRAME": "stage"}) == {**said, "captions": "band", "page": "night"}
    assert look.of(lesson(), environ={"LESSONFORGE_FRAME": "stage", "LESSONFORGE_CAPTION_BAND": "0", "LESSONFORGE_THEME": "paper"}) == said
    assert look.of(lesson(said=said), environ={"LESSONFORGE_CAPTION_BAND": "1"})["captions"] == "band"
    tried = look.of(lesson(said=said), environ={"LESSONFORGE_PICTURES": "fill", "LESSONFORGE_WORKING": "pinned"})
    assert (tried["pictures"], tried["working"]) == ("fill", "pinned")


def test_the_old_frame_always_keeps_its_band():
    old = look.of(lesson(said={"frame": "columns", "captions": "outside", "pictures": "fill", "working": "pinned"}), environ={})
    assert old == look.BEFORE                                # ... and knows nothing of what the stage frame learnt later


def test_a_new_lesson_is_staged_without_a_band_and_light_only_when_every_picture_is_a_prepared_drawing():
    assert look.for_new(lesson("diagram", None, "picture"), environ={}) == {"frame": "stage", "captions": "outside", "page": "paper",
                                                                            "pictures": "kept", "working": "pinned", "drawings": "painted",
                                                                            "joins": "carried", "math": "sans",
                                                                            "values": "spoken", "staging": "steps", "craft": "crafted"}
    # one code-drawn figure or one model-written scene: its colours were chosen for the dark page
    assert look.for_new(lesson("diagram", "bars"), environ={})["page"] == "night"
    assert look.for_new(lesson("scene"), environ={})["page"] == "night"
    # a lesson with no picture at all was not what the light page was offered for
    assert look.for_new(lesson(None, None), environ={})["page"] == "night"
    assert look.for_new(environ={}) == {"frame": "stage", "captions": "outside", "page": "night", "pictures": "kept", "working": "pinned",
                                        "drawings": "painted", "joins": "carried", "math": "sans", "values": "spoken", "staging": "steps", "craft": "crafted"}


def test_the_old_frame_is_one_setting_away():
    assert look.for_new(lesson("diagram"), environ={"HARNESS_FRAME": "columns"}) == look.BEFORE
    assert look.for_new(lesson("diagram"), environ={"HARNESS_CAPTIONS": "band", "HARNESS_PAGE": "night", "HARNESS_WORKING": "column"}) == \
        {"frame": "stage", "captions": "band", "page": "night", "pictures": "kept", "working": "column", "drawings": "painted",
         "joins": "carried", "math": "sans", "values": "spoken", "staging": "steps", "craft": "crafted"}
    assert look.for_new(lesson("bars"), environ={"HARNESS_PAGE": "paper"})["page"] == "paper"


def test_chapters_are_joined_for_new_lessons_and_cut_for_old_ones():
    # a lesson made before 2026-10-15 says nothing of its joins: it is cut, as it was made and checked
    assert look.of(lesson(said={"frame": "stage", "captions": "outside", "page": "paper"}), environ={})["joins"] == "cut"
    assert look.for_new(lesson("diagram"), environ={})["joins"] == "carried"
    assert look.for_new(lesson("diagram"), environ={"HARNESS_JOINS": "cut"})["joins"] == "cut"
    # a trial may join one render of an old lesson; the old frame never is
    assert look.of(lesson(said={"frame": "stage"}), environ={"LESSONFORGE_JOINS": "carried"})["joins"] == "carried"
    assert look.of(lesson(said={"frame": "columns", "joins": "carried"}), environ={})["joins"] == "cut"


def test_formulas_are_sans_for_new_lessons_and_serif_for_old_ones():
    assert look.for_new(lesson("bars"), environ={})["math"] == "sans"
    assert look.for_new(lesson("bars"), environ={"HARNESS_MATH": "serif"})["math"] == "serif"
    assert look.of(lesson(said={"frame": "stage"}), environ={})["math"] == "serif"           # made before 2026-10-17
    assert look.of(lesson(said={"frame": "stage"}), environ={"LESSONFORGE_MATH": "sans"})["math"] == "sans"
    assert look.of(lesson(said={"frame": "columns", "math": "sans"}), environ={})["math"] == "serif"


def test_the_boxes_a_prepared_drawing_can_be_given():
    staged = {"frame": "stage", "captions": "outside", "page": "paper"}
    assert look.picture_boxes(staged) == [(9.0, 6.8), (13.3, 5.15)]
    assert look.picture_boxes({**staged, "captions": "band"}) == [(9.0, 5.65), (13.3, 4.0)]
    assert look.picture_boxes(look.BEFORE) == [(8.85, 5.7)]
    assert look.stage_bounds(staged) == (-6.8, 6.8, -3.8, 3.2) and look.stage_bounds({**staged, "captions": "band"})[2] == -2.65


def test_a_look_is_read_from_a_lesson_folder_and_nothing_raises(tmp_path):
    assert look.read(tmp_path) is None and look.read(None) is None
    (tmp_path / "lesson.json").write_text("not json", encoding="utf-8")
    assert look.read(tmp_path) is None
    (tmp_path / "lesson.json").write_text(json.dumps(lesson("diagram", said={"frame": "stage"})), encoding="utf-8")
    assert look.of(look.read(tmp_path), environ={})["frame"] == "stage"


def test_values_and_staging_are_new_for_new_lessons_only():
    # a lesson that says nothing is shown as every lesson was: an angle's number with its arc, a finished graph whole
    assert look.of(lesson(said={"frame": "stage"}), environ={})["values"] == "named"
    assert look.of(lesson(said={"frame": "stage"}), environ={})["staging"] == "whole"
    new = look.for_new(lesson("shape"), environ={})
    assert (new["values"], new["staging"]) == ("spoken", "steps")
    assert look.for_new(lesson("shape"), environ={"HARNESS_VALUES": "named", "HARNESS_STAGING": "whole"})["values"] == "named"
    assert look.for_new(lesson("shape"), environ={"HARNESS_STAGING": "whole"})["staging"] == "whole"
    # a stored look that has them keeps them, and a trial may override one render
    said = {"frame": "stage", "values": "spoken", "staging": "steps", "craft": "crafted"}
    assert look.of(lesson(said=said), environ={})["values"] == "spoken"
    assert look.of(lesson(said=said), environ={"LESSONFORGE_VALUES": "named"})["values"] == "named"
    assert look.of(lesson(said=said), environ={"LESSONFORGE_STAGING": "whole"})["staging"] == "whole"
    # a value nobody knows is not a look
    assert look.of(lesson(said={"frame": "stage", "values": "loud"}), environ={})["values"] == "named"
    # the old frame (HARNESS_FRAME=columns) is exactly the old look
    assert look.for_new(lesson("shape"), environ={"HARNESS_FRAME": "columns"}) == look.BEFORE
