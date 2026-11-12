"""Per-lesson settings (``lessonforge.knobs``): a lesson's switches reach its stages and its pools, nothing else."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from lessonforge import knobs
from lessonforge.harness import api, repairs, scripted, service


def test_a_setting_is_seen_by_the_lesson_and_its_pools_and_by_nobody_else(monkeypatch):
    monkeypatch.delenv("HARNESS_ANNOTATE", raising=False)
    assert knobs.get("HARNESS_ANNOTATE", "1") == "1"
    with knobs.applied({"HARNESS_ANNOTATE": "0", "HARNESS_CRITIC_ROUNDS": 1}):
        assert knobs.get("HARNESS_ANNOTATE", "1") == "0"
        assert knobs.get("HARNESS_CRITIC_ROUNDS", "2") == "1"          # stored as a string
        assert knobs.environ()["HARNESS_ANNOTATE"] == "0"
        with ThreadPoolExecutor(2) as pool:
            seen = list(pool.map(knobs.wrap(lambda _: knobs.get("HARNESS_ANNOTATE", "1")), [1, 2]))
            bare = list(pool.map(lambda _: knobs.get("HARNESS_ANNOTATE", "1"), [1]))
        assert seen == ["0", "0"]
        assert bare == ["1"], "a pool without wrap does not see the lesson's settings: wrap is what carries them"
    assert knobs.get("HARNESS_ANNOTATE", "1") == "1"
    assert knobs.overrides() == {}


def test_wrap_serves_many_workers_at_once():
    """One contextvars.Context cannot be entered by two threads: a wrapped call must not share one."""
    import time

    def slow(_):
        time.sleep(0.05)
        return knobs.get("HARNESS_ANNOTATE", "1")

    with knobs.applied({"HARNESS_ANNOTATE": "0"}):
        with ThreadPoolExecutor(6) as pool:
            assert list(pool.map(knobs.wrap(slow), range(12))) == ["0"] * 12


def test_the_environment_still_answers_when_a_lesson_has_no_setting(monkeypatch):
    monkeypatch.setenv("HARNESS_ANNOTATE", "0")
    with knobs.applied({}):
        assert knobs.get("HARNESS_ANNOTATE", "1") == "0"
    with knobs.applied({"HARNESS_ANNOTATE": "1"}):
        assert knobs.get("HARNESS_ANNOTATE", "1") == "1"


def test_validate_takes_every_kind_and_refuses_what_it_cannot_name():
    out = knobs.validate({"HARNESS_ANNOTATE": False, "HARNESS_CRITIC_ROUNDS": "1", "HARNESS_COMPOSE_MEND": "words",
                          "HARNESS_WRITER_MODELS": "anthropic/claude-haiku-5.5, openai/gpt-5.4-nano",
                          "HARNESS_QUESTIONS": "on", "LESSONFORGE_QUIZ_IN_VIDEO": "options"})
    assert out == {"HARNESS_ANNOTATE": "0", "HARNESS_CRITIC_ROUNDS": "1", "HARNESS_COMPOSE_MEND": "words",
                   "HARNESS_WRITER_MODELS": "anthropic/claude-haiku-5.5,openai/gpt-5.4-nano",
                   "LESSONFORGE_QUIZ_IN_VIDEO": "options"}, "a value equal to the default (questions on) is not recorded"
    assert knobs.validate(None) == {} and knobs.validate({"HARNESS_ANNOTATE": None}) == {}
    for bad in ({"HARNESS_NOPE": "1"}, {"HARNESS_CRITIC_ROUNDS": 9}, {"HARNESS_CRITIC_ROUNDS": "two"},
                {"HARNESS_COMPOSE_MEND": "maybe"}, {"HARNESS_ANNOTATE": "sometimes"},
                {"HARNESS_WRITER_MODELS": "rm -rf /"}, {"OPENROUTER_API_KEY": "x"}):
        with pytest.raises(knobs.BadSetting) as caught:
            knobs.validate(bad)
        assert next(iter(bad)) in str(caught.value)


def test_the_catalogue_names_every_control_with_the_servers_value(monkeypatch):
    monkeypatch.setenv("HARNESS_CRITIC_ROUNDS", "3")
    view = knobs.catalogue()
    rows = {row["id"]: row for row in view["controls"]}
    assert set(rows) == {c.id for c in knobs.CONTROLS}
    assert rows["HARNESS_CRITIC_ROUNDS"]["current"] == "3" and rows["HARNESS_CRITIC_ROUNDS"]["default"] == "2"
    assert all(row["group"] in view["groups"] for row in rows.values())
    assert all(row["options"] for row in rows.values() if row["kind"] == "choice")
    # every control's id is read somewhere in the package, through knobs.get or the render environment
    import pathlib
    source = "".join(p.read_text() for p in pathlib.Path(knobs.__file__).parent.rglob("*.py") if p.name != "knobs.py")
    for control in knobs.CONTROLS:
        assert f'"{control.id}"' in source or f"'{control.id}'" in source, f"{control.id} is listed but nothing reads it"


def test_a_render_setting_travels_in_the_subprocess_environment_only():
    with knobs.applied({"LESSONFORGE_QUIZ_IN_VIDEO": "options", "HARNESS_ANNOTATE": "0"}):
        assert knobs.render_env() == {"LESSONFORGE_QUIZ_IN_VIDEO": "options"}
    assert knobs.render_env() == {}


def test_module_constants_follow_a_lessons_setting(monkeypatch):
    monkeypatch.delenv("HARNESS_SCREEN_REPAIR_BEATS", raising=False)
    monkeypatch.delenv("HARNESS_SCRIPT_MAX_PICTURES", raising=False)
    assert repairs.max_beats() == repairs.MAX_BEATS and scripted.max_pictures() == scripted.MAX_PICTURES
    with knobs.applied({"HARNESS_SCREEN_REPAIR_BEATS": "2", "HARNESS_SCRIPT_MAX_PICTURES": "1"}):
        assert repairs.max_beats() == 2 and scripted.max_pictures() == 1


def test_the_route_validates_settings_and_hands_them_to_the_job(monkeypatch):
    seen = {}

    def fake_start(brief, quality="m", voice=None, settings=None, **_):
        seen.update(brief=brief, quality=quality, settings=settings)
        return {"job_id": "j1", "status": "queued", "stage": "queued", "stages": [], "progress": [], "title": brief.get("topic", ""),
                "brief": brief, "settings": settings or {}, "voice": None, "error": None, "video_url": None, "captions_url": None}

    monkeypatch.setattr(service, "start_job", fake_start)
    monkeypatch.setattr(api.analytics, "note", lambda *a, **k: None)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    reply = client.get("/api/harness/controls")
    assert reply.status_code == 200 and len(reply.json()["controls"]) == len(knobs.CONTROLS)
    reply = client.post("/api/harness/generate", json={"brief": {"topic": "magnets"}, "quality": "l",
                                                        "settings": {"HARNESS_ANNOTATE": False, "HARNESS_CRITIC_ROUNDS": 1}})
    assert reply.status_code == 200, reply.text
    assert seen["settings"] == {"HARNESS_ANNOTATE": "0", "HARNESS_CRITIC_ROUNDS": "1"}
    assert reply.json()["settings"] == seen["settings"]
    reply = client.post("/api/harness/generate", json={"brief": {"topic": "magnets"}, "settings": {"HARNESS_NOPE": "1"}})
    assert reply.status_code == 400 and "HARNESS_NOPE" in reply.json()["detail"]
    reply = client.post("/api/harness/generate", json={"brief": {"topic": "magnets"}})
    assert reply.status_code == 200 and seen["settings"] is None
