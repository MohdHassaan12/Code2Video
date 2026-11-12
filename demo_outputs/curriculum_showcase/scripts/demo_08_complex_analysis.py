from manim import *

class EulersFormula(Scene):
    def construct(self):
        title = Title("Euler's Formula: e^{i theta} = cos(theta) + i sin(theta)").to_edge(UP)
        self.play(Write(title))
        
        plane = ComplexPlane(x_range=[-2, 2, 1], y_range=[-2, 2, 1]).scale(1.2).shift(DOWN*0.3)
        circle = Circle(radius=1.2, color=BLUE).move_to(plane.c2p(0, 0))
        self.play(Create(plane), Create(circle))
        
        dot = Dot(plane.c2p(1, 0), color=YELLOW)
        v_pos = Arrow(plane.c2p(0, 0), dot.get_center(), buff=0, color=YELLOW)
        self.play(FadeIn(dot), GrowArrow(v_pos))
        
        self.play(Rotating(dot, about_point=plane.c2p(0, 0), radians=PI, run_time=3))
        self.wait(2)