"""Unit 2: what makes a four-sided shape break (pack section 2, A to C)."""
import sys
from common import B, C, Q, S, lesson, write

P = {"A": [0, 0], "B": [5, 0.4], "C": [5.6, 3.6], "D": [0.6, 3.0]}
F = [-0.6, -0.6, 7.0, 4.2]
TRI = {"A": [0, 0], "B": [4, 0], "C": [1.5, 3]}
TF = [-2.6, -2.2, 6.2, 5.0]
TESTS = {"D1": [1.8, 1.0], "D2": [-0.6, 2.2], "D3": [2.0, -1.2], "D4": [3.6, 2.2], "D5": [-1.8, -1.4],
         "D6": [5.5, -0.8], "D7": [1.4, 4.6]}


def quad(**more):
    spec = {"kind": "shape", "points": P, "polygon": "ABCD", "frame": F}
    spec.update(more)
    return spec


def flat(**more):
    spec = {"kind": "shape", "points": P, "polygon": "ABCD", "view": "oblique"}
    spec.update(more)
    return spec


def puzzle(**more):
    spec = {"kind": "shape", "points": TRI, "polygon": "ABC", "lines": ["AB", "BC", "CA"], "frame": TF}
    spec.update(more)
    return spec


ch1 = C(1, "THREE CHECKS", "Know the three conditions a valid quadrilateral must meet", [
    B("01", "Four dots joined in order do not always make a quadrilateral. Three things can still go wrong. "
            "So a valid quadrilateral has to pass three checks. First, all four points lie on one flat plane. "
            "Second, the shape does not collapse onto a straight line. Third, the boundary never crosses itself.",
      quad(), [S("Three things can still go wrong", "Three things can go wrong"),
               S("all four points lie on one flat plane", "1. One flat plane", "key"),
               S("does not collapse onto a straight line", "2. No collapse", "key"),
               S("the boundary never crosses itself", "3. No crossing", "key")]),
])

ch2 = C(2, "OFF THE PLANE", "See why four points must be coplanar", [
    B("02", "Here is ABCD, lying flat on a sheet of paper. Before anything moves, make a prediction. "
            "If I lift D straight up off the paper, which check will fail?",
      flat(), [S("lying flat on a sheet of paper", "ABCD on a flat sheet"),
               S("which check will fail", "Lift D: which check fails?", "key")],
      Q("If D is lifted off the paper, which check fails?", ["one flat plane", "no collapse", "no crossing"], 0,
        ["Yes. A, B and C stay on the paper and D does not, so the four points are no longer on one plane.",
         "Nothing collapses: no three corners end up on one straight line.",
         "Look from above: the sides do not cut through each other."], kind="predict"), pause=6),
    B("03", "Watch. D rises above the sheet. A, B and C are still on the paper, but D is not. "
            "The four sides still join up, yet they no longer bound a flat region. "
            "So this is not a plane quadrilateral. It fails the first check.",
      flat(lift={"D": 1.6}), [S("D rises above the sheet", "D lifted off the plane"),
                              S("they no longer bound a flat region", "No flat region inside"),
                              S("It fails the first check", "Fails check 1: one plane", "key")]),
])

ch3 = C(3, "COLLAPSE", "Recognise a degenerate quadrilateral", [
    B("04", "Back on the flat page. Predict again. I will slide D until it lands exactly on the line from C to A. "
            "What happens to the shape at that moment?",
      quad(segments=[{"ends": "AC", "dashed": True}]),
      [S("lands exactly on the line from C to A", "D onto line CA: what happens?", "key")],
      Q("What happens when D lands on the line from C to A?",
        ["it collapses to a triangle", "it stays a quadrilateral", "two sides cross"], 0,
        ["Yes. C, D and A are then in one straight line, so the corner at D disappears.",
         "Count real corners: at D the boundary goes straight on, so there is no corner there.",
         "No sides cut through each other; D simply lies on the line between C and A."], kind="predict"), pause=6),
    B("05", "Watch D slide toward that line. Just before it arrives, we still have four corners, and the angle at D "
            "is close to a straight angle. The moment D lands on the line, C, D and A are in one straight line. "
            "The angle at D is one hundred and eighty degrees, and the shape is really triangle ABC.",
      quad(segments=[{"ends": "AC", "dashed": True}], move={"D": [[1.8, 2.6], [2.8, 1.8]]}, readout=["D"],
           verdict=True),
      [S("Watch D slide toward that line", "D slides toward line CA"),
       S("The moment D lands on the line", "D on the line: corner gone", "key")]),
    B("06", "We call this degenerate. It has collapsed. So the second check is this: no three vertices in a row "
            "on the boundary may lie on one straight line.",
      quad(points=dict(P, D=[2.8, 1.8]), verdict=True, roles={"CD": "wrong", "DA": "wrong"}),
      [S("We call this degenerate", "Degenerate: collapsed", "key"),
       S("no three vertices in a row", "Check 2: no three in a row on a line", "key")]),
])

