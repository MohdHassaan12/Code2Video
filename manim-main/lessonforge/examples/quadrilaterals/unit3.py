"""Unit 3: convex and non-convex quadrilaterals, the tipping point, the angle sum (pack section 3, A to D).

Every angle value, the verdicts and the quiz answer come from ``longform.geometry`` (worked out below)."""
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G
from lessonforge.longform.shape_figure import round_to_total

CV = {"A": [0, 0], "B": [4, 0.3], "C": [4.6, 3.2], "D": [0.4, 2.8]}
AR = {"A": [0, 0], "B": [4.4, 1.6], "C": [0, 3.2], "D": [1.4, 1.6]}
THIN = {"A": [0, 0], "B": [5, 0.2], "C": [5.4, 1.1], "D": [0.2, 0.8]}
FC = [-0.6, -0.6, 5.2, 3.8]
FA = [-0.6, -0.6, 5.0, 3.8]

ar = round_to_total(G.Model({"points": AR, "polygon": "ABCD"}).interior(), 360)
assert G.status([AR[k] for k in "ABCD"])["kind"] == "concave" and ar["D"] > 180
known = [ar["A"], ar["B"], ar["C"]]
D_ANGLE = 360 - sum(known)
assert D_ANGLE == ar["D"]
OUTSIDE = 360 - D_ANGLE                 # the angle measured outside the dent
TRIANGLE = 180 - sum(known)             # the triangle angle sum used by mistake
assert not G.segments_cross(AR["A"], AR["C"], AR["B"], AR["D"])


def say_deg(n):
    return f"{n:g} degrees"


def cv(**more):
    spec = {"kind": "shape", "points": CV, "polygon": "ABCD", "frame": FC}
    spec.update(more)
    return spec


def arrow(**more):
    spec = {"kind": "shape", "points": AR, "polygon": "ABCD", "frame": FA}
    spec.update(more)
    return spec


def pair(left=None, right=None):
    left, right = left or {}, right or {}
    return {"kind": "shape", "panels": [
        dict({"points": CV, "polygon": "ABCD", "caption": "first", "key": "first outward convex"}, **left),
        dict({"points": AR, "polygon": "ABCD", "caption": "second", "key": "second dent concave inward"}, **right)]}


ch1 = C(1, "NOTICE THE DENT", "Spot the inward corner of a non-convex quadrilateral", [
    B("01", "Here are two quadrilaterals. Both have four sides. In the first, every corner points outward. "
            "In the second, one corner is pushed inward, like a dent.",
      pair({"hide_points": list("ABCD")}, {"hide_points": list("ABCD")}),
      [S("Both have four sides", "Two quadrilaterals"),
       S("every corner points outward", "First: all corners out"),
       S("one corner is pushed inward", "Second: a dent", "key")]),
    B("02", "Look at the second shape. Which vertex is pushed inward?",
      arrow(), [S("Which vertex is pushed inward", "Which vertex is the dent?", "key")],
      Q("Which vertex of the second shape is pushed inward?", ["D", "B", "A", "C"], 0,
        ["Yes. At D the boundary turns back in toward the middle.",
         "B is the sharp tip: it points outward, it is not pushed in.",
         "A points outward, at the bottom of the shape.",
         "C points outward, at the top of the shape."], kind="spot"), pause=6),
    B("03", f"It is D. Now measure the angle inside the shape at D. It is {say_deg(D_ANGLE)}, "
            "more than a straight angle. An angle bigger than one hundred and eighty degrees is called a reflex angle.",
      arrow(angles=["D"]), [S("It is D", "The dent: D", "key"),
                            S("Now measure the angle inside the shape at D", f"Angle D = {D_ANGLE:g}°"),
                            S("is called a reflex angle", "More than 180°: reflex", "key")]),
])

