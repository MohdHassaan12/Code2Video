from manim import *

class NewtonsThirdLaw(Scene):
    def construct(self):
        title = Title("Newton's Third Law: Forces Act on Different Bodies").to_edge(UP)
        self.play(Write(title))
        
        # Body 1: Box A, Body 2: Box B
        box_a = Square(side_length=1.8, color=BLUE, fill_opacity=0.5).shift(LEFT*2.5)
        box_b = Square(side_length=1.8, color=RED, fill_opacity=0.5).shift(RIGHT*2.5)
        lbl_a = Text("Body A").move_to(box_a)
        lbl_b = Text("Body B").move_to(box_b)
        self.play(FadeIn(box_a), FadeIn(box_b), Write(lbl_a), Write(lbl_b))
        
        # Interaction force arrows
        f_ba = Arrow(box_b.get_left(), box_a.get_right(), color=YELLOW, buff=0.1)
        f_ab = Arrow(box_a.get_right(), box_b.get_left(), color=YELLOW, buff=0.1)
        
        self.play(GrowArrow(f_ba), GrowArrow(f_ab))
        self.wait(2)