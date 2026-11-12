"""Unit 1: what a quadrilateral is, and its parts (pack section 1, A to D)."""
import sys
from common import B, C, Q, S, lesson, write

P = {"A": [0, 0], "B": [5, 0.4], "C": [5.6, 3.6], "D": [0.6, 3.0]}
F = [-0.6, -0.6, 6.2, 4.2]
SQ = {"A": [0, 0], "B": [3, 0], "C": [3, 3], "D": [0, 3]}
TRI = {"A": [0, 0], "B": [3.4, 0], "C": [1.4, 3]}
BOW = {"A": [0, 0], "B": [3, 3], "C": [3, 0], "D": [0, 3]}


def quad(**more):
    spec = {"kind": "shape", "points": P, "polygon": "ABCD", "frame": F}
    spec.update(more)
    return spec


def three(verdicts=False):
    def panel(points, poly, cap, key, verdict=None):
        p = {"points": points, "polygon": poly, "caption": cap, "key": key, "hide_points": list(points)}
        if verdicts and verdict:
            p["verdict"] = verdict
        return p
    return {"kind": "shape", "panels": [
        panel(SQ, "ABCD", "square", "square", "quadrilateral"),
        panel(TRI, "ABC", "triangle: 3 sides" if verdicts else "triangle", "triangle"),
        panel(BOW, "ABCD", "bow-tie", "bow-tie bow tie", True)]}


everyday = {"kind": "shape", "panels": [
    {"points": {"A": [0, 0], "B": [2, 0], "C": [2, 4], "D": [0, 4]}, "polygon": "ABCD", "caption": "phone screen",
     "key": "phone screen", "hide_points": ["A", "B", "C", "D"]},
    {"points": {"A": [0, 0], "B": [3, 0], "C": [3, 3], "D": [0, 3]}, "polygon": "ABCD", "caption": "floor tile",
     "key": "floor tile", "hide_points": ["A", "B", "C", "D"]},
    {"points": {"A": [0, 0], "B": [2.8, 0], "C": [2.8, 3.8], "D": [0, 3.8]}, "polygon": "ABCD",
     "caption": "notebook page", "key": "notebook page", "hide_points": ["A", "B", "C", "D"]}]}

ch1 = C(1, "FOUR STRAIGHT SIDES", "Recognise a quadrilateral and say what rules it out", [
    B("01", "Look at the outline of your phone screen. Now a floor tile, and a page of your notebook. "
            "Trace each outline with your finger. Every one of them is made of straight sides, and each has four.",
      everyday, [S("outline of your phone screen", "Everyday outlines"),
                 S("Every one of them is made of straight sides", "Straight sides only"),
                 S("each has four", "Four sides each", "key")]),
    B("02", "Here are three shapes: a square, a triangle and a bow-tie. Only one of them is a quadrilateral. "
            "Which one is it?",
      three(), [S("square, a triangle and a bow-tie", "Square, triangle, bow-tie")],
      Q("Which shape is a quadrilateral?", ["the square", "the triangle", "the bow-tie"], 0,
        ["Yes. Four straight sides that close up and never cross.",
         "Count its sides: a triangle has only three.",
         "It has four sides, but two of them cross in the middle. Watch what happens there."],
        kind="spot"), pause=7),
    B("03", "It is the square. The triangle has only three sides. The bow-tie does have four sides, "
            "but look at the middle. Two of its sides cross each other there, at a point that is not a corner. "
            "So its boundary crosses itself, and that rules it out.",
      three(verdicts=True), [S("triangle has only three sides", "Triangle: 3 sides"),
                             S("Two of its sides cross each other", "Bow-tie: sides cross", "key"),
                             S("that rules it out", "Not a quadrilateral")]),
    B("04", "So here is the definition we will use. A quadrilateral is a closed shape on a flat surface, "
            "made of four straight sides. The sides meet only at their ends, two at each corner, "
            "and no side crosses another.",
      quad(), [S("closed shape on a flat surface", "Closed, on a flat plane"),
               S("made of four straight sides", "Four straight sides", "key"),
               S("meet only at their ends", "Sides meet only at their ends"),
               S("no side crosses another", "No side crosses another", "key")]),
])

