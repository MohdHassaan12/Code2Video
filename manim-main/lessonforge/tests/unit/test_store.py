"""What a paid stage produced is kept under everything it was made from (harness/store.py)."""
from lessonforge.harness import store


def test_a_key_is_made_from_everything_and_from_nothing_else(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    brief = {"mode": "script", "script": "Ek roti lijiye.", "language": "hinglish"}
    same = store.key("script", store.content(brief), ["model-a"])
    assert same == store.key("script", store.content(dict(reversed(list(brief.items())))), ["model-a"])   # order of keys: no
    assert same != store.key("script", store.content({**brief, "script": "Do roti lijiye."}), ["model-a"])  # the words: yes
    assert same != store.key("script", store.content(brief), ["model-b"])                                   # who is asked: yes
    assert same != store.key("verify", store.content(brief), ["model-a"])                                   # which stage: yes
    # how a run is to be made is not what is made: a fresh take, a voice job and a draft file share the key
    assert same == store.key("script", store.content({**brief, "fresh": True, "voice_for": "x", "draft_file": "/y"}), ["model-a"])


def test_what_is_kept_comes_back_whole_and_only_when_it_may(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    key = store.key("script", {"script": "x"})
    assert store.get("script", key) is None
    lesson = {"title": "Half aur one fourth", "chapters": [{"id": 1, "beats": [{"id": "01", "narration": "Ek roti lijiye."}]}]}
    store.put("script", key, lesson)
    assert store.get("script", key) == lesson and store.get("verify", key) is None
    assert store.get("script", key, fresh=True) is None                  # a new take was asked for
    store.put("script", key, {"title": "second take"})                   # ... and it replaces what was kept
    assert store.get("script", key) == {"title": "second take"}
    store.put("script", store.key("odd"), {"cannot": object()})          # what JSON cannot write is not kept, and nothing is raised
    assert store.get("script", store.key("odd")) is None
    monkeypatch.setenv("HARNESS_STORE", "0")
    assert store.get("script", key) is None
    store.put("script", store.key("off"), {"a": 1})
    monkeypatch.setenv("HARNESS_STORE", "1")
    assert store.get("script", store.key("off")) is None and store.get("script", key) == {"title": "second take"}
