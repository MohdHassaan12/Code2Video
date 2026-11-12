from manim import *

class SVMScene(Scene):
    def construct(self):
        title = Title("Support Vector Machine: Maximum Margin").to_edge(UP)
        self.play(Write(title))
        
        # Hyperplane and Margins
        line_opt = Line([-4, -1, 0], [4, 1.5, 0], color=GREEN)
        line_m1 = Line([-4, 0, 0], [4, 2.5, 0], color=BLUE, stroke_width=2).set_stroke(opacity=0.6)
        line_m2 = Line([-4, -2, 0], [4, 0.5, 0], color=RED, stroke_width=2).set_stroke(opacity=0.6)
        
        self.play(Create(line_opt), Create(line_m1), Create(line_m2))
        self.wait(2)