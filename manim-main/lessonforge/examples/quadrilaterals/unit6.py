"""Unit 6: the midpoint theorem and its converse (pack section 6, A to D). Predict first, then the theorem, the proof
by constructing a parallelogram, and the converse with the pack's DE example (DH = 4 cm, GH = 5 cm)."""
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G

# the theorem's triangle: BC = 6, so PQ = 3 (one unit = one centimetre)
T = {"A": [1.8, 3.8], "B": [0, 0], "C": [6, 0]}
MID = {"P": "AB", "Q": "AC"}
F = [-0.6, -0.6, 7.4, 4.3]
P_ = G.midpoint(T["A"], T["B"])
Q_ = G.midpoint(T["A"], T["C"])
R_ = [2 * Q_[0] - P_[0], 2 * Q_[1] - P_[1]]          # PQ extended its own length past Q
PROOF = dict(T, P=list(P_), Q=list(Q_), R=R_)

# a second triangle for the transfer question: BC = 9
T9 = {"A": [3.4, 3.6], "B": [0, 0], "C": [9, 0]}

# the pack's example: G the midpoint of DE, GH parallel to EF, DH = 4, GH = 5
EX = {"E": [0, 0], "F": [10, 0], "D": [3.6, 4.8]}
EX_MID = {"G": "DE", "H": "DF"}
m = G.Model({"points": EX, "midpoints": EX_MID})
assert abs(m.length("DH") - 4) < 1e-9 and abs(m.length("GH") - 5) < 1e-9 and abs(m.length("EF") - 10) < 1e-9


def tri(**more):
    spec = {"kind": "shape", "points": T, "polygon": "ABC", "midpoints": MID, "frame": F}
    spec.update(more)
    return spec


def proof(**more):
    spec = {"kind": "shape", "points": PROOF, "polygon": "ABC", "frame": F}
    spec.update(more)
    return spec


def ex(**more):
    spec = {"kind": "shape", "points": EX, "polygon": "DEF", "midpoints": EX_MID, "segments": ["GH"],
            "unit": "cm", "frame": [-0.8, -0.8, 10.8, 5.6]}
    spec.update(more)
    return spec


def ang(at, frm, to, role, value=False):
    return {"at": at, "from": frm, "to": to, "role": role, "value": value}


HALVES = [["AP", "PB"], ["AQ", "QC"]]

ch1 = C(1, "PREDICT", "Predict how PQ relates to BC, and say what would count as proof", [
    B("01", "Here is triangle ABC. P is the midpoint of side AB, so AP equals PB. Q is the midpoint of side AC, "
            "so AQ equals QC. Now join P to Q.",
      tri(equal=HALVES, segments=[{"ends": "PQ", "role": "unknown"}]),
      [S("P is the midpoint of side AB", "P: midpoint of AB"),
       S("Q is the midpoint of side AC", "Q: midpoint of AC"),
       S("Now join P to Q", "Join PQ", "key")]),
    B("02", "Before any measuring, make a prediction. How do you think PQ compares with the third side, BC?",
      tri(equal=HALVES, segments=[{"ends": "PQ", "role": "unknown"}], roles={"BC": "given"}),
      [S("make a prediction", "Predict"),
       S("How do you think PQ compares with the third side", "PQ and BC?", "key")],
      Q("P and Q are the midpoints of AB and AC. What do you predict about PQ and BC?",
        ["PQ ∥ BC, and PQ is half of BC", "PQ ∥ BC, and PQ = BC", "There is no link"], 0,
        ["That is the prediction we will now test, and then prove.",
         "PQ looks parallel, but look at the lengths: PQ reaches only halfway across.",
         "There is a link. Look at the direction of PQ and how far it reaches."], kind="predict"), pause=8),
    B("03", "PQ looks parallel to BC, and it looks half as long. But a drawing can fool the eye. "
            "What would count as proof?",
      tri(equal=HALVES, segments=[{"ends": "PQ", "role": "unknown"}], roles={"BC": "given"}),
      [S("PQ looks parallel to BC", "Looks parallel, looks half"),
       S("a drawing can fool the eye", "Looking is not proof", "key"),
       S("What would count as proof", "What counts as proof?", "key")],
      Q("What would count as proof that PQ ∥ BC and PQ = ½ BC?",
        ["An argument that works for every triangle", "Measuring this one drawing carefully",
         "Checking three different drawings"], 0,
        ["Yes. A proof uses only the conditions, so it holds for every triangle, not just this one.",
         "A measurement shows one drawing, and only as well as the ruler. It is evidence, not proof.",
         "Three examples are still examples. A fourth triangle could break the pattern."], kind="recall"), pause=7),
])

