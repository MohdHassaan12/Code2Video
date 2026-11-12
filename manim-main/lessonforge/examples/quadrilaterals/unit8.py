"""Unit 8: the midpoint theorem for quadrilaterals (Varignon). The pack has only a production brief here; the outcome
was agreed with the owner: joining the midpoints of any quadrilateral gives a parallelogram, proved with the midpoint
theorem of unit 6 in triangles ABC and ADC. Predict, prove, deform ABCD (convex, then concave) and apply it."""
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G

Q4 = {"A": [0.4, 3.6], "B": [0, 0], "C": [6.5, 0.6], "D": [5.2, 4.4]}
MID = {"P": "AB", "Q": "BC", "R": "CD", "S": "DA"}
F = [-0.7, -0.7, 8.1, 5.0]
INNER = [{"ends": "PQ", "role": "result"}, {"ends": "QR", "role": "result"}, {"ends": "RS", "role": "result"},
         {"ends": "SP", "role": "result"}]
HALVES = [["AP", "PB"], ["BQ", "QC"], ["CR", "RD"], ["DS", "SA"]]
AC = {"ends": "AC", "role": "given", "dashed": True}
BD = {"ends": "BD", "role": "given", "dashed": True}
MOVE = {"D": [[3.0, 1.6], [7.4, 3.6], [5.2, 4.4]]}

# the claim, checked on the coordinates before anything is filmed: PQRS has both pairs of opposite sides parallel
for D in ([5.2, 4.4], [3.0, 1.6], [7.4, 3.6]):
    m = G.Model({"points": dict(Q4, D=D), "midpoints": MID, "polygon": "PQRS"})
    assert G.parallelogram_tests(m)["both_pairs_parallel"], D
    assert abs(m.length("PQ") - m.length("AC") / 2) < 1e-9 and abs(m.length("QR") - m.length("BD") / 2) < 1e-9


def quad(**more):
    spec = {"kind": "shape", "points": Q4, "polygon": "ABCD", "midpoints": MID, "frame": F}
    spec.update(more)
    return spec


ch1 = C(1, "PREDICT", "Predict what shape the midpoints of a quadrilateral make", [
    B("01", "Here is a quadrilateral ABCD, with no equal sides and no parallel sides. Mark the midpoint of each "
            "side: P on AB, Q on BC, R on CD, and S on DA. Now join them in order, P to Q to R to S.",
      quad(equal=HALVES, segments=INNER),
      [S("no equal sides and no parallel sides", "ABCD: any quadrilateral"),
       S("Mark the midpoint of each side", "P, Q, R, S: midpoints", "key"),
       S("join them in order", "Join PQRS", "key")]),
    B("02", "ABCD is a shape with nothing special about it. What kind of shape do you think PQRS is?",
      quad(equal=HALVES, segments=INNER),
      [S("nothing special about it", "Nothing special about ABCD"),
       S("What kind of shape do you think PQRS is", "PQRS is a … ?", "key")],
      Q("P, Q, R, S are the midpoints of the sides of ABCD. What kind of shape is PQRS?",
        ["A parallelogram", "It depends on ABCD", "A rectangle"], 0,
        ["That is the prediction. Now we prove it, so we know it is not luck.",
         "A fair guess, since ABCD is irregular. Watch the proof: it never uses anything special about ABCD.",
         "Its angles are not right angles here. Look at the sides instead: which pairs look parallel?"],
        kind="predict"), pause=8),
])

