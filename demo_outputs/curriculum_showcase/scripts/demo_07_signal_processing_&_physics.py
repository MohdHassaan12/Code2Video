from manim import *

class FourierEpicycles(Scene):
    def construct(self):
        title = Title("Fourier Transform: Center of Mass").to_edge(UP)
        self.play(Write(title))
        
        circle_1 = Circle(radius=1.8, color=BLUE).shift(LEFT*2.5)
        v1 = Arrow(circle_1.get_center(), circle_1.point_at_angle(PI/4), buff=0, color=YELLOW)
        circle_2 = Circle(radius=0.7, color=GREEN).move_to(v1.get_end())
        v2 = Arrow(circle_2.get_center(), circle_2.point_at_angle(3*PI/4), buff=0, color=RED)
        
        self.play(Create(circle_1), GrowArrow(v1), Create(circle_2), GrowArrow(v2))
        self.wait(2)