ch2 = C(2, "THE THEOREM", "State the midpoint theorem with its conditions, and apply it", [
    B("04", "Here is the midpoint theorem. The conditions: P is the midpoint of AB, and Q is the midpoint of AC. "
            "The conclusion: PQ is parallel to BC, and PQ is half of BC. Here, BC is six centimetres, "
            "so PQ is three centimetres.",
      tri(equal=HALVES, segments=[{"ends": "PQ", "role": "result"}], parallel=[["PQ", "BC"]],
          readout=["BC", "PQ"], unit="cm"),
      [S("The conditions", "If: P, Q are midpoints of AB, AC"),
       S("PQ is parallel to BC", "Then: PQ ∥ BC", "key"),
       S("PQ is half of BC", "and PQ = ½ BC", "key"),
       S("so PQ is three centimetres", "6 ÷ 2 = 3 cm", "point")]),
    B("05", "Try a new triangle. Here, P and Q are again the midpoints of AB and AC, and BC is nine centimetres. "
            "How long is PQ?",
      {"kind": "shape", "points": T9, "polygon": "ABC", "midpoints": MID, "equal": HALVES,
       "segments": [{"ends": "PQ", "role": "unknown"}], "readout": ["BC"], "unit": "cm"},
      [S("P and Q are again the midpoints", "Midpoints again: check"),
       S("BC is nine centimetres", "BC = 9 cm"),
       S("How long is PQ", "PQ = ?", "key")],
      Q("P and Q are the midpoints of AB and AC, and BC = 9 cm. How long is PQ?", ["4.5 cm", "9 cm", "18 cm"], 0,
        ["Yes. PQ = ½ × 9 = 4.5 cm.",
         "PQ is parallel to BC, but not equal to it. It joins midpoints, so it is half.",
         "That doubles BC. PQ is the shorter one: it is half of BC."]), pause=8),
    B("06", "First check the conditions: P and Q are both midpoints, so the theorem applies. Then PQ is half of "
            "nine, which is four point five centimetres.",
      {"kind": "shape", "points": T9, "polygon": "ABC", "midpoints": MID, "equal": HALVES,
       "segments": [{"ends": "PQ", "role": "result"}], "parallel": [["PQ", "BC"]], "readout": ["BC", "PQ"],
       "unit": "cm"},
      [S("First check the conditions", "1. Both midpoints? Yes"),
       S("Then PQ is half of nine", "2. PQ = 9 ÷ 2 = 4.5 cm", "key")]),
])

