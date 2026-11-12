from manim import *

class PythagorasProof(Scene):
    def construct(self):
        title = Title("Visual Proof: a^2 + b^2 = c^2").to_edge(UP)
        self.play(Write(title))
        
        # Outer square (a+b) x (a+b)
        outer_box = Square(side_length=5, color=WHITE).shift(DOWN*0.3)
        self.play(Create(outer_box))
        
        # Two internal squares
        sq_a = Square(side_length=2, color=BLUE, fill_opacity=0.7).align_to(outer_box, DL)
        sq_b = Square(side_length=3, color=GREEN, fill_opacity=0.7).align_to(outer_box, UR)
        lbl_a = MathTex("a^2").move_to(sq_a.get_center())
        lbl_b = MathTex("b^2").move_to(sq_b.get_center())
        self.play(FadeIn(sq_a), FadeIn(sq_b), Write(lbl_a), Write(lbl_b))
        self.wait(1)
        
        # Transform to central c^2 square
        sq_c = Square(side_length=3.6, color=YELLOW, fill_opacity=0.7).rotate(PI/6).move_to(outer_box.get_center())
        lbl_c = MathTex("c^2").move_to(sq_c.get_center())
        self.play(ReplacementTransform(VGroup(sq_a, sq_b), sq_c),
                  ReplacementTransform(VGroup(lbl_a, lbl_b), lbl_c))
        self.wait(2)