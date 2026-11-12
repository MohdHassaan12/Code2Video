"""Unit 7: medians and the centroid (pack section 7, A to C). One triangle, one worked example (GD = 10 cm, so
AG = 20 cm), and the triangle stretched while the ratio AG : GD is read off the picture and stays 2 : 1."""
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G

T = {"A": [1.5, 4.2], "B": [0, 0], "C": [6, 0]}
MID = {"D": "BC", "E": "CA", "F": "AB"}
F = [-0.6, -0.6, 6.6, 4.8]
MEDIANS = [{"ends": "AD", "role": "result"}, {"ends": "BE", "role": "given"}, {"ends": "CF", "role": "given"}]
MEET = {"G": ["AD", "BE"]}

m = G.Model({"points": T, "midpoints": MID, "meet": MEET})
SCALE = 10 / m.length("GD")                       # one unit of the drawing in cm, so GD reads 10 cm
assert abs(m.length("AG") / m.length("GD") - 2) < 1e-9
H = [T["A"][0], 0.0]                                # foot of the altitude from A (BC is the x-axis)


def tri(**more):
    spec = {"kind": "shape", "points": T, "polygon": "ABC", "frame": F}
    spec.update(more)
    return spec


def cand(segment, extra, caption, key, more=None):
    spec = {"points": dict(T, **extra), "polygon": "ABC", "segments": [segment], "caption": caption, "key": key}
    spec.update(more or {})
    return spec


CANDIDATES = {"kind": "shape", "panels": [
    cand({"ends": "AH", "role": "unknown"}, {"H": H}, "segment 1", "segment 1",
         {"angles": [{"at": "H", "from": "C", "to": "A", "role": "given", "value": False}], "hide_points": ["H"]}),
    cand({"ends": "AD", "role": "unknown"}, {}, "segment 2", "segment 2",
         {"midpoints": {"D": "BC"}, "equal": [["BD", "DC"]], "hide_points": ["D"]}),
    cand({"ends": "DK", "role": "unknown"}, {"D": [3.0, 0.0], "K": [3.0, 3.2]}, "segment 3", "segment 3",
         {"equal": [["BD", "DC"]], "angles": [{"at": "D", "from": "C", "to": "K", "role": "given", "value": False}],
          "hide_points": ["D", "K"]}),
]}

ch1 = C(1, "MEDIANS", "Know what a median is and tell it from other segments", [
    B("01", "A median joins a corner of a triangle to the midpoint of the opposite side. Here, D is the midpoint "
            "of BC, so BD equals DC. The segment from A to D is a median.",
      tri(midpoints={"D": "BC"}, equal=[["BD", "DC"]], segments=[{"ends": "AD", "role": "result"}]),
      [S("A median joins a corner", "Median: corner to opposite midpoint", "key"),
       S("D is the midpoint of BC", "D: midpoint of BC"),
       S("The segment from A to D is a median", "AD is a median", "key")]),
    B("02", "Three segments are drawn from this triangle. Only one of them is a median. Which one?",
      CANDIDATES,
      [S("Only one of them is a median", "One of these is a median"),
       S("Which one", "Which one?", "key")],
      Q("Which segment is a median?", ["segment 2", "segment 1", "segment 3"], 0,
        ["Yes. It starts at the corner A and ends at D, the midpoint of the opposite side.",
         "That one meets BC at a right angle: it is an altitude. Its foot is not the midpoint of BC.",
         "That one crosses BC at its midpoint at a right angle, but it does not start at a corner."],
        kind="spot"), pause=8),
    B("03", "Segment two is the median: it starts at a corner and ends at a midpoint. Segment one is an altitude: "
            "it meets BC at a right angle, but not at the midpoint. Segment three is a perpendicular bisector: "
            "it does not start at a corner.",
      CANDIDATES,
      [S("Segment two is the median", "Segment 2: the median", "key", highlight="segment 2"),
       S("Segment one is an altitude", "Segment 1: an altitude", highlight="segment 1"),
       S("Segment three is a perpendicular bisector", "Segment 3: a perpendicular bisector", highlight="segment 3")]),
    B("04", "Every triangle has three medians, one from each corner. Draw the other two, from B and from C. "
            "All three meet at one point, G. That point is called the centroid.",
      tri(midpoints=MID, equal=[["BD", "DC"], ["CE", "EA"], ["AF", "FB"]], segments=MEDIANS, meet=MEET),
      [S("Every triangle has three medians", "Three medians, one per corner"),
       S("Draw the other two", "Medians BE and CF"),
       S("All three meet at one point", "They meet at G", "key"),
       S("That point is called the centroid", "G: the centroid", "key")]),
])

