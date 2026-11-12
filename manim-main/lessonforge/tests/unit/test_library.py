

def test_a_maths_topic_is_not_sent_to_the_science_book_by_an_everyday_word():
    # seen 2026-10-19: "work out the probability" sent a Monty Hall lesson to Class 10 science
    from lessonforge.harness.library import school_subject
    assert school_subject({"topic": "Monty Hall problem", "goal": "work out the probability of winning"}) == "maths"
    assert school_subject({"topic": "Why is 0.999... equal to 1?", "goal": "the repeating decimal and 1"}) == "maths"
    assert school_subject({"topic": "Work and energy", "goal": "find the work done"}) == "science"
    assert school_subject({"topic": "Why does ice float?", "goal": "explain it with density"}) == "science"
    assert school_subject({"topic": "The Moon's face", "goal": "explain it"}) is None
