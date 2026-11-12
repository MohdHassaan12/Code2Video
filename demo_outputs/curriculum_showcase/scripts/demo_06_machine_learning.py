from manim import *

class BackpropScene(Scene):
    def construct(self):
        title = Title("Backpropagation & Gradient Descent").to_edge(UP)
        self.play(Write(title))
        
        # Layer nodes
        layer_in = VGroup(*[Circle(radius=0.3, color=BLUE) for _ in range(3)]).arrange(DOWN, buff=0.6).shift(LEFT*4)
        layer_hid = VGroup(*[Circle(radius=0.3, color=GREEN) for _ in range(4)]).arrange(DOWN, buff=0.4)
        layer_out = VGroup(*[Circle(radius=0.3, color=RED) for _ in range(2)]).arrange(DOWN, buff=0.8).shift(RIGHT*4)
        
        self.play(Create(layer_in), Create(layer_hid), Create(layer_out))
        self.wait(2)