ch2 = C(2, "THE PROOF", "Prove PQRS is a parallelogram with the midpoint theorem", [
    B("03", "Draw the diagonal AC. It cuts ABCD into two triangles, ABC and ADC. Look at triangle ABC first. "
            "P is the midpoint of AB and Q is the midpoint of BC.",
      quad(equal=[["AP", "PB"], ["BQ", "QC"]], segments=[AC, {"ends": "PQ", "role": "result"}],
           fills=[{"poly": "ABC", "role": "given"}]),
      [S("Draw the diagonal AC", "Draw diagonal AC", "key"),
       S("two triangles, ABC and ADC", "Two triangles: ABC and ADC"),
       S("Look at triangle ABC first", "In triangle ABC"),
       S("Q is the midpoint of BC", "P, Q: midpoints of AB, BC")]),
    B("04", "So by the midpoint theorem from unit six, PQ is parallel to AC, and PQ is half of AC.",
      quad(equal=[["AP", "PB"], ["BQ", "QC"]], segments=[AC, {"ends": "PQ", "role": "result"}],
           parallel=[["PQ", "AC"]], fills=[{"poly": "ABC", "role": "given"}]),
      [S("by the midpoint theorem", "Midpoint theorem"),
       S("PQ is parallel to AC", "PQ ∥ AC", "key"),
       S("PQ is half of AC", "PQ = ½ AC", "key")]),
    B("05", "Now triangle ADC. S is the midpoint of AD and R is the midpoint of DC. The same theorem gives "
            "SR parallel to AC, and SR is half of AC too.",
      quad(equal=[["DS", "SA"], ["CR", "RD"]], segments=[AC, {"ends": "RS", "role": "result"}],
           parallel=[["SR", "AC"]], fills=[{"poly": "ADC", "role": "result"}]),
      [S("Now triangle ADC", "In triangle ADC"),
       S("S is the midpoint of AD", "S, R: midpoints of AD, DC"),
       S("SR parallel to AC", "SR ∥ AC", "key"),
       S("SR is half of AC too", "SR = ½ AC", "key")]),
    B("06", "Put the two together. PQ and SR are both parallel to AC, and both are half of AC. "
            "Which parallelogram test does that pass?",
      quad(equal=[["PQ", "SR"]], segments=[AC] + INNER, parallel=[["PQ", "AC", "SR"]]),
      [S("PQ and SR are both parallel to AC", "PQ ∥ AC ∥ SR"),
       S("both are half of AC", "PQ = SR = ½ AC"),
       S("Which parallelogram test does that pass", "Which test?", "key")],
      Q("PQ ∥ SR and PQ = SR. Which parallelogram test does PQRS pass?",
        ["One pair of opposite sides equal and parallel", "Both pairs of opposite sides parallel",
         "The diagonals bisect each other"], 0,
        ["Yes. One pair, PQ and SR, is both equal and parallel. That test alone is enough.",
         "True, but we have only shown one pair so far. The test we can use now needs one pair, equal and parallel.",
         "We have not looked at the diagonals of PQRS at all. Look at what we proved about PQ and SR."]), pause=8),
    B("07", "One pair of opposite sides is equal and parallel, so PQRS is a parallelogram. As a check, the "
            "other diagonal, BD, gives the same for the other pair: QR and PS are both parallel to BD.",
      quad(equal=[["PQ", "SR"], ["QR", "PS"]], segments=[AC, BD] + INNER,
           parallel=[["PQ", "AC", "SR"], ["QR", "BD", "PS"]]),
      [S("so PQRS is a parallelogram", "PQRS is a parallelogram", "key"),
       S("the other diagonal, BD", "Check with diagonal BD"),
       S("QR and PS are both parallel to BD", "QR ∥ BD ∥ PS")]),
])

