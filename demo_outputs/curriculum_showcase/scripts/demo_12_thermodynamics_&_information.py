from manim import *

class ShannonEntropy(Scene):
    def construct(self):
        title = Title("Claude Shannon's Entropy: H(X) = -sum p log_2 p").to_edge(UP)
        self.play(Write(title))
        
        axes = Axes(x_range=[0, 1, 0.2], y_range=[0, 1.2, 0.2], x_length=7, y_length=4.5).to_edge(DOWN)
        labels = axes.get_axis_labels(x_label="p", y_label="H(p)")
        
        # Entropy curve -p log2 p - (1-p) log2 (1-p)
        curve = axes.plot(
            lambda p: -p * np.log2(p) - (1-p) * np.log2(1-p) if 0 < p < 1 else 0,
            x_range=[0.001, 0.999],
            color=YELLOW
        )
        self.play(Create(axes), Write(labels), Create(curve))
        self.wait(2)