"""Where a model-written scene or drawing is kept (engine/sim_gen.py). No model, no render."""
def test_two_scene_descriptions_that_begin_alike_never_share_a_cache_file(tmp_path, monkeypatch):
    """The ice lesson (2026-10-19): a scene asked for again with what it had to show added at the END came back from
    the cache as the old scene, because the file was named after the first 56 letters only."""
    import json
    from lessonforge.engine import sim_gen
    monkeypatch.setattr(sim_gen, "CACHE_DIR", str(tmp_path))
    first = "Two blocks side by side, both labelled equal mass; first the water block appears."
    again = first + " It must plainly show: the ice block."
    assert sim_gen.cached_path(first) != sim_gen.cached_path(again)
    assert sim_gen.cached_path("a ball") == str(tmp_path / "sim_a_ball.py")          # a short one keeps its name
    legacy = tmp_path / f"sim_{sim_gen.slug(first)}.py"                               # made before the change: still used
    legacy.write_text("def build(w, h): pass")
    (tmp_path / (legacy.name + ".json")).write_text(json.dumps({"description": first}))
    assert sim_gen.cached_path(first) == str(legacy) and sim_gen.cached_path(again) != str(legacy)
