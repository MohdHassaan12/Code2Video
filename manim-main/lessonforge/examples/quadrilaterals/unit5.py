"""Unit 5: proofs of the parallelogram theorems (pack section 5, A to E). Proved in order, each step using only what
was proved before it (the pack: keep a proof-dependency graph, never cite an unproved result)."""
import math
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G

P = {"A": [0, 0], "B": [4.5, 0], "C": [6, 2.8], "D": [1.5, 2.8]}
F = [-0.6, -0.6, 6.6, 3.4]
DIAG = [{"ends": "AC", "dashed": True}, {"ends": "BD", "dashed": True}]
PAR = [["AB", "DC"], ["AD", "BC"]]

# two parallel lines and a transversal at exactly 70 degrees, so the quiz's 70 is the picture's 70
X = (2.0, 0.0)
c, s = math.cos(math.radians(70)), math.sin(math.radians(70))
Y = (X[0] + 2.4 / s * c, 2.4)
TR = {"P": [-0.5, 0], "Q": [6, 0], "R": [-0.5, 2.4], "S": [6, 2.4],
      "U": [X[0] - 1.1 * c, -1.1 * s], "V": [Y[0] + 1.1 * c, 2.4 + 1.1 * s], "X": list(X), "Y": list(Y)}
TF = [-0.6, -1.3, 6.1, 3.6]
assert abs(G.Model({"points": TR}).angle({"at": "X", "from": "Q", "to": "Y"})["value"] - 70) < 0.01
RH = {"A": [0, 0], "B": [3, 0], "C": [4.5, 3 * math.sin(math.radians(60))], "D": [1.5, 3 * math.sin(math.radians(60))]}
SQ = {"A": [0, 0], "B": [3, 0], "C": [3, 3], "D": [0, 3]}


def par(**more):
    spec = {"kind": "shape", "points": P, "polygon": "ABCD", "frame": F}
    spec.update(more)
    return spec


def ang(at, frm, to, role, value=False):
    return {"at": at, "from": frm, "to": to, "role": role, "value": value}


def tr(angles=(), **more):
    spec = {"kind": "shape", "points": TR, "segments": ["PQ", "RS", "UV"], "parallel": [["PQ", "RS"]],
            "hide_points": ["P", "Q", "R", "S", "U", "V"], "show_points": ["X", "Y"], "angles": list(angles),
            "frame": TF}
    spec.update(more)
    return spec


ch1 = C(1, "TWO TOOLS", "Use alternate and same-side interior angles", [
    B("01", "Every proof in this lesson uses two tools. Here are two parallel lines, and a third line crossing "
            "them. The angles on opposite sides of the crossing line, between the parallels, are alternate angles. "
            "They make a Z shape, and they are equal.",
      tr([ang("X", "Q", "Y", "given", None), ang("Y", "R", "X", "given", None)]),
      [S("two parallel lines", "Two parallel lines, one crossing line"),
       S("are alternate angles", "Alternate angles: a Z shape"),
       S("and they are equal", "Alternate angles are equal", "key")]),
    B("02", "Now take two angles on the same side of the crossing line, between the parallels. "
            "These same-side interior angles add up to one hundred and eighty degrees.",
      tr([ang("X", "Q", "Y", "given", None), ang("Y", "S", "X", "result", None)]),
      [S("same-side interior angles", "Same-side interior angles"),
       S("add up to one hundred and eighty degrees", "They add to 180°", "key")]),
    B("03", "Check yourself. One same-side interior angle is seventy degrees. What is the other one?",
      tr([ang("X", "Q", "Y", "given", None), {"at": "Y", "from": "S", "to": "X", "role": "unknown", "value": "?"}]),
      [S("What is the other one", "70° and ?", "key")],
      Q("One same-side interior angle is 70°. What is the other?", ["110°", "70°", "290°"], 0,
        ["Yes. Same-side interior angles add to 180°, and 180 − 70 = 110.",
         "Equal angles are the ALTERNATE ones. Same-side interior angles add to 180°.",
         "That would make the two add to 360°. Between parallels they add to 180°."]), pause=7),
    B("04", "It is one hundred and ten degrees, because seventy and one hundred and ten make one hundred and eighty. "
            "Our second tool is congruent triangles: when two triangles are congruent, all their matching sides "
            "and angles are equal.",
      tr([ang("X", "Q", "Y", "given", None), ang("Y", "S", "X", "result", None)]),
      [S("It is one hundred and ten degrees", "180° − 70° = 110°", "math"),
       S("Our second tool is congruent triangles", "Congruent triangles: matching parts equal", "key")]),
])

