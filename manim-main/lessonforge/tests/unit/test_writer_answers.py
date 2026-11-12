"""A writer model's answer must be a JSON object; anything else is a failed answer and the chain moves on."""
import json

import pytest

from lessonforge.engine import llm as engine_llm
from lessonforge.harness import writer

LESSON = {"title": "T", "chapters": []}


def test_an_object_serialised_twice_is_read_and_anything_else_is_refused():
    assert writer.answer_object(json.dumps(LESSON)) == LESSON
    assert writer.answer_object(json.dumps(json.dumps(LESSON))) == LESSON, "a JSON string holding JSON is parsed again"
    assert writer.answer_object("```json\n" + json.dumps(LESSON) + "\n```") == LESSON
    for bad in (json.dumps("just words"), json.dumps([1, 2]), json.dumps(3), json.dumps(json.dumps("x"))):
        with pytest.raises(ValueError):
            writer.answer_object(bad)


def test_the_openrouter_writer_asks_the_next_model_after_an_answer_that_is_no_object(monkeypatch):
    asked = []
    answers = [json.dumps("a story about magnets"), json.dumps(LESSON)]

    def fake_openrouter(key, prompt, system, models=None, **kwargs):
        asked.append(list(models))
        return answers.pop(0)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(engine_llm, "call_openrouter", fake_openrouter)
    call = writer.default_llm(models=["m/one", "m/two", "m/three"])
    assert call("p", "s") == LESSON
    assert asked == [["m/one", "m/two", "m/three"], ["m/two", "m/three"]], "the first model's string answer moved the chain on"

    answers[:] = [json.dumps("still words")]
    asked.clear()
    with pytest.raises(ValueError):
        writer.default_llm(models=["m/only"])("p", "s")
    assert asked == [["m/only"]], "with one model left the failure is reported, not retried for ever"
