from manim import *

class BayesTheorem(Scene):
    def construct(self):
        title = Title("Bayes' Theorem: Prior Probability Updating").to_edge(UP)
        self.play(Write(title))
        
        # 2D Unit Square
        square = Square(side_length=4.5, color=WHITE).shift(DOWN*0.3)
        self.play(Create(square))
        
        # Partition into Sick (1%) vs Healthy (99%)
        sick_strip = Rectangle(width=0.045*4.5, height=4.5, color=RED, fill_opacity=0.7).align_to(square, LEFT)
        self.play(FadeIn(sick_strip))
        
        # Positive test area
        self.wait(2)