ch3 = C(3, "THE PROOF", "Prove the theorem by building a parallelogram", [
    B("07", "Now the proof. We build one extra point, and we say why each step is allowed. Extend PQ past Q "
            "to a point R, so that QR equals PQ. Then join C to R.",
      proof(segments=[{"ends": "PR", "role": "unknown"}, {"ends": "CR", "role": "given"}],
            equal=[["AP", "PB"], ["AQ", "QC"], ["PQ", "QR"]]),
      [S("we say why each step is allowed", "Every construction is justified"),
       S("Extend PQ past Q", "Extend PQ to R: QR = PQ", "key"),
       S("Then join C to R", "Join CR")]),
    B("08", "Look at triangles APQ and CRQ. AQ equals CQ, because Q is the midpoint. PQ equals RQ, because we "
            "built R that way. And the angles at Q are vertically opposite, so they are equal. "
            "So the triangles are congruent by SAS.",
      proof(segments=[{"ends": "PR", "role": "unknown"}, {"ends": "CR", "role": "given"}],
            equal=[["AQ", "QC"], ["PQ", "QR"]], angles=[ang("Q", "A", "P", "given"), ang("Q", "C", "R", "given")],
            fills=[{"poly": "APQ", "role": "given"}, {"poly": "CRQ", "role": "result"}]),
      [S("AQ equals CQ", "AQ = CQ: Q is the midpoint"),
       S("PQ equals RQ", "PQ = RQ: built that way"),
       S("vertically opposite", "Vertically opposite angles"),
       S("congruent by SAS", "△APQ ≅ △CRQ by SAS", "key")]),
    B("09", "So CR equals AP, and AP equals PB, so CR equals PB. Also angle PAQ equals angle RCQ. "
            "Why does that make CR parallel to AB?",
      proof(segments=[{"ends": "PR", "role": "unknown"}, {"ends": "CR", "role": "result"}],
            equal=[["AP", "PB", "CR"]], angles=[ang("A", "P", "Q", "given"), ang("C", "R", "Q", "given")],
            fills=[{"poly": "APQ", "role": "given"}, {"poly": "CRQ", "role": "result"}]),
      [S("CR equals PB", "CR = AP = PB", "key"),
       S("angle PAQ equals angle RCQ", "∠PAQ = ∠RCQ"),
       S("Why does that make CR parallel to AB", "Why CR ∥ AB?", "key")],
      Q("∠PAQ = ∠RCQ. Why does that make CR parallel to AB?",
        ["They are equal alternate angles on the line AC", "CR looks parallel to AB", "CR = PB"], 0,
        ["Yes. AC crosses AB and CR, and equal alternate angles mean the lines are parallel.",
         "Looking is not a reason. Name the angle fact.",
         "Equal lengths say nothing about direction. Look at the two equal angles on AC."]), pause=8),
    B("10", "They are equal alternate angles on the line AC, so CR is parallel to AB. Now look at PBCR. "
            "Its sides PB and CR are equal and parallel, so by test five it is a parallelogram. "
            "So PR is parallel to BC, and PR equals BC. PQ is half of PR, so PQ is half of BC.",
      proof(polygon="PBCR", segments=[{"ends": "AP", "role": "given"}, {"ends": "AC", "role": "given"},
                                      {"ends": "PQ", "role": "result"}],
            equal=[["PB", "CR"], ["PQ", "QR"]], parallel=[["PB", "CR"], ["PR", "BC"]],
            fills=[{"poly": "PBCR", "role": "result"}]),
      [S("so CR is parallel to AB", "CR ∥ AB: alternate angles"),
       S("by test five it is a parallelogram", "PBCR: parallelogram (test 5)", "key"),
       S("PR is parallel to BC, and PR equals BC", "PR ∥ BC, PR = BC"),
       S("so PQ is half of BC", "PQ = ½ PR = ½ BC", "key")]),
])