ch2 = C(2, "CONVEX OR CONCAVE", "Classify by the interior angles and by the diagonals", [
    B("04", "Here is the rule. A quadrilateral is convex when every interior angle is less than one hundred and "
            "eighty degrees. It is concave, also called non-convex, when one interior angle is more than one "
            "hundred and eighty degrees.",
      pair({"angles": list("ABCD"), "verdict": True}, {"angles": list("ABCD"), "verdict": True}),
      [S("convex when every interior angle is less than", "Convex: every angle < 180°", "key"),
       S("It is concave, also called non-convex", "Concave: one angle > 180°", "key")]),
    B("05", "Be careful with thin shapes. Look at this long, flat one. Is it convex or concave?",
      {"kind": "shape", "points": THIN, "polygon": "ABCD", "frame": [-0.4, -0.6, 5.8, 1.5]},
      [S("Is it convex or concave", "Thin shape: convex or concave?", "key")],
      Q("Is this long, thin quadrilateral convex or concave?", ["convex", "concave"], 0,
        ["Yes. Every interior angle is still less than 180 degrees.",
         "Thin is not the same as dented: check each interior angle against 180 degrees."], kind="apply"),
      pause=6),
    B("06", "It is convex. It looks squashed, but measure the four angles: every one is less than one hundred and "
            "eighty degrees. Thinness does not matter. Only an inward corner makes a shape concave.",
      {"kind": "shape", "points": THIN, "polygon": "ABCD", "frame": [-0.4, -0.6, 5.8, 1.5], "angles": list("ABCD"),
       "verdict": True},
      [S("It is convex", "Thin, but convex", "key"),
       S("Thinness does not matter", "Only a dent makes it concave")]),
    B("07", "There is a second test, using the diagonals. In the convex shape both diagonals lie inside it, "
            "and they cross each other inside. In the concave shape, diagonal AC runs outside, "
            "and the two diagonals do not cross at all.",
      pair({"segments": [{"ends": "AC", "dashed": True}, {"ends": "BD", "dashed": True}], "meet": {"E": ["AC", "BD"]}},
           {"segments": [{"ends": "AC", "dashed": True, "role": "wrong"}, {"ends": "BD", "dashed": True}]}),
      [S("using the diagonals", "Second test: the diagonals"),
       S("they cross each other inside", "Convex: diagonals cross inside", "key"),
       S("diagonal AC runs outside", "Concave: AC outside, no crossing", "key")]),
])

ch3 = C(3, "THE TIPPING POINT", "Follow a quadrilateral from convex, through degenerate, to concave", [
    B("08", "Now an experiment. D will move toward the diagonal AC, then right past it. "
            "What do you predict will happen to the shape?",
      cv(segments=[{"ends": "AC", "dashed": True}]),
      [S("D will move toward the diagonal AC", "D moves across AC"),
       S("What do you predict will happen", "What happens?", "key")],
      Q("D moves toward diagonal AC and past it. What happens?",
        ["convex, then flat, then concave", "it stays convex", "it is never valid again"], 0,
        ["Yes. Three phases: convex, collapsed for a moment on the line, then concave.",
         "Watch the angle at D: once D passes AC it grows past 180 degrees.",
         "Past the line the boundary still does not cross itself, so the shape is valid again, just concave."],
        kind="predict"), pause=7),
    B("09", "Watch the angle at D. Before D reaches the line, the shape is convex, and the angle grows. "
            "Exactly on the line, C, D and A are in a row, and the shape has collapsed. "
            "After D crosses, the angle is more than one hundred and eighty degrees, and the shape is concave.",
      cv(segments=[{"ends": "AC", "dashed": True}], move={"D": [[1.5, 2.2], [2.3, 1.6], [3.0, 1.4]]},
         readout=["D"], verdict=True),
      [S("Before D reaches the line", "Before the line: convex"),
       S("Exactly on the line", "On the line: collapsed", "key"),
       S("After D crosses", "Past the line: concave", "key")]),
    B("10", "So there are three phases. Before the line, convex. On the line, not a quadrilateral at all. "
            "Past the line, concave. And if D went so far that two sides crossed, "
            "that would be a different failure, self-intersecting, not merely concave.",
      {"kind": "shape", "panels": [
          {"points": dict(CV, D=[1.5, 2.2]), "polygon": "ABCD", "verdict": True, "caption": "before",
           "key": "before", "segments": [{"ends": "AC", "dashed": True}]},
          {"points": dict(CV, D=[2.3, 1.6]), "polygon": "ABCD", "verdict": True, "caption": "on the line",
           "key": "on"},
          {"points": dict(CV, D=[3.0, 1.4]), "polygon": "ABCD", "verdict": True, "caption": "past",
           "key": "past", "segments": [{"ends": "AC", "dashed": True}]}]},
      [S("So there are three phases", "Three phases", "key"),
       S("that would be a different failure", "Sides crossing: another failure")]),
])

