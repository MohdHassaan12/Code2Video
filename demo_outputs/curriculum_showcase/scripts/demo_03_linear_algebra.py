from manim import *

class DeterminantScene(LinearTransformationScene):
    def __init__(self):
        super().__init__(show_coordinates=True, leave_ghost_vectors=True)

    def construct(self):
        title = Title("The Determinant: Area Scaling").to_edge(UP)
        self.add_title(title)
        
        matrix = [[3, 1], [0, 2]]
        self.apply_matrix(matrix)
        self.wait(1)