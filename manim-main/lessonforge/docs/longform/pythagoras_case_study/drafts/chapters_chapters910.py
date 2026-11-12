# Premium model source; see generated/ and editorial_changes.json for provenance.
from lesson_runtime import *
import numpy as np

# ── helpers ────────────────────────────────────────────────────────────────────

def right_triangle(a, b, origin=ORIGIN, color_a=TEAL, color_b=GOLD, color_c=PINK):
    A = np.array(origin)
    B = A + np.array([a, 0, 0])
    C = A + np.array([0, b, 0])
    tri = Polygon(A, B, C, color=INK, fill_opacity=0)
    sides = VGroup(
        Line(A, B, color=color_a, stroke_width=4),
        Line(A, C, color=color_b, stroke_width=4),
        Line(B, C, color=color_c, stroke_width=4),
    )
    sq_size = min(a, b) * 0.12
    sq = Polygon(A + [sq_size, 0, 0], A + [sq_size, sq_size, 0],
                 A + [0, sq_size, 0], A, color=INK, stroke_width=2)
    return tri, sides, sq

def countdown_graphic(n, center=ORIGIN):
    circle = Circle(radius=0.45, color=GOLD, stroke_width=3).move_to(center)
    num = eq(str(n), size=36, color=GOLD).move_to(center)
    return VGroup(circle, num)

def small_eq(s, size=32, color=INK):
    return MathTex(s, font_size=size, color=color)


