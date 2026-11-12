from manim import *

class EigenvectorScene(LinearTransformationScene):
    def construct(self):
        title = Title("Eigenvectors: Invariant Directions").to_edge(UP)
        self.add_title(title)
        
        v_eig = Vector([2, 1], color=YELLOW)
        v_norm = Vector([1, 2], color=RED)
        self.add_vector(v_eig)
        self.add_vector(v_norm)
        
        matrix = [[3, 0], [1, 2]]
        self.apply_matrix(matrix)
        self.wait(2)