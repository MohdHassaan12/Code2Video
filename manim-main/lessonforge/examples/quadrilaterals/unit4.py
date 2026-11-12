"""Unit 4: parallelograms, the definition and five tests, and three proofs (pack section 4, A to F).

Equal ticks, parallel arrows, the crossing point E and every verdict are checked by ``longform.geometry`` against
the coordinates before they are drawn; the asserts below make the builder refuse a drawing that would lie."""
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G

P = {"A": [0, 0], "B": [4.5, 0], "C": [6, 2.8], "D": [1.5, 2.8]}
F = [-0.6, -0.6, 6.6, 3.4]
KITE = {"A": [0, 1.5], "B": [2, 0], "C": [6, 1.5], "D": [2, 3]}
TRAP = {"A": [0, 0], "B": [5, 0], "C": [3.8, 2.4], "D": [1.2, 2.4]}
assert G.parallelogram_tests(G.Model({"points": P, "polygon": "ABCD"}))["both_pairs_equal"]
assert not G.parallelogram_tests(G.Model({"points": KITE, "polygon": "ABCD"}))["both_pairs_equal"]
assert not any(G.parallelogram_tests(G.Model({"points": TRAP, "polygon": "ABCD"})).values())

PAR = [["AB", "DC"], ["AD", "BC"]]
EQ = [["AB", "CD"], ["AD", "BC"]]
DIAG = [{"ends": "AC", "dashed": True}, {"ends": "BD", "dashed": True}]


def par(**more):
    spec = {"kind": "shape", "points": P, "polygon": "ABCD", "frame": F}
    spec.update(more)
    return spec


def ang(at, frm, to, role, value=False):
    return {"at": at, "from": frm, "to": to, "role": role, "value": value}


ch1 = C(1, "WHAT A PARALLELOGRAM IS", "State the definition and tell it apart from a test", [
    B("01", "A parallelogram is a quadrilateral in which both pairs of opposite sides are parallel. "
            "Here, AB is parallel to DC, and AD is parallel to BC. The arrow marks show which sides are parallel: "
            "one arrow for the first pair, two arrows for the second.",
      par(parallel=PAR), [S("both pairs of opposite sides are parallel", "Both pairs of opposite sides parallel", "key"),
                          S("AB is parallel to DC", "AB ∥ DC"), S("AD is parallel to BC", "AD ∥ BC"),
                          S("The arrow marks show", "Arrows mark parallel sides")]),
    B("02", "That sentence is the definition. It says what a parallelogram is. But parallel lines are not always "
            "easy to check. So we also use tests. A test is a different fact which, once it is true, proves that "
            "the shape must be a parallelogram.",
      par(parallel=PAR), [S("That sentence is the definition", "Definition: what it IS", "key"),
                          S("So we also use tests", "Test: a fact that PROVES it", "key")]),
    B("03", "Quick check. Which of these is the definition of a parallelogram?",
      par(), [S("Which of these is the definition", "Which is the definition?", "key")],
      Q("Which statement is the definition of a parallelogram?",
        ["both pairs of opposite sides parallel", "both pairs of opposite sides equal",
         "the diagonals bisect each other"], 0,
        ["Yes. The definition says what the shape is: opposite sides parallel, both pairs.",
         "That is true of every parallelogram, but it is one of the tests, not the definition.",
         "That is true of every parallelogram too, but it is a test, proved from the definition."],
        kind="recall"), pause=7),
])

