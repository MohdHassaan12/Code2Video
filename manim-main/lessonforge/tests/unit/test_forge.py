"""Lesson Forge sections → lesson.json (harness/forge.py): no network, no model."""
from lessonforge.harness import forge
from lessonforge.longform.contract import Lesson

PLAN = {"schema": "forge/1", "title": "Linear equations", "topic": "Linear equations", "level": "Class 8", "language": "en",
        "lectures": [{"title": "Solving simple equations", "story": "An equation is a balance.", "running_example": "3x + 5 = 14",
                      "keypoints": [{"title": "The balancing rule", "goal": "Keep both sides equal.",
                                     "brief": "Learners often forget to subtract from both sides."}]}]}
SECTIONS = [
    {"type": "narrate", "say": "Hi Riya! Today we treat an equation like a balance."},
    {"type": "card", "id": "k1", "title": "The Golden Rule", "text": "3x + 5 = 14\n\n- Subtract 5 from both sides\n- 3x = 9\n- x = 3",
     "say": "Here is our equation.", "lines_said": ["Take five from each side.", "That leaves three x equals nine.",
                                                    "So x equals three."], "your_turn": False},
    {"type": "mark", "card": "k1", "text": "both sides", "style": "circle", "say": "Both sides, always."},
    {"type": "graphic", "layout": "plot", "params": {"layout": "plot", "expression": "2*x - 1", "expression2": "-x + 5",
                                                     "x_min": -2, "x_max": 5},
     "computed": {"points": []}, "text": "**Graph**\n- the two lines meet at (2, 3)", "say": "Two lines on one graph.",
     "lines_said": ["They cross at one point."]},
    {"type": "check", "question": "What is x if x + 7 = 10?", "answer": "x = 3",
     "choices": [{"text": "3", "correct": True, "feedback": "Take seven from both sides."},
                 {"text": "17", "correct": False, "feedback": "That adds seven instead."},
                 {"text": "7", "correct": False, "feedback": "Seven is what was added."}], "pairs": []},
]
BUILT = {"keypoints": [{"keypoint": 0, "title": "The balancing rule", "goal": "Keep both sides equal.", "sections": SECTIONS}],
         "errors": [], "done": {"cost_usd": 0.004}}


def test_a_forge_lecture_becomes_a_valid_lesson(tmp_path):
    lesson = forge.lesson_from_forge(PLAN, BUILT, 0, store=tmp_path)
    Lesson.model_validate(lesson)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    assert lesson["generated_by"] == forge.GENERATED_BY
    assert not beats[0]["narration"].startswith("Hi")                    # the board's greeting is not filmed
    card = beats[1]
    assert card["narration"].startswith("Here is our equation.") and "Both sides, always." in card["narration"]
    shows = [s["show"] for s in card["steps"]]
    assert shows[0] == "The Golden Rule" and any("both sides" in s for s in shows)
    assert all(s["say"] for s in card["steps"])                          # every line appears on words really spoken
    graph = beats[2]["figure"]
    assert graph["kind"] == "graph" and graph["functions"] == ["2*x - 1", "-x + 5"]
    question, answer = beats[3], beats[4]
    assert question["quiz"]["options"] == ["3", "17", "7"] and question["quiz"]["answer_index"] == 0
    assert question["quiz"]["why"][1] == "That adds seven instead."
    assert question["thinking_pause_seconds"] >= 5
    assert "three" in answer["narration"]                                # the answer is spoken, not only tapped
    assert lesson["brief"]["misconception"].startswith("Learners often forget")
    assert lesson["brief"]["audience"].startswith("Class 8")


def test_algebra_is_spoken_as_algebra():
    from lessonforge.harness.writer import speakable
    assert speakable("Use 3x + 5 = 14.") == "Use three x plus five equals fourteen."
    assert speakable("Solve 2(x - 3) = 4x - 10") == "Solve two times (x minus three) equals four x minus ten"
    assert speakable("y = -x + 5") == "y equals minus x plus five"
    assert speakable("It costs ₹50 and is 10cm long, the 5th one") == "It costs fifty rupees and is ten centimetres long, the fifth one"
    assert speakable("Ab 2x + 3 = 9 hai", "hinglish") == "Ab two x plus three equals nine hai"
    assert speakable("twenty-five and well-known") == "twenty-five and well-known"


def test_a_board_svg_is_made_standalone():
    svg = forge.standalone_svg('<style>.hk-n{}</style><svg class="hk-fig" viewBox="0 0 480 144" role="img">'
                               '<g class="c-blue hk-n"><rect class="box" x="1" y="1" width="9" height="9"/></g></svg><p>caption</p>')
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and 'width="480"' in svg
    assert ".c-blue>rect" in svg and "<p>" not in svg and "hk-n" not in svg


def test_a_brief_carries_what_forge_built():
    brief = forge.brief_from(PLAN, BUILT, 0, stop_after="verify")
    assert forge.is_forge(brief) and brief["stop_after"] == "verify" and forge.spoken_words(brief) > 20
    from lessonforge.harness import store
    assert "stop_after" not in store.content(brief)                      # checking the script first does not change its key
