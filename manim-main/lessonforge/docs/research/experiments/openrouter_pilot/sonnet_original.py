from manim import *
import numpy as np
import math

class SlopeInterceptDemo(Scene):
    def construct(self):
        # ── Layout constants ──────────────────────────────────────────────
        AX_ORIGIN = LEFT * 3.2 + DOWN * 0.3
        EQ_CENTER = RIGHT * 3.0 + UP * 2.2

        # ── Axes ──────────────────────────────────────────────────────────
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-3, 5, 1],
            x_length=5.6,
            y_length=6.4,
            axis_config={
                "include_numbers": True,
                "numbers_to_include": [-3, -2, -1, 0, 1, 2, 3],
                "font_size": 22,
                "tip_length": 0.18,
            },
            y_axis_config={
                "numbers_to_include": [-3, -2, -1, 0, 1, 2, 3, 4, 5],
            },
        ).move_to(AX_ORIGIN)

        x_label = axes.get_x_axis_label(MathTex("x", font_size=28), direction=RIGHT)
        y_label = axes.get_y_axis_label(MathTex("y", font_size=28), direction=UP)

        # ── Right-panel helpers ───────────────────────────────────────────
        def make_eq(m_val, b_val):
            m_str = "" if m_val == 1 else ("-" if m_val == -1 else f"{m_val:+.1f}".lstrip("+") if m_val < 0 else f"{m_val:.1f}")
            b_sign = "+" if b_val >= 0 else "-"
            b_abs = abs(b_val)
            if m_val == 1:
                eq_str = rf"y = x {b_sign} {b_abs:.1f}"
            elif m_val == -1:
                eq_str = rf"y = -x {b_sign} {b_abs:.1f}"
            else:
                eq_str = rf"y = {m_val:.1f}x {b_sign} {b_abs:.1f}"
            return MathTex(eq_str, font_size=36).move_to(EQ_CENTER)

        def make_label(text_str, row=0):
            t = Text(text_str, font_size=24)
            t.move_to(RIGHT * 3.0 + UP * (1.3 - row * 0.55))
            return t

        # ── Clip line to axis bounds ──────────────────────────────────────
        def clipped_line(m, b):
            x0, x1 = -3.0, 3.0
            y0, y1 = -3.0, 5.0
            pts = []
            # left edge x=-3
            y = m * (-3) + b
            if y0 <= y <= y1:
                pts.append((-3, y))
            # right edge x=3
            y = m * 3 + b
            if y0 <= y <= y1:
                pts.append((3, y))
            # bottom edge y=-3
            if m != 0:
                x = (-3 - b) / m
                if x0 <= x <= x1:
                    pts.append((x, -3))
            # top edge y=5
            if m != 0:
                x = (5 - b) / m
                if x0 <= x <= x1:
                    pts.append((x, 5))
            elif b == -3:
                pts.append((-3, -3)); pts.append((3, -3))
            elif b == 5:
                pts.append((-3, 5)); pts.append((3, 5))
            # deduplicate
            unique = []
            for p in pts:
                if not any(abs(p[0]-q[0]) < 1e-9 and abs(p[1]-q[1]) < 1e-9 for q in unique):
                    unique.append(p)
            if len(unique) < 2:
                return Line(axes.c2p(-3, m*(-3)+b), axes.c2p(3, m*3+b), color=YELLOW, stroke_width=3)
            unique.sort(key=lambda p: p[0])
            return Line(axes.c2p(unique[0][0], unique[0][1]),
                        axes.c2p(unique[-1][0], unique[-1][1]),
                        color=YELLOW, stroke_width=3)

        # ═══════════════════════════════════════════════════════════════════
        # STAGE A  (0 – 30 s)
        # ═══════════════════════════════════════════════════════════════════

        # 0-3 s  draw axes
        self.play(Create(axes), Write(x_label), Write(y_label), run_time=3)

        # 3-5 s  show initial equation y = x + 1
        eq_A = make_eq(1, 1)
        self.play(Write(eq_A), run_time=2)

        # 5-8 s  draw line y=x+1
        line_A = clipped_line(1, 1)
        self.play(Create(line_A), run_time=3)

        # 8-11 s  mark y-intercept (0,1)
        dot_b = Dot(axes.c2p(0, 1), color=RED, radius=0.1)
        lbl_b = MathTex("(0,1)", font_size=28, color=RED).next_to(dot_b, RIGHT, buff=0.15)
        info1 = make_label("y-intercept b = 1", row=0)
        self.play(FadeIn(dot_b), Write(lbl_b), Write(info1), run_time=3)

        # 11-13 s  pause
        self.wait(2)

        # 13-16 s  show slope=1 label
        info2 = make_label("slope m = 1", row=1)
        self.play(Write(info2), run_time=2)

        # 16-19 s  draw rise/run triangle for m=1 on y=x+1
        # run from x=0 to x=1, rise from y=1 to y=2
        p_start = axes.c2p(0, 1)
        p_run   = axes.c2p(1, 1)
        p_end   = axes.c2p(1, 2)
        tri_run  = Line(p_start, p_run,  color=GREEN,  stroke_width=3)
        tri_rise = Line(p_run,   p_end,  color=ORANGE, stroke_width=3)
        lbl_run  = MathTex(r"\Delta x=1", font_size=24, color=GREEN).next_to(
            axes.c2p(0.5, 1), DOWN, buff=0.12)
        lbl_rise = MathTex(r"\Delta y=1", font_size=24, color=ORANGE).next_to(
            axes.c2p(1, 1.5), RIGHT, buff=0.12)
        self.play(Create(tri_run), Create(tri_rise),
                  Write(lbl_run), Write(lbl_rise), run_time=3)

        # 19-21 s  pause
        self.wait(2)

        # 21-24 s  vary b: animate line from b=1 to b=2
        info3 = make_label("increase b: line shifts up", row=2)
        self.play(Write(info3), run_time=1)

        line_A2 = clipped_line(1, 2)
        eq_A2   = make_eq(1, 2)
        dot_b2  = Dot(axes.c2p(0, 2), color=RED, radius=0.1)
        lbl_b2  = MathTex("(0,2)", font_size=28, color=RED).next_to(dot_b2, RIGHT, buff=0.15)

        self.play(
            Transform(line_A, line_A2),
            Transform(eq_A, eq_A2),
            Transform(dot_b, dot_b2),
            Transform(lbl_b, lbl_b2),
            run_time=3,
        )

        # 24-27 s  show slope still 1
        info4 = make_label(r"slope still = 1", row=3)
        self.play(Write(info4), run_time=2)

        # 27-30 s  pause / thinking pause
        self.wait(3)

        # ═══════════════════════════════════════════════════════════════════
        # TRANSITION  (30 – 33 s)
        # ═══════════════════════════════════════════════════════════════════

        # clean up Stage A annotations, keep axes + line
        self.play(
            FadeOut(info1), FadeOut(info2), FadeOut(info3), FadeOut(info4),
            FadeOut(tri_run), FadeOut(tri_rise),
            FadeOut(lbl_run), FadeOut(lbl_rise),
            FadeOut(lbl_b), FadeOut(dot_b),
            run_time=2,
        )

        # reset line to b=1, m=1
        line_B_init = clipped_line(1, 1)
        eq_B = make_eq(1, 1)
        dot_pivot = Dot(axes.c2p(0, 1), color=RED, radius=0.1)
        lbl_pivot = MathTex("(0,1)", font_size=28, color=RED).next_to(dot_pivot, RIGHT, buff=0.15)

        self.play(
            Transform(line_A, line_B_init),
            Transform(eq_A, eq_B),
            FadeIn(dot_pivot), Write(lbl_pivot),
            run_time=1,
        )

        # ═══════════════════════════════════════════════════════════════════
        # STAGE B  (33 – 60 s)
        # ═══════════════════════════════════════════════════════════════════

        # 33-35 s  Stage B title
        title_B = make_label("Stage B: vary slope m", row=0)
        self.play(Write(title_B), run_time=2)

        # 35-38 s  keep b=1, vary m from 1 to 0.5
        info_B1 = make_label("b = 1 fixed, pivot at (0,1)", row=1)
        self.play(Write(info_B1), run_time=2)

        # 38-42 s  animate m from 1 to -1 in steps
        # Step 1: m=1 -> m=0 (3 s)
        line_m0  = clipped_line(0, 1)
        eq_m0    = make_eq(0, 1)
        info_m0  = make_label("m = 0  (horizontal)", row=2)
        self.play(
            Transform(line_A, line_m0),
            Transform(eq_A, eq_m0),
            Write(info_m0),
            run_time=3,
        )
        self.wait(1)

        # Step 2: m=0 -> m=-1 (3 s)
        line_m1n = clipped_line(-1, 1)
        eq_m1n   = make_eq(-1, 1)
        info_m1n = make_label("m = -1  (negative slope)", row=3)
        self.play(
            Transform(line_A, line_m1n),
            Transform(eq_A, eq_m1n),
            FadeOut(info_m0),
            Write(info_m1n),
            run_time=3,
        )

        # 45-47 s  pause
        self.wait(2)

        # 47-51 s  draw signed rise/run triangle for m=-1
        # run from x=0 to x=1, rise from y=1 to y=0 (negative)
        p0  = axes.c2p(0, 1)
        p1  = axes.c2p(1, 1)
        p2  = axes.c2p(1, 0)
        tri2_run  = Line(p0, p1, color=GREEN,  stroke_width=3)
        tri2_rise = Line(p1, p2, color=ORANGE, stroke_width=3)
        lbl2_run  = MathTex(r"\Delta x=1",  font_size=24, color=GREEN).next_to(
            axes.c2p(0.5, 1), UP, buff=0.12)
        lbl2_rise = MathTex(r"\Delta y=-1", font_size=24, color=ORANGE).next_to(
            axes.c2p(1, 0.5), RIGHT, buff=0.12)
        slope_frac = MathTex(r"m = \frac{\Delta y}{\Delta x} = \frac{-1}{1} = -1",
                             font_size=30).move_to(RIGHT * 3.0 + DOWN * 0.5)

        self.play(
            Create(tri2_run), Create(tri2_rise),
            Write(lbl2_run), Write(lbl2_rise),
            run_time=2,
        )
        self.play(Write(slope_frac), run_time=2)

        # 51-54 s  pause / thinking pause
        self.wait(3)

        # 54-57 s  summary text
        summary1 = make_label("b shifts line vertically", row=4)
        summary2 = Text("m controls steepness & direction",
                        font_size=24).move_to(RIGHT * 3.0 + UP * (1.3 - 4 * 0.55) - DOWN * 0.55)

        self.play(Write(summary1), run_time=1.5)
        self.play(Write(summary2), run_time=1.5)

        # 57-60 s  final pause – preserve graph and labels
        self.wait(3)