ch2 = C(2, "THE 2 : 1 RATIO", "Use AG : GD = 2 : 1 in both directions", [
    B("05", "The centroid cuts each median in the ratio two to one, measured from the corner. "
            "On the median AD, AG is twice GD. Here GD is ten centimetres, and AG is twenty.",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET, readout=["AG", "GD", "AG:GD"], unit="cm", unit_scale=SCALE),
      [S("in the ratio two to one", "AG : GD = 2 : 1", "key"),
       S("measured from the corner", "The longer part touches the corner"),
       S("Here GD is ten centimetres", "GD = 10 cm, AG = 20 cm")]),
    B("06", "Your turn. In another triangle, GD on a median is ten centimetres. How long is AG?",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET, readout=["GD"], unit="cm", unit_scale=SCALE),
      [S("GD on a median is ten centimetres", "GD = 10 cm"),
       S("How long is AG", "AG = ?", "key")],
      Q("G is the centroid and GD = 10 cm. How long is AG?", ["20 cm", "5 cm", "30 cm"], 0,
        ["Yes. The part from the corner is the longer one: AG = 2 × 10 = 20 cm.",
         "That halves GD, which puts the ratio the wrong way round. The part touching the corner is longer.",
         "30 cm is the whole median AD. AG is only the part from A to G."]), pause=8),
    B("07", "AG is twenty centimetres: the part from the corner is the longer one, so double ten. Now turn it "
            "round. If AG is twenty centimetres, how long is GD?",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET, readout=["AG"], unit="cm", unit_scale=SCALE),
      [S("double ten", "AG = 2 × 10 = 20 cm", "key"),
       S("Now turn it round", "Now the other way"),
       S("how long is GD", "AG = 20 cm, GD = ?", "key")],
      Q("G is the centroid and AG = 20 cm. How long is GD?", ["10 cm", "40 cm", "20 cm"], 0,
        ["Yes. GD is the shorter part: half of AG, so 10 cm.",
         "That doubles AG, so the ratio is the wrong way round. GD is the shorter part.",
         "AG and GD are not equal: AG is twice GD."]), pause=8),
    B("08", "GD is ten centimetres, half of AG. So the whole median AD is thirty centimetres: "
            "two parts from the corner to G, and one part from G to the side.",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET, readout=["AG", "GD"], unit="cm", unit_scale=SCALE),
      [S("GD is ten centimetres", "GD = 20 ÷ 2 = 10 cm", "key"),
       S("the whole median AD is thirty centimetres", "AD = 20 + 10 = 30 cm"),
       S("two parts from the corner to G", "Three equal parts: two, then one")]),
])

ch3 = C(3, "STRETCH THE TRIANGLE", "See that the ratio stays 2 : 1 when the triangle changes shape", [
    B("09", "Predict first. If we drag corner A and stretch the triangle, will AG to GD still be two to one?",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET, readout=["AG:GD"]),
      [S("Predict first", "Predict"),
       S("will AG to GD still be two to one", "Still 2 : 1?", "key")],
      Q("If we stretch the triangle, will AG : GD still be 2 : 1?",
        ["Yes, it stays 2 : 1", "No, it changes with the shape", "Only for an equilateral triangle"], 0,
        ["Let us watch and see if the picture agrees.",
         "The lengths change, but watch the ratio as the triangle stretches.",
         "Our triangle is not equilateral, and it is already 2 : 1. Watch it stretch."], kind="predict"), pause=7),
    B("10", "Watch A move. The midpoints move, the medians move, and G moves with them. AG and GD both change "
            "length, but AG is always twice GD. The ratio stays two to one.",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET, readout=["AG", "GD", "AG:GD"], unit="cm", unit_scale=SCALE,
          move={"A": [[4.8, 4.6], [5.2, 2.2], [1.5, 4.2]]}),
      [S("Watch A move", "A moves"),
       S("G moves with them", "The medians and G follow"),
       S("AG and GD both change length", "Both lengths change"),
       S("The ratio stays two to one", "AG : GD stays 2 : 1", "key")]),
    B("11", "The lengths changed and the ratio did not. Now one more, on your own. A median is eighteen "
            "centimetres long. How far is the centroid from the corner?",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET),
      [S("The lengths changed and the ratio did not", "Lengths change; the ratio does not", "key"),
       S("A median is eighteen centimetres long", "Median AD = 18 cm"),
       S("How far is the centroid from the corner", "AG = ?", "key")],
      Q("A median AD is 18 cm long and G is the centroid. How long is AG?", ["12 cm", "9 cm", "6 cm"], 0,
        ["Yes. Split 18 into three equal parts of 6: AG is two of them, 12 cm.",
         "That splits the median in half. The centroid splits it two to one, not one to one.",
         "6 cm is GD, the shorter part. AG is the part from the corner: two parts, 12 cm."]), pause=9),
    B("12", "Twelve centimetres. Eighteen splits into three parts of six. AG takes two of them, and GD takes one.",
      tri(midpoints=MID, segments=MEDIANS, meet=MEET),
      [S("Eighteen splits into three parts of six", "18 ÷ 3 = 6 cm a part"),
       S("AG takes two of them", "AG = 2 × 6 = 12 cm", "key"),
       S("GD takes one", "GD = 6 cm")]),
])

ch4 = C(4, "IN SHORT", "Recall medians, the centroid and the ratio", [
    B("13", "So, a median joins a corner to the midpoint of the opposite side. The three medians meet at the "
            "centroid. And the centroid cuts every median two to one, with the longer part at the corner, "
            "whatever the shape of the triangle.",
      tri(midpoints=MID, equal=[["BD", "DC"], ["CE", "EA"], ["AF", "FB"]], segments=MEDIANS, meet=MEET,
          readout=["AG:GD"]),
      [S("a median joins a corner to the midpoint", "Median: corner to midpoint"),
       S("The three medians meet at the centroid", "Medians meet at the centroid G"),
       S("the centroid cuts every median two to one", "AG : GD = 2 : 1", "key"),
       S("whatever the shape of the triangle", "For every triangle")]),
], role="recap")

L = lesson("Quadrilaterals 7: medians and the centroid", [ch1, ch2, ch3, ch4])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u7.json")