# ══════════════════════════════════════════════════════════════════════════════
class C09(LessonScene):
    def construct(self):
        self.chapter(9)

        # ── Beat 33 ────────────────────────────────────────────────────────────
        self.begin("33")

        # Build 5-12 right triangle on left side
        scale = 0.38
        a, b = 5 * scale, 12 * scale
        ox, oy = -5.2, -1.6
        A = np.array([ox, oy, 0])
        B = A + np.array([a * 2, 0, 0])   # horizontal leg (5)
        C = A + np.array([0, b * 2, 0])   # vertical leg (12)

        tri33 = Polygon(A, B, C, color=INK, stroke_width=2, fill_opacity=0)
        leg_a = Line(A, B, color=TEAL, stroke_width=5)
        leg_b = Line(A, C, color=GOLD, stroke_width=5)
        hyp   = Line(B, C, color=PINK, stroke_width=5)

        sq_s = 0.18
        ra_sq = Polygon(A+[sq_s,0,0], A+[sq_s,sq_s,0], A+[0,sq_s,0], A,
                        color=INK, stroke_width=2)

        lbl_a = txt("5 m", 26, TEAL).next_to(leg_a, DOWN, buff=0.12)
        lbl_b = txt("12 m", 26, GOLD).next_to(leg_b, LEFT, buff=0.12)
        lbl_c = txt("c = ?", 26, PINK).next_to(hyp, RIGHT, buff=0.12)

        eq33 = small_eq(r"c^2 = 5^2 + 12^2", 38, INK).move_to([3.5, 1.2, 0])

        self.cue("Time to try one yourself.",
                 Create(leg_a), Create(leg_b), Create(hyp),
                 Create(ra_sq), run_time=1.4)
        self.cue("What is the length of the hypotenuse",
                 FadeIn(lbl_a), FadeIn(lbl_b), FadeIn(lbl_c), run_time=1.0)
        self.cue("Set up the equation",
                 Write(eq33), run_time=1.2)

        # countdown 8 s — show timer, no answer
        cd = countdown_graphic(8, center=[3.5, -0.5, 0])
        self.cue("You have eight seconds",
                 FadeIn(cd), run_time=0.8)

        self.finish()

        # ── Beat 34 ────────────────────────────────────────────────────────────
        self.begin("34")

        # Reveal answer step by step
        step1 = small_eq(r"5^2 = 25", 34, TEAL).move_to([3.5, 0.55, 0])
        step2 = small_eq(r"12^2 = 144", 34, GOLD).move_to([3.5, 0.0, 0])
        step3 = small_eq(r"25 + 144 = 169", 34, INK).move_to([3.5, -0.55, 0])
        step4 = small_eq(r"c = \sqrt{169} = 13\,\text{m}", 36, PINK).move_to([3.5, -1.15, 0])
        check = txt("✓", 40, TEAL).next_to(step4, RIGHT, buff=0.2)

        self.cue("Five squared is twenty-five",
                 FadeOut(cd), Write(step1), run_time=1.0)
        self.cue("twelve squared is one hundred and forty-four",
                 Write(step2), run_time=1.0)
        self.cue("twenty-five plus one hundred and forty-four is one hundred and sixty-nine",
                 Write(step3), run_time=1.0)
        self.cue("The square root of one hundred and sixty-nine is thirteen",
                 Write(step4), FadeIn(check), run_time=1.2)

        # New triangle: hyp=10, leg=6, unknown leg h
        scale2 = 0.42
        ox2, oy2 = -5.2, -1.6
        leg6 = 6 * scale2; hyp10 = 8 * scale2   # display height for 10 hyp
        A2 = np.array([ox2, oy2, 0])
        B2 = A2 + np.array([leg6, 0, 0])
        # place C2 so BC = 10*scale2 and AC = h*scale2
        h_val = 8 * scale2
        C2 = A2 + np.array([0, h_val, 0])

        leg_a2 = Line(A2, B2, color=TEAL, stroke_width=5)
        leg_b2 = Line(A2, C2, color=GOLD, stroke_width=5)
        hyp2   = Line(B2, C2, color=PINK, stroke_width=5)
        ra2    = Polygon(A2+[0.18,0,0], A2+[0.18,0.18,0], A2+[0,0.18,0], A2,
                         color=INK, stroke_width=2)
        lbl_6  = txt("6 m", 26, TEAL).next_to(leg_a2, DOWN, buff=0.12)
        lbl_10 = txt("10 m", 26, PINK).next_to(hyp2, RIGHT, buff=0.12)
        lbl_h  = txt("h = ?", 26, GOLD).next_to(leg_b2, LEFT, buff=0.12)
        eq34   = small_eq(r"h^2 + 6^2 = 10^2", 36, INK).move_to([3.5, 1.2, 0])

        self.cue("Now a second question",
                 FadeOut(VGroup(leg_a, leg_b, hyp, ra_sq, lbl_a, lbl_b, lbl_c, eq33,
                                step1, step2, step3, step4, check)),
                 Create(leg_a2), Create(leg_b2), Create(hyp2), Create(ra2),
                 run_time=1.2)
        self.cue("What is the other leg",
                 FadeIn(lbl_6), FadeIn(lbl_10), FadeIn(lbl_h), run_time=1.0)
        self.cue("Set up the equation: leg squared plus six squared",
                 Write(eq34), run_time=1.0)

        cd2 = countdown_graphic(8, center=[3.5, -0.5, 0])
        self.cue("You have eight seconds",
                 FadeIn(cd2), run_time=0.8)

        self.finish()

        # ── Beat 35 ────────────────────────────────────────────────────────────
        self.begin("35")

        ans_h1 = small_eq(r"h^2 + 36 = 100", 34, INK).move_to([3.5, 0.55, 0])
        ans_h2 = small_eq(r"h^2 = 64", 34, INK).move_to([3.5, 0.0, 0])
        ans_h3 = small_eq(r"h = \sqrt{64} = 8\,\text{m}", 36, GOLD).move_to([3.5, -0.55, 0])
        chk2   = txt("✓", 40, TEAL).next_to(ans_h3, RIGHT, buff=0.2)

        self.cue("H squared plus thirty-six equals one hundred",
                 FadeOut(cd2), Write(ans_h1), run_time=1.0)
        self.cue("Subtract thirty-six to get sixty-four",
                 Write(ans_h2), run_time=1.0)
        self.cue("h is eight metres",
                 Write(ans_h3), FadeIn(chk2), run_time=1.0)

        # Clear and show unit square + diagonal + two candidates
        unit = 2.2
        sq_orig = np.array([-5.5, -1.1, 0])
        sq_pts = [sq_orig, sq_orig+[unit,0,0], sq_orig+[unit,unit,0], sq_orig+[0,unit,0]]
        unit_sq = Polygon(*sq_pts, color=INK, stroke_width=3, fill_opacity=0)
        diag_line = Line(sq_pts[0], sq_pts[2], color=PINK, stroke_width=4)
        lbl_1a = txt("1 m", 24, INK).next_to(Line(sq_pts[0], sq_pts[1]), DOWN, buff=0.1)
        lbl_1b = txt("1 m", 24, INK).next_to(Line(sq_pts[1], sq_pts[2]), RIGHT, buff=0.1)
        cand_a = small_eq(r"d = 2\,?", 34, MUTED).move_to([3.5, 0.6, 0])
        cand_b = small_eq(r"d = \sqrt{2}\,?", 34, MUTED).move_to([3.5, -0.1, 0])

        self.cue("Now a reasoning question",
                 FadeOut(VGroup(leg_a2, leg_b2, hyp2, ra2, lbl_6, lbl_10, lbl_h,
                                eq34, ans_h1, ans_h2, ans_h3, chk2)),
                 Create(unit_sq), Create(diag_line),
                 FadeIn(lbl_1a), FadeIn(lbl_1b), run_time=1.2)
        self.cue("A student says its diagonal is two metres",
                 Write(cand_a), run_time=1.0)
        self.cue("Another says the diagonal is the square root of two metres",
                 Write(cand_b), run_time=1.0)

        cd3 = countdown_graphic(8, center=[3.5, -1.1, 0])
        self.cue("Think for eight seconds",
                 FadeIn(cd3), run_time=0.8)

        self.finish()

        # ── Beat 36 ────────────────────────────────────────────────────────────
        self.begin("36")

        # Draw square on diagonal (tilted square, area=2)
        # diagonal goes from sq_pts[0] to sq_pts[2]
        d0 = np.array(sq_pts[0]); d1 = np.array(sq_pts[2])
        mid = (d0 + d1) / 2
        perp = np.array([-(d1-d0)[1], (d1-d0)[0], 0]) * 0.5
        ds_pts = [d0, d0 + perp, d1 + perp, d1]
        diag_sq = Polygon(*ds_pts, color=PINK, stroke_width=3,
                          fill_color=PINK, fill_opacity=0.18)
        lbl_area2 = txt("area = 2", 22, PINK).move_to(mid + perp*0.5 + np.array([0.0, 0.3, 0]))

        # Hypothetical square side=2
        hyp_sq = Square(side_length=1.1, color=MUTED, stroke_width=2,
                        fill_color=MUTED, fill_opacity=0.12).move_to([-1.5, 0.4, 0])
        lbl_area4 = txt("area = 4\n(too large)", 22, MUTED).move_to([-1.5, -0.35, 0])

        correct = small_eq(r"\sqrt{2} \approx 1.414", 34, TEAL).move_to([3.5, 0.6, 0])
        wrong   = small_eq(r"2 = \text{route length}", 32, PINK).move_to([3.5, -0.05, 0])
        cross   = txt("✗", 36, PINK).next_to(wrong, RIGHT, buff=0.15)
        tick    = txt("✓", 36, TEAL).next_to(correct, RIGHT, buff=0.15)

        self.cue("The diagonal is the square root of two metres",
                 FadeOut(cd3), FadeOut(cand_a), FadeOut(cand_b),
                 Create(diag_sq), FadeIn(lbl_area2), run_time=1.3)
        self.cue("the square on the diagonal must have area two",
                 Write(correct), FadeIn(tick), run_time=1.1)
        self.cue("If that side were two metres, its square would have area four",
                 FadeIn(hyp_sq), FadeIn(lbl_area4), run_time=1.2)
        self.cue("which contradicts our area relationship",
                 Write(wrong), FadeIn(cross), run_time=1.0)
        self.cue("The length two measures the bent route along two edges",
                 Indicate(wrong, color=PINK), run_time=1.0)

        self.finish()


