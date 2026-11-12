from manim import *
import math
import numpy as np

class SlopeInterceptDemo(Scene):
    def construct(self):
        # Configuration
        AXES_X_RANGE = [-3, 3, 1]
        AXES_Y_RANGE = [-3, 5, 1]
        AXES_X_LENGTH = 6
        AXES_Y_LENGTH = 8
        GRAPH_ORIGIN = LEFT * 4
        TEXT_RIGHT_X = 2.5
        TEXT_RIGHT_Y_TOP = 3.5
        TEXT_RIGHT_Y_SPACING = 0.8
        TEXT_WIDTH = 5.5

        # --- Beat 1: Varying y-intercept (b) ---
        # Setup axes
        axes = Axes(
            x_range=AXES_X_RANGE,
            y_range=AXES_Y_RANGE,
            x_length=AXES_X_LENGTH,
            y_length=AXES_Y_LENGTH,
            axis_config={"include_numbers": True, "font_size": 24},
            tips=False
        ).shift(GRAPH_ORIGIN)

        x_label = axes.get_x_axis_label(Tex("$x$"), edge=RIGHT, direction=RIGHT, buff=0.2)
        y_label = axes.get_y_axis_label(Tex("$y$"), edge=UP, direction=UP, buff=0.2)
        graph_labels = VGroup(x_label, y_label)

        self.play(Create(axes), Create(graph_labels))
        self.wait(1)

        # Initial line y = x + 1
        m_val = ValueTracker(1)
        b_val = ValueTracker(1)

        def get_line(m, b):
            return axes.get_graph(lambda x: m * x + b, x_range=[AXES_X_RANGE[0], AXES_X_RANGE[1]], color=BLUE)

        line1 = always_redraw(lambda: get_line(m_val.get_value(), b_val.get_value()))
        self.play(Create(line1))
        self.wait(0.5)

        # Equation display
        equation_text = MathTex("y = mx + b").shift(RIGHT * TEXT_RIGHT_X + UP * TEXT_RIGHT_Y_TOP)
        self.play(Write(equation_text))
        self.wait(0.5)

        current_equation = always_redraw(
            lambda: MathTex(f"y = {m_val.get_value():.0f}x + {b_val.get_value():.0f}")
            .next_to(equation_text, DOWN, buff=0.5)
            .align_to(equation_text, LEFT)
        )
        self.play(Create(current_equation))
        self.wait(1)

        # Identify y-intercept (0,1)
        y_intercept_point = always_redraw(lambda: Dot(axes.c2p(0, b_val.get_value()), color=RED))
        y_intercept_label = always_redraw(
            lambda: MathTex(f"(0, {b_val.get_value():.0f})")
            .next_to(y_intercept_point, UP + RIGHT, buff=0.1)
            .set_color(RED)
        )
        self.play(Create(y_intercept_point), Write(y_intercept_label))
        self.wait(1)

        # Explanation for b
        b_explanation = Text("b is the y-intercept", font_size=28).next_to(current_equation, DOWN, buff=TEXT_RIGHT_Y_SPACING).align_to(current_equation, LEFT)
        self.play(Write(b_explanation))
        self.wait(1)

        # Vary b from 1 to 2
        self.play(b_val.animate.set_value(2), run_time=3)
        self.wait(1)

        # Show delta y / delta x for m=1
        delta_x_line = Line(axes.c2p(0, 1), axes.c2p(1, 1), color=YELLOW)
        delta_y_line = Line(axes.c2p(1, 1), axes.c2p(1, 2), color=GREEN)
        delta_x_label = MathTex("\\Delta x = 1", font_size=28).next_to(delta_x_line, DOWN, buff=0.1).set_color(YELLOW)
        delta_y_label = MathTex("\\Delta y = 1", font_size=28).next_to(delta_y_line, RIGHT, buff=0.1).set_color(GREEN)

        self.play(
            Create(delta_x_line),
            Create(delta_y_line),
            Write(delta_x_label),
            Write(delta_y_label)
        )
        self.wait(2)

        slope_ratio_text = MathTex("\\frac{\\Delta y}{\\Delta x} = \\frac{1}{1} = 1", font_size=32).next_to(b_explanation, DOWN, buff=TEXT_RIGHT_Y_SPACING).align_to(b_explanation, LEFT)
        m_explanation = Text("m is the slope", font_size=28).next_to(slope_ratio_text, DOWN, buff=TEXT_RIGHT_Y_SPACING).align_to(slope_ratio_text, LEFT)
        self.play(Write(slope_ratio_text))
        self.play(Write(m_explanation))
        self.wait(2)

        # Cleanup for next beat
        self.play(
            FadeOut(delta_x_line), FadeOut(delta_y_line),
            FadeOut(delta_x_label), FadeOut(delta_y_label),
            FadeOut(b_explanation), FadeOut(slope_ratio_text),
            FadeOut(m_explanation)
        )
        self.wait(1)

        # --- Beat 2: Varying slope (m) ---
        # Reset b to 1, keep m=1 initially
        self.play(b_val.animate.set_value(1), run_time=1.5)
        self.wait(0.5)

        # Pivot point (0,1) remains
        pivot_point = Dot(axes.c2p(0, 1), color=RED)
        pivot_label = MathTex("(0,1)").next_to(pivot_point, UP + RIGHT, buff=0.1).set_color(RED)
        self.play(
            Transform(y_intercept_point, pivot_point),
            Transform(y_intercept_label, pivot_label)
        )
        self.wait(1)

        # Vary m from 1 to -1
        m_val.set_value(1) # Ensure m starts at 1
        self.play(m_val.animate.set_value(-1), run_time=5)
        self.wait(1)

        # Show rise/run triangle for final line (y = -x + 1)
        # From (0,1) to (1,0)
        rise_line = always_redraw(
            lambda: Line(axes.c2p(0, b_val.get_value()), axes.c2p(1, b_val.get_value()), color=YELLOW)
        )
        run_line = always_redraw(
            lambda: Line(axes.c2p(1, b_val.get_value()), axes.c2p(1, b_val.get_value() + m_val.get_value()), color=GREEN)
        )

        rise_label = always_redraw(
            lambda: MathTex(f"\\Delta x = 1", font_size=28)
            .next_to(rise_line, DOWN, buff=0.1)
            .set_color(YELLOW)
        )
        run_label = always_redraw(
            lambda: MathTex(f"\\Delta y = {m_val.get_value():.0f}", font_size=28)
            .next_to(run_line, RIGHT, buff=0.1)
            .set_color(GREEN)
        )

        self.play(
            Create(rise_line),
            Create(run_line),
            Write(rise_label),
            Write(run_label)
        )
        self.wait(2)

        final_slope_ratio = always_redraw(
            lambda: MathTex(f"\\frac{{\\Delta y}}{{\\Delta x}} = \\frac{{{m_val.get_value():.0f}}}{{1}} = {m_val.get_value():.0f}", font_size=32)
            .next_to(current_equation, DOWN, buff=TEXT_RIGHT_Y_SPACING)
            .align_to(current_equation, LEFT)
        )
        self.play(Create(final_slope_ratio))
        self.wait(2)

        # Final cleanup of updaters
        self.remove(line1, current_equation, y_intercept_point, y_intercept_label, rise_line, run_line, rise_label, run_label, final_slope_ratio)
        self.wait(1)

        # Final state for 60s mark
        final_line = get_line(m_val.get_value(), b_val.get_value())
        final_equation = MathTex(f"y = {m_val.get_value():.0f}x + {b_val.get_value():.0f}").next_to(equation_text, DOWN, buff=0.5).align_to(equation_text, LEFT)
        final_y_intercept_point = Dot(axes.c2p(0, b_val.get_value()), color=RED)
        final_y_intercept_label = MathTex(f"(0, {b_val.get_value():.0f})").next_to(final_y_intercept_point, UP + RIGHT, buff=0.1).set_color(RED)
        final_rise_line = Line(axes.c2p(0, b_val.get_value()), axes.c2p(1, b_val.get_value()), color=YELLOW)
        final_run_line = Line(axes.c2p(1, b_val.get_value()), axes.c2p(1, b_val.get_value() + m_val.get_value()), color=GREEN)
        final_rise_label = MathTex(f"\\Delta x = 1", font_size=28).next_to(final_rise_line, DOWN, buff=0.1).set_color(YELLOW)
        final_run_label = MathTex(f"\\Delta y = {m_val.get_value():.0f}", font_size=28).next_to(final_run_line, RIGHT, buff=0.1).set_color(GREEN)
        final_slope_ratio_static = MathTex(f"\\frac{{\\Delta y}}{{\\Delta x}} = \\frac{{{m_val.get_value():.0f}}}{{1}} = {m_val.get_value():.0f}", font_size=32).next_to(final_equation, DOWN, buff=TEXT_RIGHT_Y_SPACING).align_to(final_equation, LEFT)

        self.add(final_line, final_equation, final_y_intercept_point, final_y_intercept_label, final_rise_line, final_run_line, final_rise_label, final_run_label, final_slope_ratio_static)
        self.wait(1) # Final pause to reach 60 seconds