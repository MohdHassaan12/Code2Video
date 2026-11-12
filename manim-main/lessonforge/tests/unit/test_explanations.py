"""The checked NCERT explanation table reaches the writer only when a topic clearly matches a row."""
import csv

from lessonforge.harness import explanations, writer

ROWS = [
    {"concept_id": "C10-MAT-08-01", "class": "10", "subject": "Mathematics", "chapter": "Introduction to Trigonometry",
     "concept": "Trigonometric ratios of an acute angle", "key_idea": "The ratios depend only on the angle. Misconception: sides.",
     "prerequisites": "Pythagoras theorem", "lecture1_title": "Trig ratios", "lecture1_channel": "Khan Academy India"},
    {"concept_id": "C8-SCI-06-01", "class": "8", "subject": "Science", "chapter": "Pressure, Winds, Storms",
     "concept": "Pressure = force / area; unit pascal", "key_idea": "Same force on a smaller area presses harder.",
     "prerequisites": "Force"},
]


def _table(tmp_path, monkeypatch):
    path = tmp_path / "kb.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=explanations.FIELDS)
        w.writeheader()
        for r in ROWS:
            w.writerow({k: r.get(k, "") for k in explanations.FIELDS})
    monkeypatch.setenv("LESSONFORGE_EXPLANATIONS", str(path))
    monkeypatch.setenv("HARNESS_EXPLANATIONS", "1")


def test_a_clear_topic_gets_its_row_and_the_class_matters(tmp_path, monkeypatch):
    _table(tmp_path, monkeypatch)
    found = explanations.find("Tangent and reciprocal ratios (trigonometric ratios of an acute angle)", "Class 10")
    assert [r["concept_id"] for r in found] == ["C10-MAT-08-01"]
    assert explanations.find("Trigonometric ratios of an acute angle", "Class 6") == []
    assert explanations.find("Air pressure and winds", "Class 8") == []      # one shared word is not a match


def test_the_rows_go_into_the_brief_and_the_writer_is_told(tmp_path, monkeypatch):
    _table(tmp_path, monkeypatch)
    brief = explanations.attach({"topic": "The concept of pressure: force over area", "level": "Class 8"})
    assert brief["explanations"][0]["concept_id"] == "C8-SCI-06-01"
    text = writer._brief_block(brief, {"voice": "", "stages": []})
    assert "HOW THE BEST TEACHERS EXPLAIN THIS" in text and "smaller area presses harder" in text
    assert explanations.attach(brief) is brief                              # attached once


def test_off_means_untouched(tmp_path, monkeypatch):
    _table(tmp_path, monkeypatch)
    monkeypatch.setenv("HARNESS_EXPLANATIONS", "0")
    brief = {"topic": "Trigonometric ratios of an acute angle", "level": "Class 10"}
    assert explanations.attach(brief) is brief


def test_mistakes_come_from_the_skill_that_is_the_topic(tmp_path, monkeypatch):
    path = tmp_path / "eedi-misconception-map.csv"
    rows = [("Believes larger numerator means smaller fraction", "40", "Order fractions with the same denominators"),
            ("Adds the denominators", "60", "Add proper fractions with different denominators"),
            ("Thinks a larger shaded area is a larger fraction", "30", "Order fractions whose denominators are not multiples")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["MisconceptionId", "MisconceptionName", "PercentageMisconceptionExistsInThisConstruct", "ConstructId",
                    "ConstructName", "SubTopicSubjectId", "SubTopicName"])
        for i, (name, share, skill) in enumerate(rows):
            w.writerow([i, name, share, i, skill, 1, "Fractions"])
    monkeypatch.setenv("LESSONFORGE_MISCONCEPTIONS", str(path))
    found = explanations.mistakes("Comparing fractions with like denominators")
    assert found[0]["mistake"] == "Believes larger numerator means smaller fraction"
    assert explanations.mistakes("Photosynthesis in green plants") == []