ch4 = C(4, "ANGLE SUM", "Use the 360 degree angle sum, counting a reflex angle", [
    B("11", "Add up the four interior angles of a quadrilateral and you always get three hundred and sixty degrees. "
            "Here is why. The diagonal AC splits this convex shape into two triangles. "
            "The angles of each triangle add up to one hundred and eighty degrees, and two triangles make three "
            "hundred and sixty.",
      cv(angles=list("ABCD"), segments=[{"ends": "AC", "dashed": True}],
         fills=[{"poly": "ABC", "role": "given"}, {"poly": "ACD", "role": "result"}], angle_sum=True),
      [S("you always get three hundred and sixty degrees", "Angle sum = 360°", "key"),
       S("splits this convex shape into two triangles", "Two triangles"),
       S("two triangles make three hundred and sixty", "2 × 180° = 360°", "key")]),
    B("12", "It works for the concave shape too, as long as we count the reflex angle at D. "
            "Here the diagonal BD lies inside, and it splits the shape into triangles ABD and BCD. "
            "Two triangles again, so three hundred and sixty degrees.",
      arrow(angles=list("ABCD"), segments=[{"ends": "BD", "dashed": True}],
            fills=[{"poly": "ABD", "role": "given"}, {"poly": "BCD", "role": "result"}], angle_sum=True),
      [S("as long as we count the reflex angle at D", "Count the reflex angle"),
       S("splits the shape into triangles ABD and BCD", "Triangles ABD and BCD"),
       S("so three hundred and sixty degrees", "Still 360°", "key")]),
    B("13", f"Your turn. The angles at A, B and C are {known[0]:g}, {known[1]:g} and {known[2]:g} degrees. "
            "What is the interior angle at D?",
      arrow(angles=["A", "B", "C", {"at": "D", "value": "?", "role": "unknown"}]),
      [S("What is the interior angle at D", "Angle D = ?", "key")],
      Q("A, B and C measure " + ", ".join(f"{k:g}°" for k in known) + ". What is the interior angle at D?",
        [f"{D_ANGLE:g}°", f"{OUTSIDE:g}°", f"{TRIANGLE:g}°"], 0,
        [f"Yes. 360 minus {sum(known):g} leaves {D_ANGLE:g} degrees: a reflex angle.",
         f"{OUTSIDE:g} degrees is the angle on the OUTSIDE of the dent. The interior angle is the one inside.",
         f"That uses 180 degrees, the triangle's sum. A quadrilateral's angles add to 360."]), pause=8),
    B("14", f"Three hundred and sixty minus {sum(known):g} leaves {say_deg(D_ANGLE)}. It is more than one hundred "
            "and eighty, so the angle at D is reflex, and the shape is concave.",
      arrow(angles=list("ABCD"), angle_sum=True, verdict=True),
      [S("Three hundred and sixty minus", f"360° − {sum(known):g}° = {D_ANGLE:g}°", "math"),
       S("the shape is concave", "Reflex at D: concave", "key")]),
])

ch5 = C(5, "IN SHORT", "Recall the convexity tests and the angle sum", [
    B("15", "So, in short. A convex quadrilateral has every interior angle below one hundred and eighty degrees, "
            "and its diagonals cross inside it. A concave one has a reflex angle at its dent. "
            "On the way from one to the other, the shape collapses for a moment. "
            "And the four interior angles always add up to three hundred and sixty degrees.",
      pair({"verdict": True, "angles": list("ABCD"), "angle_values": False},
           {"verdict": True, "angles": list("ABCD"), "angle_values": False}),
      [S("every interior angle below one hundred and eighty degrees", "Convex: all angles < 180°"),
       S("A concave one has a reflex angle", "Concave: one reflex angle"),
       S("the shape collapses for a moment", "In between: collapsed"),
       S("always add up to three hundred and sixty degrees", "Angle sum: 360°", "key")]),
], role="recap")

L = lesson("Quadrilaterals 3: convex and concave", [ch1, ch2, ch3, ch4, ch5])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u3.json")
