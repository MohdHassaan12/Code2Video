"""Storyboard cross-reference checks and scene renumbering."""
from lessonforge.engine.storyboard import reference_problems, renumber_scenes


def _scene(idx, elements, events=()):
    return {"scene_index": idx, "elements": elements,
            "narration_cues": [{"cue": "x", "animation_events": list(events)}]}


def test_clean_board_has_no_problems():
    sb = {"visual_storyboard": [_scene(1, [{"id": "a"}, {"id": "b"}, {"id": "c", "connects": ["a", "b"]}],
                                       [{"action": "show", "target": "a"}])]}
    assert reference_problems(sb) == []


def test_duplicate_ids_bad_connectors_and_unknown_targets_are_named():
    sb = {"visual_storyboard": [_scene(1, [{"id": "a"}, {"id": "a"}, {"id": "e", "connects": ["a", "zzz"]}],
                                       [{"action": "show", "target": "ghost"},
                                        {"action": "transform", "target": "a", "to": "nope"},
                                        {"action": "hide", "target": "from_earlier_scene"}])]}
    text = " | ".join(reference_problems(sb))
    assert "twice" in text and "connects" in text and "ghost" in text and "nope" in text
    assert "from_earlier_scene" not in text       # hiding an earlier scene's element is legitimate


def test_renumber_makes_indices_one_to_n():
    sb = {"visual_storyboard": [{"scene_index": 1}, {"scene_index": 1}, {"scene_index": 5}]}
    assert renumber_scenes(sb) == 2
    assert [s["scene_index"] for s in sb["visual_storyboard"]] == [1, 2, 3]
    assert renumber_scenes(sb) == 0