ch3 = C(3, "ANY QUADRILATERAL", "See that the result holds for every quadrilateral, even a concave one", [
    B("08", "The proof never used anything special about ABCD. So predict: if we drag D inside, and ABCD becomes "
            "concave, is PQRS still a parallelogram?",
      quad(equal=[["PQ", "SR"], ["QR", "PS"]], segments=INNER, parallel=[["PQ", "SR"], ["QR", "PS"]]),
      [S("The proof never used anything special", "The proof used only midpoints"),
       S("ABCD becomes concave", "ABCD concave?"),
       S("is PQRS still a parallelogram", "Still a parallelogram?", "key")],
      Q("If ABCD becomes concave, is PQRS still a parallelogram?",
        ["Yes, always", "No, only for a convex ABCD", "Only if ABCD is a parallelogram"], 0,
        ["Let us watch and see if the picture agrees with the proof.",
         "Check the proof: it used two triangles and the midpoint theorem. Did it ever need ABCD to be convex?",
         "ABCD here has no parallel sides at all, and PQRS is already a parallelogram."], kind="predict"), pause=7),
    B("09", "Watch D move inside, and back out again. The midpoints move, and PQRS changes shape, but its "
            "opposite sides stay parallel and equal the whole time. PQRS is always a parallelogram.",
      quad(equal=[["PQ", "SR"], ["QR", "PS"]], segments=INNER, parallel=[["PQ", "SR"], ["QR", "PS"]],
           readout=["PQ", "SR"], unit="cm", move=MOVE),
      [S("Watch D move inside", "D moves: ABCD turns concave"),
       S("PQRS changes shape", "PQRS changes shape"),
       S("opposite sides stay parallel and equal", "Opposite sides stay ∥ and equal", "key"),
       S("PQRS is always a parallelogram", "Always a parallelogram", "key")]),
    B("10", "Now use it. In a quadrilateral, the diagonal AC is ten centimetres and the diagonal BD is eight "
            "centimetres. What is the perimeter of PQRS?",
      quad(segments=[AC, BD] + INNER),
      [S("AC is ten centimetres", "AC = 10 cm"),
       S("BD is eight centimetres", "BD = 8 cm"),
       S("What is the perimeter of PQRS", "Perimeter of PQRS = ?", "key")],
      Q("AC = 10 cm and BD = 8 cm. What is the perimeter of PQRS?", ["18 cm", "9 cm", "36 cm"], 0,
        ["Yes. PQ and SR are each half of AC, 5 cm; QR and PS are each half of BD, 4 cm. 5 + 5 + 4 + 4 = 18 cm.",
         "That adds only one side from each pair. PQRS has four sides: two of 5 cm and two of 4 cm.",
         "That doubles. Each side of PQRS is HALF a diagonal, not equal to it."]), pause=9),
    B("11", "Eighteen centimetres. PQ and SR are each half of ten, five centimetres. QR and PS are each half of "
            "eight, four centimetres. Five plus five plus four plus four is eighteen: the two diagonals added together.",
      quad(segments=[AC, BD] + INNER, parallel=[["PQ", "AC", "SR"], ["QR", "BD", "PS"]]),
      [S("PQ and SR are each half of ten", "PQ = SR = 10 ÷ 2 = 5 cm", "key"),
       S("QR and PS are each half of eight", "QR = PS = 8 ÷ 2 = 4 cm", "key"),
       S("the two diagonals added together", "AC + BD = 18 cm")]),
])

ch4 = C(4, "IN SHORT", "Recall the result and why it is true", [
    B("12", "So, join the midpoints of the sides of any quadrilateral, in order, and you get a parallelogram. "
            "The reason is the midpoint theorem, used twice: each side of PQRS is parallel to a diagonal of ABCD, "
            "and half as long.",
      quad(equal=[["PQ", "SR"], ["QR", "PS"]], segments=[AC, BD] + INNER,
           parallel=[["PQ", "AC", "SR"], ["QR", "BD", "PS"]]),
      [S("join the midpoints of the sides of any quadrilateral", "Midpoints of any quadrilateral"),
       S("you get a parallelogram", "→ a parallelogram", "key"),
       S("the midpoint theorem, used twice", "Midpoint theorem, twice"),
       S("parallel to a diagonal of ABCD, and half as long", "Each side ∥ a diagonal, half as long", "key")]),
], role="recap")

L = lesson("Quadrilaterals 8: the midpoints of any quadrilateral", [ch1, ch2, ch3, ch4])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u8.json")
