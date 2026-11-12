"""The reaction picture points at what the voice names (owner, 2026-10-20: "no dynamic hints, the video is stale")."""
from lessonforge.longform import figure_math, reaction_hints


def _species(equation):
    parsed = figure_math.parse_equation(equation)
    return [dict(sp, side=side) for side in ("left", "right") for sp in parsed[side]]


def _sentence(text, start=0.0):
    words = text.lower().replace(",", "").replace(".", "").split()
    return {"text": text, "start": start, "words": [{"word": w, "start": start + .3 * i} for i, w in enumerate(words)]}


def test_named_atoms_sides_formulas_and_counting_become_hints():
    sp = _species("2H2 + O2 -> 2H2O")
    events = reaction_hints.plan([_sentence("But now there are four hydrogen atoms on the right and only two on the left"),
                                  _sentence("so we take two water molecules", 10),
                                  _sentence("Now count again", 20)], sp)
    kinds = [(e["kind"], e.get("element"), e.get("side"), e.get("species")) for e in events]
    assert ("atoms", "H", None, None) in kinds
    assert ("tally", "H", "right", None) in kinds and ("tally", "H", "left", None) in kinds
    assert ("species", None, None, 2) in kinds          # "water" is the H2O on the right
    assert kinds[-1][0] == "count"


def test_a_formula_read_aloud_and_a_substance_name_are_not_an_element():
    sp = _species("H2 + O2 -> H2O2")
    events = reaction_hints.plan([_sentence("Making H two O two changes it, because hydrogen peroxide is a bleach")], sp)
    assert [e["kind"] for e in events] == ["species", "species"]
    assert all(e["species"] == 2 for e in events)


def test_the_figure_names_what_each_hint_lights():
    from lessonforge.longform import figures
    fig = figures.build({"kind": "reaction", "equation": "2H2 + O2 -> 2H2O"})
    lit = fig.hint_targets({"kind": "tally", "element": "O", "side": "right"})
    assert len(lit) == 3 and lit[-1][0] is fig.tally_pieces[("right", "O")]   # two O balls, one after another, then the count
    assert lit[0][1] < lit[1][1] <= lit[2][1]
    counted = fig.hint_targets({"kind": "count"})
    assert len(counted) == 12 + 4 and counted[-1][1] <= 3.2