ch2 = C(2, "OPPOSITE SIDES ARE EQUAL", "Prove that a parallelogram's opposite sides are equal", [
    B("05", "Start with a parallelogram: AB is parallel to DC, and AD is parallel to BC. Draw the diagonal AC. "
            "Because AB is parallel to DC, angle BAC equals angle DCA: they are alternate angles.",
      par(parallel=PAR, segments=[{"ends": "AC", "role": "given"}],
          angles=[ang("A", "B", "C", "given"), ang("C", "D", "A", "given")]),
      [S("Start with a parallelogram", "Given: AB ∥ DC, AD ∥ BC"),
       S("Draw the diagonal AC", "Draw AC"),
       S("angle BAC equals angle DCA", "∠BAC = ∠DCA, alternate", "key")]),
    B("06", "Because AD is parallel to BC, angle BCA equals angle DAC, alternate angles again. "
            "Which congruence test do triangles ABC and CDA now meet?",
      par(parallel=PAR, segments=[{"ends": "AC", "role": "given"}],
          angles=[ang("A", "B", "C", "given"), ang("C", "D", "A", "given"),
                  ang("C", "B", "A", "result"), ang("A", "D", "C", "result")],
          fills=[{"poly": "ABC", "role": "given"}, {"poly": "CDA", "role": "result"}]),
      [S("angle BCA equals angle DAC", "∠BCA = ∠DAC"),
       S("Which congruence test", "Which test?", "key")],
      Q("Triangles ABC and CDA: which congruence test do they meet?", ["ASA", "SSS", "SAS"], 0,
        ["Yes. Two pairs of equal angles, and the side AC between them is shared.",
         "SSS needs three pairs of equal sides, and the equal sides are what we are trying to prove.",
         "SAS needs two pairs of equal sides. We know only one: AC, which is shared."]), pause=8),
    B("07", "ASA: two angles, and the side AC between them, which both triangles share. So the triangles are "
            "congruent, and their matching sides are equal: AB equals CD, and BC equals DA.",
      par(parallel=PAR, segments=[{"ends": "AC", "role": "given"}], equal=[["AB", "CD"], ["BC", "DA"]],
          fills=[{"poly": "ABC", "role": "given"}, {"poly": "CDA", "role": "result"}]),
      [S("ASA", "△ABC ≅ △CDA by ASA", "key"),
       S("AB equals CD, and BC equals DA", "So AB = CD, BC = DA", "key")]),
])

ch3 = C(3, "OPPOSITE ANGLES ARE EQUAL", "Prove that a parallelogram's opposite angles are equal", [
    B("08", "Now the angles. Angle A and angle B lie between the parallel sides AD and BC, on the same side of AB. "
            "So angle A plus angle B is one hundred and eighty degrees. In the same way, angle B plus angle C is "
            "one hundred and eighty degrees. What follows?",
      par(parallel=PAR, angles=["A", "B", "C"]),
      [S("angle A plus angle B is one hundred and eighty degrees", "∠A + ∠B = 180°", "math"),
       S("angle B plus angle C is", "∠B + ∠C = 180°", "math"),
       S("What follows", "So ...?", "key")],
      Q("∠A + ∠B = 180° and ∠B + ∠C = 180°. What follows?",
        ["∠A = ∠C", "∠A = ∠B", "∠B = 90°"], 0,
        ["Yes. Both sums are 180° and both contain ∠B, so what is left must be equal.",
         "∠A and ∠B add to 180°. They are equal only if both are 90°.",
         "Nothing says the angles are right angles. Look at what the two sums share."]), pause=8),
    B("09", "Angle A equals angle C. Both sums are one hundred and eighty, and both contain angle B. "
            "Take angle B away from each, and what is left is equal. In the same way, angle B equals angle D.",
      par(parallel=PAR, angles=list("ABCD"), equal_angles=[["A", "C"], ["B", "D"]]),
      [S("Angle A equals angle C", "∠A = ∠C", "key"),
       S("Take angle B away from each", "Take ∠B from both sums"),
       S("angle B equals angle D", "∠B = ∠D", "key")]),
])