ch4 = C(4, "CROSSING", "Recognise a self-intersecting boundary", [
    B("07", "Third check. Start with ABCD again and move D to the right. First it pushes into the shape and makes "
            "a dent. Then it goes right past side BC. Now side DA cuts through side BC, at a point that is not a "
            "corner. The boundary crosses itself.",
      quad(move={"D": [[2.6, 2.8], [3.6, 1.6], [7.0, 2.8]]}, verdict=True),
      [S("move D to the right", "D moves right"),
       S("makes a dent", "A dent: still valid"),
       S("goes right past side BC", "Past BC: sides cross", "key")]),
    B("08", "Here the crossing is marked. A boundary that crosses itself is called self-intersecting, "
            "and it is not a quadrilateral. That is the third check.",
      quad(points=dict(P, D=[7.0, 2.8]), verdict=True),
      [S("is called self-intersecting", "Self-intersecting", "key"),
       S("That is the third check", "Fails check 3: no crossing")]),
    B("09", "Now you try. Look at this shape. A, B and C sit on the bottom edge, and D is above. "
            "Which check does it fail?",
      {"kind": "shape", "points": {"A": [0, 0], "B": [2.5, 0], "C": [5, 0], "D": [2, 3]}, "polygon": "ABCD",
       "frame": [-0.6, -0.6, 5.6, 3.6]},
      [S("Which check does it fail", "Which check fails?", "key")],
      Q("Which check does this shape fail?", ["no collapse", "no crossing", "one flat plane"], 0,
        ["Yes. A, B and C lie on one straight line, so there is no corner at B.",
         "Trace the boundary: no side cuts through another.",
         "It is drawn on the flat page, so all four points share one plane."]), pause=7),
    B("10", "It fails the collapse check. A, B and C lie on one straight line, so the angle at B is one hundred "
            "and eighty degrees. The shape is really triangle ACD.",
      {"kind": "shape", "points": {"A": [0, 0], "B": [2.5, 0], "C": [5, 0], "D": [2, 3]}, "polygon": "ABCD",
       "frame": [-0.6, -0.6, 5.6, 3.6], "verdict": True, "roles": {"AB": "wrong", "BC": "wrong"}},
      [S("It fails the collapse check", "Collapsed at B", "key"),
       S("The shape is really triangle ACD", "Really triangle ACD")]),
])

ch5 = C(5, "WHERE CAN D GO?", "Apply all three checks to place a fourth vertex", [
    B("11", "Here is a puzzle. Start with triangle ABC. Draw the full lines through its sides, AB, BC and CA, "
            "running on forever in both directions. These three lines cut the flat page into seven regions.",
      puzzle(), [S("Start with triangle ABC", "Triangle ABC"),
                 S("Draw the full lines through its sides", "Three full lines"),
                 S("cut the flat page into seven regions", "Seven regions", "key")]),
    B("12", "We want a fourth point, D, so that ABCD is a valid quadrilateral with sides AB, BC, CD and DA. "
            "Predict before we test. In how many of the seven regions can D go?",
      puzzle(), [S("so that ABCD is a valid quadrilateral", "Place D: ABCD valid"),
                 S("In how many of the seven regions", "How many regions work?", "key")],
      Q("In how many of the seven regions can D go?", ["5", "7", "1", "3"], 0,
        ["Yes. Only the two regions across side AB and across side BC fail.",
         "Test the region across side AB: there CD cuts through AB.",
         "More than one works: inside the triangle gives a dented, concave shape that is still valid.",
         "Count again: the three regions past the corners all work, and so do two more."],
        kind="predict"), pause=8),
    B("13", "Let us test one point in each region by tracing the boundary: from A to B, to C, to D, and back to A. "
            "A green tick means the shape passes every check, a red cross means it fails.",
      puzzle(tests=TESTS), [S("test one point in each region", "Test one D per region"),
                            S("A green tick means", "Tick: valid. Cross: fails", "key")]),
    B("14", "Five regions work. Inside the triangle, D makes a dent, so ABCD is concave. Across side CA it is "
            "convex. Past each corner it is concave again. Only two regions fail. Across side AB, side CD cuts "
            "through AB. Across side BC, side DA cuts through BC.",
      puzzle(tests=TESTS), [S("Five regions work", "Five regions work", "key"),
                            S("Only two regions fail", "Two fail: sides cross", "key")]),
    B("15", "Here are those two failures side by side. In both, the boundary crosses itself. "
            "And one more case: if D sits exactly on one of the three lines, three vertices are in a row, "
            "and the shape collapses.",
      {"kind": "shape", "panels": [
          {"points": dict(TRI, D=TESTS["D3"]), "polygon": "ABCD", "caption": "D across AB", "key": "across side AB",
           "verdict": True},
          {"points": dict(TRI, D=TESTS["D4"]), "polygon": "ABCD", "caption": "D across BC", "key": "across side BC",
           "verdict": True}]},
      [S("the boundary crosses itself", "Both: boundary crosses", "key"),
       S("if D sits exactly on one of the three lines", "D on a line: collapse")]),
])

ch6 = C(6, "IN SHORT", "Recall the three checks", [
    B("16", "So, a quadrilateral needs more than four dots. All four points lie on one flat plane. "
            "No three vertices in a row lie on one line. And the boundary never crosses itself. "
            "Pass all three checks, and you have a quadrilateral.",
      quad(verdict=True), [S("All four points lie on one flat plane", "1. One flat plane"),
                           S("No three vertices in a row lie on one line", "2. No collapse"),
                           S("the boundary never crosses itself", "3. No crossing"),
                           S("Pass all three checks", "All three: a quadrilateral", "key")]),
], role="recap")

L = lesson("Quadrilaterals 2: what makes a shape break", [ch1, ch2, ch3, ch4, ch5, ch6])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u2.json")