ch2 = C(2, "VERTICES AND SIDES", "Name vertices, sides, adjacent and opposite sides and angles", [
    B("05", "Let us give our shape names. This is quadrilateral ABCD. Its four corners, A, B, C and D, "
            "are called its vertices. One corner is a vertex.",
      quad(), [S("This is quadrilateral ABCD", "Quadrilateral ABCD", "key"),
               S("are called its vertices", "Corners are vertices"),
               S("One corner is a vertex", "One corner: a vertex")]),
    B("06", "Its sides are AB, BC, CD and DA. Read them in order and you walk around the boundary: "
            "from A to B, to C, to D, and back to A where you started.",
      quad(), [S("Its sides are AB, BC, CD and DA", "Sides: AB, BC, CD, DA", "key"),
               S("you walk around the boundary", "Walk around the boundary")]),
    B("07", "Now look at side AB and side BC. They both end at B. Two sides that share an endpoint are "
            "called adjacent sides.",
      quad(roles={"AB": "given", "BC": "given"}),
      [S("They both end at B", "AB and BC share B"),
       S("are called adjacent sides", "Adjacent sides share an endpoint", "key")]),
    B("08", "Side AB and side CD share no endpoint at all. They sit across from each other, so they are "
            "opposite sides. In the same way, BC and DA are opposite sides.",
      quad(roles={"AB": "given", "CD": "given"}),
      [S("share no endpoint at all", "AB and CD share no endpoint"),
       S("so they are opposite sides", "Opposite sides: no shared endpoint", "key"),
       S("BC and DA are opposite sides", "BC and DA: opposite too")]),
    B("09", "Your turn. Which side is opposite side BC?",
      quad(roles={"BC": "unknown"}), [S("Which side is opposite side BC", "Opposite BC is ...?", "key")],
      Q("Which side is opposite BC?", ["DA", "AB", "CD"], 0,
        ["Yes. BC ends at B and C; DA ends at D and A, so they share nothing.",
         "AB shares the endpoint B with BC, so AB is adjacent to it.",
         "CD shares the endpoint C with BC, so CD is adjacent to it."]), pause=6),
    B("10", "It is DA. BC uses the points B and C, and DA uses D and A, so they share no endpoint. "
            "AB and CD both touch BC, so they are its adjacent sides.",
      quad(roles={"BC": "given", "DA": "result"}),
      [S("It is DA", "Opposite BC: DA", "key"), S("they are its adjacent sides", "AB, CD: adjacent to BC")]),
    B("11", "Each vertex also has an angle inside the shape: angle A, angle B, angle C and angle D. "
            "Angle A and angle C are opposite angles. Angle A and angle B are adjacent angles.",
      quad(angles=["A", "B", "C", "D"], angle_values=False),
      [S("Each vertex also has an angle", "Four interior angles"),
       S("Angle A and angle C are opposite angles", "A and C: opposite angles", "key"),
       S("Angle A and angle B are adjacent angles", "A and B: adjacent angles")]),
])