ch2 = C(2, "FIVE TESTS", "Know the five sufficient conditions and their traps", [
    B("04", "It is the first one. Now the five tests. A quadrilateral is a parallelogram if any one of them is true. "
            "Test one is the definition itself: both pairs of opposite sides are parallel.",
      par(parallel=PAR), [S("Now the five tests", "Five tests", "key"),
                          S("Test one is the definition itself", "1. Both pairs parallel")]),
    B("05", "Test two: both pairs of opposite sides are equal. AB equals CD, and AD equals BC. "
            "One tick marks the first pair, two ticks the second.",
      par(equal=EQ), [S("both pairs of opposite sides are equal", "2. Both pairs of opposite sides equal", "key"),
                      S("AB equals CD, and AD equals BC", "AB = CD, AD = BC")]),
    B("06", "Test three: both pairs of opposite angles are equal. Angle A equals angle C, "
            "and angle B equals angle D.",
      par(angles=list("ABCD"), equal_angles=[["A", "C"], ["B", "D"]]),
      [S("both pairs of opposite angles are equal", "3. Opposite angles equal", "key"),
       S("Angle A equals angle C", "∠A = ∠C, ∠B = ∠D")]),
    B("07", "Test four: the diagonals bisect each other. They cross at E, and E is the midpoint of both. "
            "AE equals EC, and BE equals ED.",
      par(segments=DIAG, meet={"E": ["AC", "BD"]}, equal=[["AE", "EC"], ["BE", "ED"]]),
      [S("the diagonals bisect each other", "4. Diagonals bisect each other", "key"),
       S("E is the midpoint of both", "E: midpoint of both"),
       S("AE equals EC, and BE equals ED", "AE = EC, BE = ED")]),
    B("08", "Test five: one pair of opposite sides is both equal and parallel. Here AB equals DC, "
            "and AB is parallel to DC. It must be the same pair that is equal and parallel.",
      par(equal=[["AB", "DC"]], parallel=[["AB", "DC"]]),
      [S("one pair of opposite sides is both equal and parallel", "5. One pair equal AND parallel", "key"),
       S("It must be the same pair", "The SAME pair")]),
    B("09", "Now a trap. This kite has two pairs of equal sides. Is it a parallelogram?",
      {"kind": "shape", "points": KITE, "polygon": "ABCD", "equal": [["AB", "DA"], ["BC", "CD"]],
       "frame": [-0.4, -0.4, 6.4, 3.4]},
      [S("This kite has two pairs of equal sides", "A kite: two pairs of equal sides"),
       S("Is it a parallelogram", "Parallelogram?", "key")],
      Q("This kite has two pairs of equal sides. Is it a parallelogram?", ["No", "Yes"], 0,
        ["Right. Its equal sides are next to each other, not opposite each other.",
         "Look at where the equal sides are: AB and AD meet at A, so they are adjacent, not opposite."],
        kind="spot"), pause=7),
    B("10", "No. In the kite, AB equals AD, but those two sides meet at A. They are adjacent, not opposite. "
            "Test two needs opposite sides equal.",
      {"kind": "shape", "points": KITE, "polygon": "ABCD", "equal": [["AB", "DA"], ["BC", "CD"]],
       "frame": [-0.4, -0.4, 6.4, 3.4], "roles": {"AB": "wrong", "DA": "wrong"}},
      [S("those two sides meet at A", "AB and AD meet at A"),
       S("Test two needs opposite sides equal", "Test 2 needs OPPOSITE sides", "key")]),
    B("11", "One more trap. In this shape, AB is parallel to DC, and AD equals BC. Is it a parallelogram?",
      {"kind": "shape", "points": TRAP, "polygon": "ABCD", "parallel": [["AB", "DC"]], "equal": [["AD", "BC"]],
       "frame": [-0.4, -0.4, 5.4, 2.8]},
      [S("AB is parallel to DC, and AD equals BC", "AB ∥ DC and AD = BC"),
       S("Is it a parallelogram", "Parallelogram?", "key")],
      Q("AB is parallel to DC and AD equals BC. Is it a parallelogram?", ["No", "Yes"], 0,
        ["Right. The parallel pair and the equal pair are different pairs.",
         "Test five needs ONE pair that is both equal and parallel. Here the parallel pair is not the equal pair."],
        kind="spot"), pause=7),
    B("12", "No. AB and DC are the parallel pair, but AD and BC are the equal pair. Those are different pairs, "
            "so test five does not apply. This shape is an isosceles trapezium. To use test five, we would "
            "need AB to equal DC as well.",
      {"kind": "shape", "points": TRAP, "polygon": "ABCD", "parallel": [["AB", "DC"]], "equal": [["AD", "BC"]],
       "frame": [-0.4, -0.4, 5.4, 2.8], "verdict": "isosceles trapezium"},
      [S("Those are different pairs", "Different pairs: test 5 fails", "key"),
       S("This shape is an isosceles trapezium", "An isosceles trapezium"),
       S("we would need AB to equal DC as well", "Would need AB = DC too")]),
])