ch4 = C(4, "DIAGONALS BISECT EACH OTHER", "Prove the diagonal theorem using only results already proved", [
    B("10", "Last theorem. The diagonals meet at E. We proved that AB equals CD in chapter two, so we may use it "
            "now. Alternate angles give angle BAE equals angle DCE, and angle ABE equals angle CDE.",
      par(parallel=PAR, equal=[["AB", "CD"]], segments=DIAG, meet={"E": ["AC", "BD"]},
          angles=[ang("A", "B", "E", "given"), ang("C", "D", "E", "given"),
                  ang("B", "E", "A", "result"), ang("D", "E", "C", "result")]),
      [S("We proved that AB equals CD in chapter two", "Already proved: AB = CD"),
       S("angle BAE equals angle DCE", "∠BAE = ∠DCE"),
       S("angle ABE equals angle CDE", "∠ABE = ∠CDE")]),
    B("11", "So triangles ABE and CDE are congruent by ASA. Their matching sides are equal: AE equals CE, and "
            "BE equals DE. E is the midpoint of both diagonals: they bisect each other. Notice the order. "
            "We used only facts proved earlier. Using the result to prove itself would be circular.",
      par(parallel=PAR, equal=[["AB", "CD"], ["AE", "EC"], ["BE", "ED"]], segments=DIAG, meet={"E": ["AC", "BD"]},
          fills=[{"poly": "ABE", "role": "given"}, {"poly": "CDE", "role": "result"}]),
      [S("congruent by ASA", "△ABE ≅ △CDE by ASA", "key"),
       S("AE equals CE, and BE equals DE", "AE = CE, BE = DE"),
       S("We used only facts proved earlier", "Only earlier results: no circle", "key")]),
])

ch5 = C(5, "CONVERSES", "Tell a converse from the original and test it", [
    B("12", "A converse swaps the if and the then. Theorem: if ABCD is a parallelogram, then its opposite sides "
            "are equal. Converse: if the opposite sides are equal, then ABCD is a parallelogram. That converse is "
            "true. We proved it in the last lesson, as test two.",
      par(equal=[["AB", "CD"], ["BC", "DA"]], parallel=PAR),
      [S("A converse swaps the if and the then", "Converse: swap if and then", "key"),
       S("Converse: if the opposite sides are equal", "If sides equal, then parallelogram"),
       S("That converse is true", "True: proved as test 2")]),
    B("13", "But a converse is not true just because the original is. Here is a true statement: if a "
            "quadrilateral is a square, then its four sides are equal. Now the converse: if a quadrilateral has "
            "four equal sides, must it be a square?",
      {"kind": "shape", "panels": [
          {"points": SQ, "polygon": "ABCD", "equal": [["AB", "BC", "CD", "DA"]], "caption": "square", "key": "square"},
          {"points": RH, "polygon": "ABCD", "equal": [["AB", "BC", "CD", "DA"]], "caption": "?", "key": "four equal"}]},
      [S("if a quadrilateral is a square", "Square ⇒ four equal sides: true"),
       S("must it be a square", "Four equal sides ⇒ square?", "key")],
      Q("If a quadrilateral has four equal sides, must it be a square?", ["No", "Yes"], 0,
        ["Right. A rhombus has four equal sides without right angles.",
         "Look for a counterexample: tilt the square and keep the sides the same length."], kind="apply"), pause=7),
    B("14", "No. This rhombus has four equal sides, but its angles are not right angles. One counterexample is "
            "enough to show a converse is false. So test every converse: prove it, or find a counterexample.",
      {"kind": "shape", "panels": [
          {"points": SQ, "polygon": "ABCD", "equal": [["AB", "BC", "CD", "DA"]], "angles": ["A"], "caption": "square",
           "key": "square"},
          {"points": RH, "polygon": "ABCD", "equal": [["AB", "BC", "CD", "DA"]], "angles": ["A"],
           "caption": "rhombus", "key": "rhombus"}]},
      [S("This rhombus has four equal sides", "A rhombus: four equal sides"),
       S("its angles are not right angles", "Not a square", "key"),
       S("prove it, or find a counterexample", "Prove it, or find a counterexample", "key")]),
])

ch6 = C(6, "IN SHORT", "Recall the proofs and their order", [
    B("15", "So, in a parallelogram, opposite sides are equal, by ASA on the diagonal. Opposite angles are equal, "
            "because same-side angles add to one hundred and eighty. And the diagonals bisect each other, "
            "using the equal sides we proved first. Each proof stands only on what came before it.",
      par(parallel=PAR, equal=[["AB", "CD"], ["BC", "DA"], ["AE", "EC"], ["BE", "ED"]], segments=DIAG,
          meet={"E": ["AC", "BD"]}),
      [S("opposite sides are equal", "Opposite sides equal: ASA"),
       S("Opposite angles are equal", "Opposite angles equal: 180° sums"),
       S("the diagonals bisect each other", "Diagonals bisect: uses the sides"),
       S("Each proof stands only on what came before it", "Each proof uses only earlier ones", "key")]),
], role="recap")

L = lesson("Quadrilaterals 5: proving the parallelogram theorems", [ch1, ch2, ch3, ch4, ch5, ch6])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u5.json")