# ══════════════════════════════════════════════════════════════════════════════
class C10(LessonScene):
    def construct(self):
        self.chapter(10)

        # ── Beat 37 ────────────────────────────────────────────────────────────
        self.begin("37")

        # Robot diagram: rectangle corner, east=4, north=3
        sc = 0.52
        ox, oy = -5.6, -1.5
        O  = np.array([ox, oy, 0])
        E  = O + np.array([4*sc, 0, 0])
        N  = O + np.array([0, 3*sc, 0])
        NE = O + np.array([4*sc, 3*sc, 0])

        rect = Polygon(O, E, NE, N, color=GRID, stroke_width=1.5, fill_opacity=0)
        arr_e = Arrow(O, E, buff=0, color=TEAL, stroke_width=5, tip_length=0.18)
        arr_n = Arrow(E, NE, buff=0, color=GOLD, stroke_width=5, tip_length=0.18)
        diag37 = Line(O, NE, color=PINK, stroke_width=5)
        ra37   = Polygon(E+[-0.15,0,0], E+[-0.15,0.15,0], E+[0,0.15,0], E,
                         color=INK, stroke_width=2)

        lbl_4  = txt("4 m", 26, TEAL).next_to(arr_e, DOWN, buff=0.1)
        lbl_3  = txt("3 m", 26, GOLD).next_to(arr_n, RIGHT, buff=0.1)
        lbl_c37= txt("c = ?", 26, PINK).move_to((O+NE)/2 + np.array([-0.5, 0.25, 0]))

        self.cue("Return to our robot",
                 Create(rect), Create(arr_e), Create(arr_n),
                 Create(diag37), Create(ra37), run_time=1.3)
        self.cue("Four metres east and three metres north",
                 FadeIn(lbl_4), FadeIn(lbl_3), FadeIn(lbl_c37), run_time=1.0)

        # Step-by-step calculation on right
        calc1 = small_eq(r"c^2 = 4^2 + 3^2", 36, INK).move_to([3.8, 1.3, 0])
        calc2 = small_eq(r"= 16 + 9 = 25", 36, INK).move_to([3.8, 0.65, 0])
        calc3 = small_eq(r"c = \sqrt{25} = 5\,\text{m}", 38, PINK).move_to([3.8, 0.0, 0])
        comp  = txt("Route: 7 m  vs  Diagonal: 5 m", 26, INK).move_to([3.8, -0.75, 0])
        save  = txt("Saving: 2 m", 26, TEAL).move_to([3.8, -1.25, 0])

        self.cue("Their squares have areas sixteen and nine",
                 Write(calc1), run_time=1.0)
        self.cue("totalling twenty-five",
                 Write(calc2), run_time=1.0)
        self.cue("So the diagonal's square has area twenty-five and its side is five metres",
                 Write(calc3), run_time=1.2)

        lbl_c37_new = txt("5 m", 26, PINK).move_to((O+NE)/2 + np.array([-0.5, 0.25, 0]))
        self.cue("It travels five metres instead of seven",
                 ReplacementTransform(lbl_c37, lbl_c37_new),
                 FadeIn(comp), FadeIn(save), run_time=1.2)

        self.finish()

        # ── Beat 38 ────────────────────────────────────────────────────────────
        self.begin("38")

        # Draw three outward squares on the 4-3-5 triangle
        # Triangle vertices: O, E, NE  (right angle at E)
        def outward_square(P, Q, fill_col, label_str, lbl_size=24):
            v = Q - P
            perp = np.array([-v[1], v[0], 0])
            pts = [P, Q, Q + perp, P + perp]
            sq = Polygon(*pts, color=fill_col, stroke_width=2,
                         fill_color=fill_col, fill_opacity=0.25)
            ctr = (P + Q + Q + perp + P + perp) / 4
            lb  = txt(label_str, lbl_size, fill_col).move_to(ctr)
            return sq, lb

        sq_a, lb_a = outward_square(O, E,  TEAL, "16")
        sq_b, lb_b = outward_square(E, NE, GOLD, "9")
        sq_c, lb_c = outward_square(NE, O, PINK, "25")

        eq38 = small_eq(r"a^2 + b^2 = c^2", 40, INK).move_to([3.8, 1.3, 0])
        eq38b= small_eq(r"16 + 9 = 25", 36, INK).move_to([3.8, 0.65, 0])

        self.cue("Remember the connection",
                 FadeOut(VGroup(calc1, calc2, calc3, comp, save)),
                 Create(sq_a), FadeIn(lb_a), run_time=1.1)
        self.cue("their sum equals the area of the hypotenuse square",
                 Create(sq_b), FadeIn(lb_b),
                 Create(sq_c), FadeIn(lb_c), run_time=1.3)
        self.cue("We established that by counting one outer square in two ways",
                 Write(eq38), run_time=1.1)
        self.cue("a square root converts the resulting area back into a length",
                 Write(eq38b), run_time=1.1)

        self.finish()

        # ── Beat 39 ────────────────────────────────────────────────────────────
        self.begin("39")

        # Six-step checklist on right panel
        steps = [
            txt("1. Confirm right angle", 25, INK),
            txt("2. Identify hypotenuse\n   (opposite right angle)", 25, INK),
            txt("3. Square known lengths", 25, INK),
            txt("4. Add or subtract", 25, INK),
            txt("5. Positive square root", 25, INK),
            txt("6. State length unit", 25, INK),
        ]
        checklist = VGroup(*steps).arrange(DOWN, buff=0.28, aligned_edge=LEFT)
        checklist.move_to([3.5, 0.1, 0])
        if checklist.width > 5.0:
            checklist.scale_to_fit_width(5.0)
        if checklist.height > 4.3:
            checklist.scale_to_fit_height(4.3)

        # Highlight objects on diagram
        hl_ra  = Circle(radius=0.28, color=TEAL, stroke_width=3).move_to(E)
        hl_hyp = diag37.copy().set_color(PINK).set_stroke(width=8)

        self.cue("Before using the theorem, check for a right angle",
                 FadeOut(VGroup(sq_a, lb_a, sq_b, lb_b, sq_c, lb_c, eq38, eq38b)),
                 FadeIn(hl_ra), FadeIn(steps[0]), FadeIn(steps[1]), run_time=1.3)
        self.cue("That is the hypotenuse",
                 FadeIn(hl_hyp), FadeIn(steps[2]), run_time=1.0)
        self.cue("Square the known lengths, then add or subtract",
                 FadeIn(steps[3]), run_time=1.0)
        self.cue("Take the positive square root and state the length unit",
                 FadeIn(steps[4]), FadeIn(steps[5]), run_time=1.1)

        # Plausibility bounds
        bound1 = small_eq(r"c > a,\; c > b", 30, TEAL).move_to([3.5, -1.6, 0])
        bound2 = small_eq(r"c < a + b", 30, GOLD).move_to([3.5, -2.1, 0])
        self.cue("a hypotenuse exceeds either leg but is shorter than their sum",
                 Write(bound1), Write(bound2), run_time=1.1)

        self.finish()

        # ── Beat 40 ────────────────────────────────────────────────────────────
        self.begin("40")

        # Clear checklist, restore robot diagram with bent route vs diagonal
        self.play(FadeOut(VGroup(checklist, hl_ra, hl_hyp, bound1, bound2)),
                  run_time=0.6)

        bent_pts = [O, E, NE]
        bent = VMobject(color=MUTED, stroke_width=4, stroke_style="dashed")
        bent.set_points_as_corners(bent_pts)
        lbl_bent = txt("4 + 3 = 7 m (route)", 24, MUTED).move_to(
            (O + E + NE)/3 + np.array([0.0, -0.55, 0]))

        diag_solid = Line(O, NE, color=PINK, stroke_width=6)
        lbl_diag   = txt("√(4²+3²) = 5 m", 24, PINK).move_to(
            (O + NE)/2 + np.array([-0.7, 0.3, 0]))

        self.cue("Try explaining one final idea in your own words",
                 Create(bent), FadeIn(lbl_bent), run_time=1.1)
        self.cue("why does four plus three not give the diagonal",
                 Indicate(bent, color=MUTED), run_time=1.0)
        self.cue("The diagonal crosses directly between the same endpoints",
                 Create(diag_solid), FadeIn(lbl_diag), run_time=1.2)

        # Three small outward squares
        sc2 = 0.38
        O2  = np.array([-5.6, -1.5, 0])
        E2  = O2 + np.array([4*sc2, 0, 0])
        NE2 = O2 + np.array([4*sc2, 3*sc2, 0])

        def small_sq(P, Q, col):
            v = Q - P; perp = np.array([-v[1], v[0], 0])
            return Polygon(P, Q, Q+perp, P+perp, color=col, stroke_width=1.5,
                           fill_color=col, fill_opacity=0.22)

        ssq_a = small_sq(O2, E2, TEAL)
        ssq_b = small_sq(E2, NE2, GOLD)
        ssq_c = small_sq(NE2, O2, PINK)

        final_eq = small_eq(r"a^2 + b^2 = c^2", 48, INK).move_to([3.8, 0.5, 0])

        self.cue("To find its length, we compare square areas instead",
                 FadeIn(ssq_a), FadeIn(ssq_b), FadeIn(ssq_c), run_time=1.1)
        self.cue("Taking the square root turns that area relationship into the length",
                 Write(final_eq), run_time=1.3)

        self.finish()
        self.done()