ch3 = C(3, "PROVING TEST TWO", "Prove that equal opposite sides make a parallelogram", [
    B("13", "Now let us prove test two. We are given that AB equals CD, and AD equals BC. "
            "Draw the diagonal AC. It splits the shape into triangle ABC and triangle CDA. "
            "Which congruence test do the marks give us?",
      par(equal=EQ, segments=[{"ends": "AC", "role": "given"}],
          fills=[{"poly": "ABC", "role": "given"}, {"poly": "CDA", "role": "result"}]),
      [S("We are given that AB equals CD", "Given: AB = CD, AD = BC"),
       S("Draw the diagonal AC", "Draw AC"),
       S("Which congruence test", "Which congruence test?", "key")],
      Q("Triangles ABC and CDA: which congruence test do the marks give?", ["SSS", "ASA", "SAS"], 0,
        ["Yes. Three pairs of sides: AB = CD, BC = DA, and AC is shared.",
         "ASA needs two equal angles. We know no equal angles yet: nothing has been proved parallel.",
         "SAS needs an equal angle between the sides. We have not been given any angle."]), pause=8),
    B("14", "It is SSS. AB equals CD, BC equals DA, and AC is shared by both triangles. "
            "So triangle ABC is congruent to triangle CDA.",
      par(equal=EQ, segments=[{"ends": "AC", "role": "given"}],
          fills=[{"poly": "ABC", "role": "given"}, {"poly": "CDA", "role": "result"}]),
      [S("It is SSS", "SSS", "key"), S("AC is shared by both triangles", "AC is common"),
       S("So triangle ABC is congruent to triangle CDA", "△ABC ≅ △CDA", "key")]),
    B("15", "Congruent triangles have equal matching angles. So angle BAC equals angle DCA. "
            "Those are alternate angles on the line AC, and equal alternate angles mean AB is parallel to DC. "
            "In the same way, angle BCA equals angle DAC, so BC is parallel to AD. "
            "Both pairs of opposite sides are parallel. ABCD is a parallelogram.",
      par(equal=EQ, segments=[{"ends": "AC", "role": "given"}],
          angles=[ang("A", "B", "C", "given"), ang("C", "D", "A", "given"),
                  ang("C", "B", "A", "result"), ang("A", "D", "C", "result")],
          parallel=PAR),
      [S("So angle BAC equals angle DCA", "∠BAC = ∠DCA"),
       S("AB is parallel to DC", "Alternate angles: AB ∥ DC"),
       S("so BC is parallel to AD", "And BC ∥ AD"),
       S("ABCD is a parallelogram", "So ABCD is a parallelogram", "key")]),
])

ch4 = C(4, "PROVING TEST FOUR", "Prove that bisecting diagonals make a parallelogram", [
    B("16", "Next, test four. The diagonals meet at E, and we are given that AE equals CE, and BE equals DE. "
            "Look at triangles AEB and CED. Why is angle AEB equal to angle CED?",
      par(segments=DIAG, meet={"E": ["AC", "BD"]}, equal=[["AE", "EC"], ["BE", "ED"]],
          angles=[ang("E", "A", "B", "given"), ang("E", "C", "D", "given")],
          fills=[{"poly": "AEB", "role": "given"}, {"poly": "CED", "role": "result"}]),
      [S("we are given that AE equals CE", "Given: AE = CE, BE = DE"),
       S("Look at triangles AEB and CED", "Triangles AEB and CED"),
       S("Why is angle AEB equal to angle CED", "Why ∠AEB = ∠CED?", "key")],
      Q("Why is angle AEB equal to angle CED?",
        ["vertically opposite angles", "alternate angles", "the triangles are congruent"], 0,
        ["Yes. Two straight lines cross at E, and the opposite angles there are equal.",
         "Alternate angles need parallel lines, and nothing has been proved parallel yet.",
         "That is what we are trying to show. We cannot use it to prove itself."]), pause=8),
    B("17", "They are vertically opposite: two straight lines cross at E. So we have two sides and the angle "
            "between them. AE equals CE, BE equals DE, and the angles at E are equal. "
            "By SAS, triangle AEB is congruent to triangle CED.",
      par(segments=DIAG, meet={"E": ["AC", "BD"]}, equal=[["AE", "EC"], ["BE", "ED"]],
          angles=[ang("E", "A", "B", "given"), ang("E", "C", "D", "given")],
          fills=[{"poly": "AEB", "role": "given"}, {"poly": "CED", "role": "result"}]),
      [S("They are vertically opposite", "Vertically opposite angles"),
       S("two sides and the angle between them", "Side, angle, side"),
       S("By SAS", "△AEB ≅ △CED by SAS", "key")]),
    B("18", "So their matching angles are equal: angle BAE equals angle DCE. These are alternate angles on AC, "
            "so AB is parallel to CD. Triangles AED and CEB give AD parallel to BC in the same way. "
            "ABCD is a parallelogram.",
      par(segments=DIAG, meet={"E": ["AC", "BD"]}, equal=[["AE", "EC"], ["BE", "ED"]],
          angles=[ang("A", "B", "E", "given"), ang("C", "D", "E", "given")], parallel=PAR),
      [S("angle BAE equals angle DCE", "∠BAE = ∠DCE"),
       S("so AB is parallel to CD", "AB ∥ CD"),
       S("ABCD is a parallelogram", "So ABCD is a parallelogram", "key")]),
])