ch3 = C(3, "DIAGONALS AND NAMES", "Find both diagonals and name a quadrilateral in boundary order", [
    B("12", "Now join A to C. A and C are not next to each other on the boundary, so AC is not a side. "
            "A segment like this, joining two vertices that are not neighbours, is called a diagonal.",
      quad(segments=[{"ends": "AC", "dashed": True, "role": "given"}]),
      [S("join A to C", "Join A to C"), S("so AC is not a side", "AC is not a side"),
       S("is called a diagonal", "AC is a diagonal", "key")]),
    B("13", "Before I draw it, predict. What is the other diagonal?",
      quad(segments=[{"ends": "AC", "dashed": True, "role": "given"}]),
      [S("What is the other diagonal", "The other diagonal is ...?", "key")],
      Q("What is the other diagonal?", ["BD", "AB", "CA"], 0,
        ["Yes. B and D are the two vertices left that are not neighbours.",
         "AB is a side: A and B are neighbours on the boundary.",
         "CA is the same diagonal as AC, read backwards."], kind="predict"), pause=6),
    B("14", "It is BD. It joins the other two vertices that are not neighbours. "
            "Every quadrilateral has exactly two diagonals.",
      quad(segments=[{"ends": "AC", "dashed": True, "role": "given"}, {"ends": "BD", "dashed": True, "role": "result"}]),
      [S("It is BD", "Other diagonal: BD", "key"), S("exactly two diagonals", "Exactly two diagonals", "key")]),
    B("15", "One more thing: the name. We name a quadrilateral by walking around its boundary in order. "
            "ABCD works. So does BCDA, and so does DCBA, walking the other way. But look what ACBD does. "
            "It jumps along a diagonal, and the path it draws crosses itself.",
      {"kind": "shape", "panels": [
          {"points": P, "polygon": "ABCD", "caption": "ABCD: walks the boundary", "key": "abcd works"},
          {"points": P, "polygon": "ACBD", "caption": "ACBD: jumps across", "key": "acbd jumps", "verdict": True}]},
      [S("walking around its boundary in order", "Name = boundary order", "key"),
       S("So does BCDA", "BCDA and DCBA work too"),
       S("It jumps along a diagonal", "ACBD jumps: wrong name", "key")]),
    B("16", "Try one. Is ADCB a correct name for our quadrilateral?",
      quad(), [S("Is ADCB a correct name", "ADCB: a correct name?", "key")],
      Q("Is ADCB a correct name for ABCD?", ["Yes", "No"], 0,
        ["Yes. A to D, D to C, C to B, B to A: every step is a side, walked the other way.",
         "Check each step: AD, DC, CB and BA are all sides, so the walk goes round the boundary."]), pause=6),
    B("17", "Yes, it is. A to D is a side, D to C is a side, C to B is a side, and B back to A is a side. "
            "ADCB walks the same boundary, only in the other direction.",
      quad(roles={"DA": "result", "CD": "result", "BC": "result", "AB": "result"}),
      [S("A to D is a side", "AD, DC, CB, BA: all sides"),
       S("only in the other direction", "Same boundary, other way", "key")]),
])

ch4 = C(4, "CHECK YOURSELF", "Classify shapes and give the reason", [
    B("18", "Let us check what you have learnt. Here are the three shapes again. Which one has four sides "
            "and still breaks our definition?",
      three(), [S("Here are the three shapes again", "Square, triangle, bow-tie")],
      Q("Which shape has four sides but is not a quadrilateral?", ["the bow-tie", "the square", "the triangle"], 0,
        ["Yes. Its sides cross at a point that is not a corner.",
         "The square follows every rule: four sides, meeting only at their ends.",
         "The triangle fails for another reason: it has three sides, not four."], kind="recall"), pause=7),
    B("19", "It is the bow-tie. Its sides cross between the corners, and our definition says sides may meet "
            "only at their ends.",
      three(verdicts=True), [S("It is the bow-tie", "The bow-tie", "key"),
                             S("may meet only at their ends", "Sides meet only at ends")]),
    B("20", "So, in short. A quadrilateral has four vertices, four sides, four angles and two diagonals. "
            "Adjacent sides share a vertex. Opposite sides do not. And we name the shape by walking around "
            "its boundary in order.",
      quad(segments=[{"ends": "AC", "dashed": True}, {"ends": "BD", "dashed": True}], angles=["A", "B", "C", "D"],
           angle_values=False),
      [S("four vertices, four sides, four angles and two diagonals", "4 vertices, 4 sides, 4 angles, 2 diagonals", "key"),
       S("Adjacent sides share a vertex", "Adjacent: share a vertex"),
       S("Opposite sides do not", "Opposite: share none"),
       S("walking around its boundary in order", "Name in boundary order", "key")]),
], role="recap")

L = lesson("Quadrilaterals 1: what a quadrilateral is", [ch1, ch2, ch3, ch4])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u1.json")
