from manim import *

class DerivativeScene(Scene):
    def construct(self):
        title = Title("The Derivative: Instantaneous Rate of Change").to_edge(UP)
        self.play(Write(title))
        
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 16, 4], x_length=7, y_length=4.5).to_edge(DOWN)
        labels = axes.get_axis_labels(x_label="x", y_label="f(x)")
        curve = axes.plot(lambda x: 0.8 * x**2, color=BLUE)
        self.play(Create(axes), Write(labels), Create(curve))
        
        # Secant point & Tangent point
        dot_p = Dot(axes.c2p(2, 3.2), color=YELLOW)
        dot_q = Dot(axes.c2p(3.5, 9.8), color=RED)
        secant = axes.get_secant_slope_group(2, curve, dx=1.5, secant_line_color=YELLOW)
        self.play(FadeIn(dot_p), FadeIn(dot_q), Create(secant))
        
        # Shrink h -> 0
        self.play(dot_q.animate.move_to(axes.c2p(2.05, 3.36)), run_time=2)
        tangent = TangentLine(curve, alpha=0.4, length=6, color=GREEN)
        self.play(Transform(secant, tangent))
        
        eq = MathTex(r"\frac{df}{dx} = \lim_{h \to 0} \frac{f(x+h)-f(x)}{h} = 2x").to_edge(UP).shift(DOWN*0.8)
        self.play(Write(eq))
        self.wait(2)