ch5 = C(5, "PROVING TEST FIVE", "Prove that one pair equal and parallel is enough", [
    B("19", "Last, test five. AB is parallel to DC, and AB equals DC. Draw both diagonals, meeting at E. "
            "Because AB is parallel to DC, the alternate angles on AC are equal: angle BAE equals angle DCE. "
            "On BD, angle ABE equals angle CDE.",
      par(equal=[["AB", "DC"]], parallel=[["AB", "DC"]], segments=DIAG, meet={"E": ["AC", "BD"]},
          angles=[ang("A", "B", "E", "given"), ang("C", "D", "E", "given"),
                  ang("B", "E", "A", "result"), ang("D", "E", "C", "result")]),
      [S("AB is parallel to DC, and AB equals DC", "Given: AB ∥ DC, AB = DC"),
       S("Draw both diagonals", "Draw both diagonals"),
       S("angle BAE equals angle DCE", "∠BAE = ∠DCE, alternate"),
       S("angle ABE equals angle CDE", "∠ABE = ∠CDE")]),
    B("20", "Two angles and the side between them: triangles ABE and CDE are congruent by ASA. "
            "So AE equals CE, and BE equals DE. The diagonals bisect each other, and by test four, "
            "ABCD is a parallelogram.",
      par(equal=[["AB", "DC"], ["AE", "EC"], ["BE", "ED"]], parallel=[["AB", "DC"]], segments=DIAG,
          meet={"E": ["AC", "BD"]}, fills=[{"poly": "ABE", "role": "given"}, {"poly": "CDE", "role": "result"}]),
      [S("congruent by ASA", "△ABE ≅ △CDE by ASA", "key"),
       S("So AE equals CE", "AE = CE, BE = DE"),
       S("by test four", "Test 4: a parallelogram", "key")]),
])

ch6 = C(6, "CHOOSE THE TEST", "Pick the test the facts support", [
    B("21", "Let us use what we have. A quadrilateral has AB equal to CD, and AB parallel to CD. "
            "Which test proves that it is a parallelogram?",
      par(equal=[["AB", "CD"]], parallel=[["AB", "DC"]]),
      [S("Which test proves", "Which test proves it?", "key")],
      Q("AB = CD and AB ∥ CD. Which test proves ABCD is a parallelogram?",
        ["test five", "test two", "not enough information"], 0,
        ["Yes. One pair of opposite sides is both equal and parallel.",
         "Test two needs BOTH pairs of opposite sides equal. We only know about AB and CD.",
         "It is enough: test five needs only one pair, as long as it is both equal and parallel."]), pause=7),
    B("22", "Test five. AB and CD are one pair of opposite sides, and that same pair is both equal and parallel. "
            "So, the definition says both pairs of opposite sides are parallel. The five tests are other ways "
            "to prove it: both pairs of sides equal, both pairs of angles equal, diagonals that bisect each other, "
            "or one pair that is equal and parallel.",
      par(equal=EQ, parallel=PAR, segments=DIAG, meet={"E": ["AC", "BD"]}),
      [S("that same pair is both equal and parallel", "Test five", "key"),
       S("The five tests are other ways", "Five tests: other ways to prove it"),
       S("both pairs of sides equal", "Other tests: sides, angles, diagonals, one pair", "key")]),
], role="recap")

L = lesson("Quadrilaterals 4: parallelograms and their tests", [ch1, ch2, ch3, ch4, ch5, ch6])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u4.json")
