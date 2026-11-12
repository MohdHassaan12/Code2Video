"""A pasted production document is sorted into spoken, seen and neither, and the author's words stay theirs."""
from lessonforge.harness import script_reader, writer

DOC = """Riya helps her grandfather lay tiles; every idea comes out of a job they do together in the village.
Characters: Riya, 13, school uniform. Dadaji, white kurta and spectacles.
Scene
Time
On-screen visual
Voiceover (Hinglish)
1
0:00–0:30
Drone-style swoop over a village at sunrise. A banner reads "Riya aur Dadaji".
Narrator: Garmi ki chhuttiyan shuru ho chuki thi. Riya is baar apne Dadaji ke saath kaam pe jaane wali thi.
2
0:30–2:00
Top-down view of a courtyard; a chalk square draws itself with "4 m" labels.
Pehla kaam tha school ka chhota square aangan. Har side 4 metre hai, aur har tile 1 metre ki. Kitni tiles lagengi?
Scene 2 on-screen questions (answers are for the teacher):
1. Find 7². Answer: 49
2. Is 48 a perfect square? Give a reason. Answer: No; 6² = 36 and 7² = 49."""

GOOD = {"kind": "table", "title": "Riya aur Dadaji",
        "scenes": [{"name": "1", "time": [8], "picture": [9], "spoken": [10]},
                   {"name": "2", "time": [12], "picture": [13], "spoken": [14]}],
        "notes": [1, 2], "teacher": [15, 16, 17], "skip": [3, 4, 5, 6, 7, 11],
        "questions": [{"line": 16, "answer_starts_at": "Answer:"}, {"line": 17, "answer_starts_at": "Answer:"}]}


def test_only_the_voiceover_is_spoken_and_it_is_the_authors_own_words():
    seen = []
    out = script_reader.read(DOC, lambda prompt, system: seen.append(prompt) or GOOD, log=lambda *_: None)
    script = out["script"]
    assert "10: Narrator: Garmi ki chhuttiyan" in seen[0]                      # the model sees numbered lines
    assert "Garmi ki chhuttiyan shuru ho chuki thi." in script and "Kitni tiles lagengi?" in script
    for never in ("Drone-style swoop over a village at sunrise. A banner", "0:00", "Characters:", "Answer", "49", "Voiceover"):
        assert never not in "\n".join(l for l in script.splitlines() if not l.startswith("[")), never
    assert "[Top-down view of a courtyard" in script and script.count("# Scene") == 2   # the visual is a direction
    spoken = [l for l in script.splitlines() if l and not l.startswith(("#", "["))]
    assert all(line in DOC for line in spoken)                                 # word for word from the source
    assert out["questions"] == ["1. Find 7².", "2. Is 48 a perfect square? Give a reason."]
    assert "Answer: 49" in out["teacher"] and "Characters:" in out["notes"]
    assert out["report"]["scenes"] == 2 and out["report"]["spoken_words"] < out["report"]["words"] / 2


def test_a_line_nobody_labelled_is_never_spoken():
    partial = {**GOOD, "notes": [1], "skip": []}                              # lines 2 to 7 and 11 left out
    out = script_reader.read(DOC, lambda p, s: partial, log=lambda *_: None)
    assert "Characters:" not in out["script"] and "Characters:" in out["notes"]
    assert out["report"]["unlabelled_lines"] == 7


def test_the_answer_key_wins_over_a_spoken_label():
    confused = {**GOOD, "scenes": [GOOD["scenes"][0], {**GOOD["scenes"][1], "spoken": [14, 16]}]}
    out = script_reader.read(DOC, lambda p, s: confused, log=lambda *_: None)
    assert "Find 7" not in out["script"]


def test_an_answer_that_speaks_everything_or_nothing_is_refused():
    everything = {"scenes": [{"name": "1", "spoken": list(range(1, 18))}]}
    nothing = {"scenes": [{"name": "1", "spoken": []}]}
    for bad in (everything, nothing, {"scenes": "x"}, None):
        assert script_reader.read(DOC, lambda p, s: bad, log=lambda *_: None) is None

    def broken(prompt, system):
        raise RuntimeError("no model")
    assert script_reader.read(DOC, broken, log=lambda *_: None) is None


def test_plain_narration_is_not_sent_to_a_model():
    prose = "Aaj hum square numbers dekhenge. Ek square floor mein rows aur columns barabar hote hain.\n\nPhir hum gin kar dekhenge."
    assert script_reader.looks_structured(prose) == 0 and script_reader.looks_structured(DOC) >= 5


def test_a_short_word_between_numbers_stays_a_word():
    assert writer.mathify("5 by 5 square") == "5\\text{ by }5\\text{ square}"
    assert writer.mathify("x in A") == "x in A"


def test_unicode_maths_in_a_formula_step_becomes_latex():
    assert writer.one_line_math("1+3+…+(2n-1)=n^2") == "1+3+\\dots +(2n-1)=n^2"
    assert writer.one_line_math("81−1−3−5−⋯−17=0") == "81-1-3-5-\\cdots -17=0"
    assert writer.one_line_math("9² = 81") == "9^2 = 81" and writer.one_line_math("√81 ≠ 8") == "\\sqrt 81 \\neq 8"
    assert writer.one_line_math("4 × 4 = 16") == "4 \\times 4 = 16"
