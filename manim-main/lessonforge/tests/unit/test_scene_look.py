"""A model-written scene checked against what it was asked to show: text too small to read is refused by
``sim_gen.verify`` (a real manim subprocess, no model), a cached scene verified by an older check is checked again,
and ``harness.scene_look`` keeps a redraw only when nothing it showed is lost (judge and stills stubbed)."""
import json

from lessonforge.engine import sim_gen
from lessonforge.harness import scene_look, service

SCENE = '''
def build(width, height):
    box = Square(side_length=1.0, color=BLUE).shift(LEFT)
    word = Text("ice", font_size={size}).next_to(box, UP)
    return VGroup(box, word)

def animate(group, run_time):
    return group[0].animate(run_time=run_time).shift(RIGHT * 0.5).build()
'''


def test_text_too_small_to_read_is_refused_and_readable_text_passes():
    tiny = SCENE.format(size=28).replace('.next_to(box, UP)', '.scale(0.02).next_to(box, UP)')
    error = sim_gen.verify(tiny)
    assert error and "'ice'" in error and "nobody can read it" in error
    assert sim_gen.verify(SCENE.format(size=28)) is None


def test_a_cached_scene_verified_before_the_size_check_is_drawn_again(tmp_path, monkeypatch):
    path = tmp_path / "sim_ice.py"
    path.write_text(SCENE.format(size=28).replace('.next_to(box, UP)', '.scale(0.02).next_to(box, UP)'))
    (tmp_path / "sim_ice.py.json").write_text(json.dumps({"description": "ice"}))
    asked = []
    monkeypatch.setattr(sim_gen, "revise_simulation",
                        lambda d, code, brief, keys=None, client=None: asked.append(brief) or SCENE.format(size=28))
    sim_gen._verify_again(str(path), "ice")
    meta = json.loads((tmp_path / "sim_ice.py.json").read_text())
    assert asked and "nobody can read it" in asked[0]
    assert meta["verified_with"] == sim_gen.VERIFY_REV and "redrawn_for" in meta
    assert (tmp_path / "sim_ice.first.py").exists() and 'font_size=28)' in path.read_text()
    asked.clear()
    sim_gen._verify_again(str(path), "ice")            # stamped: never checked twice
    assert not asked


def test_a_failed_redraw_keeps_the_cached_scene_in_use(tmp_path, monkeypatch):
    path = tmp_path / "sim_ice.py"
    first = SCENE.format(size=28).replace('.next_to(box, UP)', '.scale(0.02).next_to(box, UP)')
    path.write_text(first)
    monkeypatch.setattr(sim_gen, "revise_simulation", lambda *a, **k: None)
    sim_gen._verify_again(str(path), "ice")
    assert path.read_text() == first
    assert "verify_failed" in json.loads((tmp_path / "sim_ice.py.json").read_text())


def test_where_a_staged_scene_rests():
    assert scene_look.rests(1) == [0.0, 0.999]
    assert scene_look.rests(3) == [0.0, 0.333, 0.6663, 0.999]


def things(*seen):
    return {"things": [{"thing": f"t{i}", "seen": s, "instead": ""} for i, s in enumerate(seen)],
            "extra_words": [], "faults": sum(s != "shown" for s in seen)}


def test_a_redraw_is_kept_only_when_it_loses_nothing_and_cures_something():
    before = things("shown", "missing", "wrong")
    assert scene_look.better(before, things("shown", "shown", "wrong"))[0]
    assert not scene_look.better(before, things("missing", "shown", "shown"))[0]       # lost t0
    assert not scene_look.better(before, things("shown", "missing", "wrong"))[0]       # cured nothing
    worded = things("shown", "shown", "shown")
    worded["extra_words"] = ["spin"]
    assert not scene_look.better(before, worded)[0]                                    # wrote words nobody asked for


def test_check_redraws_on_confirmed_faults_and_keeps_the_better_scene(tmp_path, monkeypatch):
    module = tmp_path / "sim_x.py"
    module.write_text("# header\n" + SCENE.format(size=28))
    monkeypatch.setattr(scene_look, "stills", lambda code, alphas, staged, **k: [b"a", b"b"])
    monkeypatch.setattr(scene_look, "sheet", lambda pngs, **k: b"jpg")
    answers = iter([
        {"things": [{"thing": "a block", "seen": "shown"}, {"thing": "a question mark", "seen": "missing"}]},
        {"answers": [{"n": 1, "seen": "shown"}, {"n": 2, "seen": "missing"}]},          # the faults confirmed
        {"answers": [{"n": 1, "seen": "shown"}, {"n": 2, "seen": "shown"}]},            # the redraw shows both
    ])
    briefs = []
    result = scene_look.check("a block and a question mark", module, 1, judge=lambda *a: next(answers),
                              revise=lambda code, brief: briefs.append(brief) or "def build(w, h): pass\n", log=lambda *_: None)
    assert result["kept"] and "a question mark: NOT DRAWN" in briefs[0]
    assert module.with_suffix(".first.py").exists() and "def build(w, h)" in module.read_text()
    meta = json.loads((tmp_path / "sim_x.py.json").read_text())
    assert meta["looked"]["version"] == scene_look.VERSION and meta["looked"]["redraw"]["kept"]
    again = scene_look.check("a block and a question mark", module, 1, judge=lambda *a: 1 / 0, log=lambda *_: None)
    assert again.get("cached")                          # looked at once, whatever lesson uses it next


def test_an_unconfirmed_fault_pays_for_no_redraw(tmp_path, monkeypatch):
    module = tmp_path / "sim_x.py"
    module.write_text(SCENE.format(size=28))
    monkeypatch.setattr(scene_look, "stills", lambda code, alphas, staged, **k: [b"a", b"b"])
    monkeypatch.setattr(scene_look, "sheet", lambda pngs, **k: b"jpg")
    answers = iter([{"things": [{"thing": "a block", "seen": "missing"}]},
                    {"answers": [{"n": 1, "seen": "shown"}]}])
    result = scene_look.check("a block", module, 1, judge=lambda *a: next(answers),
                              revise=lambda *a: (_ for _ in ()).throw(AssertionError("no redraw")), log=lambda *_: None)
    assert not result["redrawn"] and "did not confirm" in result["why"]


def test_the_look_is_off_unless_switched_on(monkeypatch):
    called = []
    monkeypatch.delenv("HARNESS_SCENE_LOOK", raising=False)
    assert service.look_at_scenes({"d": [{}]}, {"d": "p"}, {"d": "d"}, check=lambda *a: called.append(a)) == {}
    monkeypatch.setenv("HARNESS_SCENE_LOOK", "1")
    out = service.look_at_scenes({"d": [{"steps": [{"show": "a"}, {"show": "b"}]}]}, {"d": "p"}, {"d": "d"},
                                 log=lambda *_: None, check=lambda d, p, n: called.append(n) or {"faults": 0})
    assert called == [2] and "d" in out