ch4 = C(4, "THE CONVERSE", "Use the converse: midpoint plus parallel bisects the third side", [
    B("11", "Now the converse. Start at the midpoint of one side, and draw a line parallel to a second side. "
            "Then it cuts the third side at its midpoint. Watch P slide along AB, with PQ kept parallel to BC. "
            "AP to PB and AQ to QC change together. When P reaches the midpoint, so does Q.",
      {"kind": "shape", "points": dict(T, P=list(G.lerp(T["A"], T["B"], 0.3)), Q=list(G.lerp(T["A"], T["C"], 0.3))),
       "polygon": "ABC", "segments": [{"ends": "PQ", "role": "result"}], "parallel": [["PQ", "BC"]],
       "move": {"P": [list(G.lerp(T["A"], T["B"], 0.75)), list(G.lerp(T["A"], T["B"], 0.5))],
                "Q": [list(G.lerp(T["A"], T["C"], 0.75)), list(G.lerp(T["A"], T["C"], 0.5))]},
       "readout": ["AP:PB", "AQ:QC"], "frame": F},
      [S("Now the converse", "Converse: midpoint + parallel ⇒ midpoint", "key"),
       S("Watch P slide along AB", "P slides; PQ stays ∥ BC"),
       S("change together", "AP : PB = AQ : QC"),
       S("When P reaches the midpoint, so does Q", "1 : 1 on both sides", "key")]),
    B("12", "Both conditions matter. On the left, PQ starts at the midpoint, but it is not parallel, and Q misses "
            "the midpoint. On the right, PQ is parallel, but it does not start at the midpoint, and Q misses again.",
      {"kind": "shape", "panels": [
          {"points": dict(T, Q=list(G.lerp(T["A"], T["C"], 0.68))), "polygon": "ABC", "midpoints": {"P": "AB"},
           "equal": [["AP", "PB"]], "segments": [{"ends": "PQ", "role": "wrong"}], "readout": ["AQ:QC"], "caption": "midpoint, not parallel",
           "key": "not parallel"},
          {"points": dict(T, P=list(G.lerp(T["A"], T["B"], 0.35)), Q=list(G.lerp(T["A"], T["C"], 0.35))),
           "polygon": "ABC", "segments": [{"ends": "PQ", "role": "wrong"}], "parallel": [["PQ", "BC"]],
           "readout": ["AQ:QC"], "caption": "parallel, not midpoint", "key": "not midpoint"}]},
      [S("Both conditions matter", "Both conditions matter", "key"),
       S("it is not parallel", "Midpoint, not parallel: misses", highlight="not parallel"),
       S("it does not start at the midpoint", "Parallel, not midpoint: misses", highlight="not midpoint")]),
    B("13", "Now the example. In triangle DEF, G is the midpoint of DE, and GH is parallel to EF. "
            "DH is four centimetres, and GH is five centimetres. How long is DF?",
      ex(equal=[["DG", "GE"]], parallel=[["GH", "EF"]], readout=["DH", "GH"]),
      [S("G is the midpoint of DE", "G: midpoint of DE"),
       S("GH is parallel to EF", "GH ∥ EF"),
       S("DH is four centimetres", "DH = 4 cm, GH = 5 cm"),
       S("How long is DF", "DF = ?", "key")],
      Q("G is the midpoint of DE, GH ∥ EF, DH = 4 cm. How long is DF?", ["8 cm", "4 cm", "10 cm"], 0,
        ["Yes. By the converse, H is the midpoint of DF, so DF = 2 × 4 = 8 cm.",
         "4 cm is DH, only half of DF. By the converse, H is the midpoint of DF.",
         "10 cm is EF, a different side. Use the converse on DF: H is its midpoint."]), pause=8),
    B("14", "By the converse, H is the midpoint of DF, so DF is twice DH: eight centimetres. "
            "Now H is a midpoint too. So what is EF?",
      ex(equal=[["DG", "GE"], ["DH", "HF"]], parallel=[["GH", "EF"]], readout=["DF", "GH"]),
      [S("H is the midpoint of DF", "H: midpoint of DF", "key"),
       S("eight centimetres", "DF = 2 × 4 = 8 cm", "key"),
       S("So what is EF", "EF = ?", "key")],
      Q("G and H are the midpoints of DE and DF, and GH = 5 cm. How long is EF?", ["10 cm", "5 cm", "2.5 cm"], 0,
        ["Yes. By the midpoint theorem, GH = ½ EF, so EF = 2 × 5 = 10 cm.",
         "GH is parallel to EF, not equal to it. GH is half of EF.",
         "That halves GH. EF is the longer side: GH is half of EF."]), pause=8),
    B("15", "By the midpoint theorem, GH is half of EF, so EF is ten centimetres. Two steps, two reasons: "
            "the converse gave the midpoint, and the theorem gave the length.",
      ex(equal=[["DG", "GE"], ["DH", "HF"]], parallel=[["GH", "EF"]], readout=["DF", "EF"]),
      [S("so EF is ten centimetres", "EF = 2 × 5 = 10 cm", "key"),
       S("the converse gave the midpoint", "Converse: H is a midpoint"),
       S("the theorem gave the length", "Theorem: GH = ½ EF", "key")]),
])

ch5 = C(5, "IN SHORT", "Recall the theorem, its proof and its converse", [
    B("16", "So, the midpoint theorem: join the midpoints of two sides, and you get a segment parallel to the third "
            "side and half its length. We proved it by building a parallelogram. And the converse: from a "
            "midpoint, a line parallel to a second side cuts the third side at its midpoint.",
      tri(equal=HALVES, segments=[{"ends": "PQ", "role": "result"}], parallel=[["PQ", "BC"]]),
      [S("join the midpoints of two sides", "Midpoints joined:"),
       S("parallel to the third side and half its length", "PQ ∥ BC, PQ = ½ BC", "key"),
       S("We proved it by building a parallelogram", "Proof: build a parallelogram"),
       S("And the converse", "Converse: midpoint + parallel ⇒ midpoint", "key")]),
], role="recap")

L = lesson("Quadrilaterals 6: the midpoint theorem", [ch1, ch2, ch3, ch4, ch5])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u6.json")
