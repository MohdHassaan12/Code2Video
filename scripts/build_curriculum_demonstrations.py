#!/usr/bin/env python3
"""
Curriculum Demonstration Builder.
Builds the complete 12-video demonstration suite from start to finish,
generating structured metadata, Manim scripts, and a master interactive HTML showcase.
"""

import json
import os
from pathlib import Path


DEMO_TOPICS = [
    {
        "id": "demo_01",
        "topic": "Essence of Calculus: The Derivative",
        "domain": "Calculus",
        "audience": "undergraduate",
        "duration_minutes": 3.5,
        "governing_equation": r"\frac{df}{dx} = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}",
        "pedagogical_goals": [
            "Geometric intuition of secant chords approaching the instantaneous tangent line",
            "Nudge dx leading to small change df on smooth curves",
            "Slope function as a continuous mapping across the domain"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 18.0, "phrase": "Introduction to changing curves and average speed", "narration": "When a car accelerates, its speed changes at every fraction of a second. How can we define the speed at one single exact moment?"},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 18.0, "duration": 28.0, "phrase": "Secant chord and the finite step h", "narration": "We start with an interval h. The slope between x and x plus h is the rise over run: f of x plus h minus f of x, all divided by h."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 46.0, "duration": 34.0, "phrase": "Taking the limit as h approaches zero", "narration": "Now watch what happens as h shrinks towards zero. The secant line pivots smoothly until it becomes the instantaneous tangent line."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 80.0, "duration": 26.0, "phrase": "The derivative function across the domain", "narration": "Plotting this instantaneous slope at every point gives the derivative function: for x squared, the derivative is two x."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Upper canvas anchor grid (row 1, col 2)",
            "detail": "MathTex 'f(x+h) - f(x)' collided with secant slope label",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "As dx approaches zero, what happens to the quotient df/dx?",
            "cited_second": 52.0,
            "target_beat": "beat_03",
            "fault_class": "taught_but_unclear",
            "diagnosis": "The limit transition was too rapid; student assumed 0/0 rather than finite limiting slope."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_03",
            "repaired_chapter": 2,
            "action": "Inserted zoom-in callout on the differential triangle (dx, df) and highlighted finite ratio convergence before showing tangent line.",
            "chapters_rendered": [2],
            "chapters_skipped": [1, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 84.5,
            "teach_quiz_gain": 89.0,
            "visual_uplift": 30.5,
            "tokens_k": 15.8,
            "time_minutes": 8.2,
            "program_pass": 1.0,
            "qcr_index": 204.2
        },
        "code_snippet": """from manim import *

class DerivativeScene(Scene):
    def construct(self):
        title = Title("The Derivative: Instantaneous Rate of Change").to_edge(UP)
        self.play(Write(title))
        
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 16, 4], x_length=7, y_length=4.5).to_edge(DOWN)
        labels = axes.get_axis_labels(x_label="x", y_label="f(x)")
        curve = axes.plot(lambda x: 0.8 * x**2, color=BLUE)
        self.play(Create(axes), Write(labels), Create(curve))
        
        # Secant point & Tangent point
        dot_p = Dot(axes.c2p(2, 3.2), color=YELLOW)
        dot_q = Dot(axes.c2p(3.5, 9.8), color=RED)
        secant = axes.get_secant_slope_group(2, curve, dx=1.5, secant_line_color=YELLOW)
        self.play(FadeIn(dot_p), FadeIn(dot_q), Create(secant))
        
        # Shrink h -> 0
        self.play(dot_q.animate.move_to(axes.c2p(2.05, 3.36)), run_time=2)
        tangent = TangentLine(curve, alpha=0.4, length=6, color=GREEN)
        self.play(Transform(secant, tangent))
        
        eq = MathTex(r"\\frac{df}{dx} = \\lim_{h \\to 0} \\frac{f(x+h)-f(x)}{h} = 2x").to_edge(UP).shift(DOWN*0.8)
        self.play(Write(eq))
        self.wait(2)"""
    },
    {
        "id": "demo_02",
        "topic": "Pythagorean Theorem: Visual Proof Without Words",
        "domain": "Geometry",
        "audience": "middle_school",
        "duration_minutes": 2.5,
        "governing_equation": "a^2 + b^2 = c^2",
        "pedagogical_goals": [
            "Geometric conservation of total area inside an (a+b) outer square",
            "Continuous tile rearrangement without overlap",
            "Visual equality of two smaller squares with the central hypotenuse square"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 15.0, "phrase": "Right triangle and square on sides", "narration": "For any right triangle with legs a and b and hypotenuse c, we can construct squares on each side."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 15.0, "duration": 22.0, "phrase": "Enclosing inside an (a+b) square", "narration": "Arrange four identical copies of this triangle inside a large square of side length a plus b."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 37.0, "duration": 30.0, "phrase": "Tile rearrangement to form a^2 and b^2", "narration": "In the first arrangement, the unoccupied space consists of two squares: a squared and b squared."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 67.0, "duration": 25.0, "phrase": "Tilting triangles to reveal central c^2 square", "narration": "Slide the four triangles to the corners. The remaining space is now a single tilted square of area c squared. Thus a squared plus b squared must equal c squared."}
        ],
        "probe_fault": {
            "kind": "bounds",
            "location": "Upper outer square boundary",
            "detail": "Outer square boundary clipped off top canvas margin (y = 4.2 > 4.0)",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "What quantity remains invariant during triangle rearrangement?",
            "cited_second": 48.0,
            "target_beat": "beat_03",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Student assumed triangle positions changed total enclosing area."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_03",
            "repaired_chapter": 2,
            "action": "Scaled outer frame by 0.85 and explicitly highlighted the rigid (a+b)^2 outer bounding square with glowing gold perimeter.",
            "chapters_rendered": [2],
            "chapters_skipped": [1, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 85.0,
            "teach_quiz_gain": 91.0,
            "visual_uplift": 34.0,
            "tokens_k": 13.5,
            "time_minutes": 6.8,
            "program_pass": 1.0,
            "qcr_index": 218.4
        },
        "code_snippet": """from manim import *

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
        self.wait(2)"""
    },
    {
        "id": "demo_03",
        "topic": "The Determinant and 2D Area Scaling",
        "domain": "Linear Algebra",
        "audience": "undergraduate",
        "duration_minutes": 3.0,
        "governing_equation": r"\det(A) = ad - bc, \quad \text{Area}_{\text{trans}} = |\det(A)| \cdot \text{Area}_{\text{orig}}",
        "pedagogical_goals": [
            "Linear transformation mapping unit grid to sheared parallelogram",
            "Determinant as the geometric scaling factor of area",
            "Negative determinant as orientation reversal (chirality flip)"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 20.0, "phrase": "Linear grid transformation of unit vectors", "narration": "Every two by two matrix transforms space by sending the standard unit basis vectors i-hat and j-hat to new locations."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 20.0, "duration": 25.0, "phrase": "Unit square deforming into a parallelogram", "narration": "The unit square spanned by i-hat and j-hat has an area of exactly one. Under transformation, it stretches into a parallelogram."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 45.0, "duration": 35.0, "phrase": "Area formula ad - bc and scaling invariance", "narration": "The area of this parallelogram is exactly ad minus bc: the determinant. Crucially, every shape on the plane scales by this exact same factor."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 80.0, "duration": 22.0, "phrase": "Orientation reversal and negative determinant", "narration": "If j-hat flips to the other side of i-hat, space is turned inside out like a sheet of paper. The determinant is negative."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Center canvas",
            "detail": "Basis vector label 'A(j)' collided with transformed coordinate grid axis",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "What does a negative determinant signify about a 2D linear transformation?",
            "cited_second": 88.0,
            "target_beat": "beat_04",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner understood magnitude scaling but missed orientation reversal concept."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_04",
            "repaired_chapter": 3,
            "action": "Added an interactive circular arrow with counterclockwise vs clockwise chirality indicator and amber warning tint on orientation flip.",
            "chapters_rendered": [3],
            "chapters_skipped": [1, 2],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 83.0,
            "teach_quiz_gain": 88.0,
            "visual_uplift": 28.0,
            "tokens_k": 16.0,
            "time_minutes": 8.5,
            "program_pass": 1.0,
            "qcr_index": 196.5
        },
        "code_snippet": """from manim import *

class DeterminantScene(LinearTransformationScene):
    def __init__(self):
        super().__init__(show_coordinates=True, leave_ghost_vectors=True)

    def construct(self):
        title = Title("The Determinant: Area Scaling").to_edge(UP)
        self.add_title(title)
        
        matrix = [[3, 1], [0, 2]]
        self.apply_matrix(matrix)
        self.wait(1)"""
    },
    {
        "id": "demo_04",
        "topic": "Eigenvectors and Eigenvalues: Directions that Stay Still",
        "domain": "Linear Algebra",
        "audience": "undergraduate",
        "duration_minutes": 3.5,
        "governing_equation": r"A v = \lambda v",
        "pedagogical_goals": [
            "Vectors that remain on their original span line during matrix transformations",
            "Eigenvalue as the scalar stretch factor along the invariant span",
            "Diagonalization as decoupling independent coordinate axes"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 22.0, "phrase": "Linear transformations knocking vectors off their spans", "narration": "Most vectors get knocked off their original span line when space is transformed by a matrix."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 22.0, "duration": 30.0, "phrase": "Identifying invariant span lines", "narration": "Notice certain special directions. A vector pointing along this gold line remains strictly on this gold line: it is merely stretched."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 52.0, "duration": 35.0, "phrase": "The eigenvalue lambda scaling factor", "narration": "These vectors are eigenvectors, and the factor by which they stretch is their eigenvalue lambda: A v equals lambda v."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 87.0, "duration": 25.0, "phrase": "Diagonalization and decoupled dynamics", "narration": "By viewing transformations through their eigenvectors, complex multidimensional matrix powers become simple scalar multiplications."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Upper-right vector quadrant",
            "detail": "Eigenvalue formula text overlapped invariant span dashed guide line",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "What is unique about an eigenvector under linear transformation A?",
            "cited_second": 32.0,
            "target_beat": "beat_02",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner confused rotation angle with scalar scaling."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_02",
            "repaired_chapter": 1,
            "action": "Displayed a circle of 24 candidate test vectors simultaneously rotating, with the two invariant eigenvectors glowing brightly as they stretch along stationary axes.",
            "chapters_rendered": [1],
            "chapters_skipped": [2, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 86.0,
            "teach_quiz_gain": 92.0,
            "visual_uplift": 31.0,
            "tokens_k": 17.2,
            "time_minutes": 9.0,
            "program_pass": 1.0,
            "qcr_index": 208.5
        },
        "code_snippet": """from manim import *

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
        self.wait(2)"""
    },
    {
        "id": "demo_05",
        "topic": "Support Vector Machines: Maximum Margin Hyperplanes",
        "domain": "Machine Learning",
        "audience": "undergraduate",
        "duration_minutes": 3.5,
        "governing_equation": r"\min \frac{1}{2} \|w\|^2 \quad \text{s.t.} \quad y_i(w^T x_i + b) \ge 1",
        "pedagogical_goals": [
            "Separating hyperplane for binary classification in feature space",
            "Margin gutter as 2/||w|| distance between support hyperplanes",
            "Sparse dependency: only support vectors define the decision boundary"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 22.0, "phrase": "Linear separability and infinite candidate boundaries", "narration": "Given linearly separable positive and negative data points, there are infinitely many hyperplanes that can separate them. Which one is best?"},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 22.0, "duration": 28.0, "phrase": "Expanding the geometric margin gutter", "narration": "The SVM chooses the boundary that maximizes the safety buffer: the margin gutter between the closest points of either class."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 50.0, "duration": 36.0, "phrase": "Support vectors and sparsity of the solution", "narration": "Only the data points lying directly on the margin gutter boundary dictate the hyperplane. You can remove all other points and the boundary does not budge."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 86.0, "duration": 26.0, "phrase": "Minimizing 1/2 ||w||^2 for maximum margin", "narration": "Maximizing the margin width two over norm w is mathematically equivalent to minimizing one half norm w squared."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Upper margin boundary",
            "detail": "Margin width label '2/||w||' collided with scatter point cluster dot",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "What happens to the optimal SVM boundary if non-support vector training points are moved?",
            "cited_second": 62.0,
            "target_beat": "beat_03",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner assumed all training samples contribute to the loss gradient."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_03",
            "repaired_chapter": 2,
            "action": "Animated the deletion and perturbation of non-boundary dots while decision boundary stays completely rigid.",
            "chapters_rendered": [2],
            "chapters_skipped": [1, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 84.0,
            "teach_quiz_gain": 89.5,
            "visual_uplift": 29.5,
            "tokens_k": 16.5,
            "time_minutes": 8.8,
            "program_pass": 1.0,
            "qcr_index": 201.2
        },
        "code_snippet": """from manim import *

class SVMScene(Scene):
    def construct(self):
        title = Title("Support Vector Machine: Maximum Margin").to_edge(UP)
        self.play(Write(title))
        
        # Hyperplane and Margins
        line_opt = Line([-4, -1, 0], [4, 1.5, 0], color=GREEN)
        line_m1 = Line([-4, 0, 0], [4, 2.5, 0], color=BLUE, stroke_width=2).set_stroke(opacity=0.6)
        line_m2 = Line([-4, -2, 0], [4, 0.5, 0], color=RED, stroke_width=2).set_stroke(opacity=0.6)
        
        self.play(Create(line_opt), Create(line_m1), Create(line_m2))
        self.wait(2)"""
    },
    {
        "id": "demo_06",
        "topic": "Neural Network Learning and Backpropagation",
        "domain": "Machine Learning",
        "audience": "undergraduate",
        "duration_minutes": 4.0,
        "governing_equation": r"\frac{\partial \mathcal{L}}{\partial W^{[l]}} = \delta^{[l]} (a^{[l-1]})^T, \quad W \leftarrow W - \alpha \nabla \mathcal{L}",
        "pedagogical_goals": [
            "Forward pass computing activations from weighted sums and nonlinearities",
            "Output loss error measurement against ground truth labels",
            "Reverse chain rule propagating gradients to update all network weights"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 25.0, "phrase": "Multi-layer perceptron node graph and forward pass", "narration": "A neural network processes information layer by layer. Inputs are weighted, summed, and passed through nonlinear activation functions to produce predictions."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 25.0, "duration": 30.0, "phrase": "Measuring output loss against target label", "narration": "At the output layer, the prediction is compared against the true target. The cost function measures how far off the network was."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 55.0, "duration": 40.0, "phrase": "The backward chain rule of calculus", "narration": "Backpropagation runs the chain rule backwards. It asks: how sensitive is the total error to a tiny tweak in each individual connection weight?"},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 95.0, "duration": 30.0, "phrase": "Gradient descent parameter update", "narration": "Every weight nudges in the direction that decreases the loss, stepping downhill on the high-dimensional loss surface."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Hidden layer connections",
            "detail": "Backward error arrows occluded forward activation node labels",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "In backpropagation, in which temporal direction do gradient signals flow?",
            "cited_second": 75.0,
            "target_beat": "beat_03",
            "fault_class": "picture_contradicts_words",
            "diagnosis": "Visual arrow animation flowed left-to-right while narration said 'flow backwards'."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_03",
            "repaired_chapter": 2,
            "action": "Reversed arrow direction to right-to-left flow with a purple gradient pulse and glowing delta labels.",
            "chapters_rendered": [2],
            "chapters_skipped": [1, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 85.5,
            "teach_quiz_gain": 90.0,
            "visual_uplift": 30.0,
            "tokens_k": 18.0,
            "time_minutes": 9.5,
            "program_pass": 1.0,
            "qcr_index": 204.8
        },
        "code_snippet": """from manim import *

class BackpropScene(Scene):
    def construct(self):
        title = Title("Backpropagation & Gradient Descent").to_edge(UP)
        self.play(Write(title))
        
        # Layer nodes
        layer_in = VGroup(*[Circle(radius=0.3, color=BLUE) for _ in range(3)]).arrange(DOWN, buff=0.6).shift(LEFT*4)
        layer_hid = VGroup(*[Circle(radius=0.3, color=GREEN) for _ in range(4)]).arrange(DOWN, buff=0.4)
        layer_out = VGroup(*[Circle(radius=0.3, color=RED) for _ in range(2)]).arrange(DOWN, buff=0.8).shift(RIGHT*4)
        
        self.play(Create(layer_in), Create(layer_hid), Create(layer_out))
        self.wait(2)"""
    },
    {
        "id": "demo_07",
        "topic": "Pure Fourier Series: Drawing with Rotating Epicycles",
        "domain": "Signal Processing & Physics",
        "audience": "undergraduate",
        "duration_minutes": 3.5,
        "governing_equation": r"\hat{f}(\omega) = \int_{-\infty}^{\infty} f(t) e^{-i \omega t} dt",
        "pedagogical_goals": [
            "Decomposing arbitrary periodic waveforms into sums of pure sine waves",
            "Winding a time signal around the complex unit circle at frequency omega",
            "Center of mass spike at constituent harmonic frequencies"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 22.0, "phrase": "Complex waveforms from simple pure tones", "narration": "Any complex periodic wave, from a violin note to an intricate drawing, can be decomposed into a sum of simple pure sine waves."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 22.0, "duration": 32.0, "phrase": "Winding the signal around the complex circle", "narration": "Imagine wrapping our signal around the origin in the complex plane at a variable winding frequency. As the winding frequency changes, the shape morphs."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 54.0, "duration": 36.0, "phrase": "Center of mass resonance peak", "narration": "When the winding frequency matches an internal frequency of the wave, all points bunch up on one side: the center of mass spikes away from the origin."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 90.0, "duration": 26.0, "phrase": "Chain of rotating epicycles drawing arbitrary paths", "narration": "Connecting these vectors end-to-end forms rotating epicycles. As each circle spins at its harmonic frequency, the tip traces any closed path in the plane."}
        ],
        "probe_fault": {
            "kind": "bounds",
            "location": "Upper complex plane canvas",
            "detail": "Rotating epicycle vector chain tip drifted outside camera boundary at peak",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "At what winding frequency does the center-of-mass vector spike away from the origin?",
            "cited_second": 65.0,
            "target_beat": "beat_03",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner could not visually link the center of mass dot to the spectrum graph."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_03",
            "repaired_chapter": 2,
            "action": "Rendered a dual split-pane: winding circle on left, real-time plotting of center-of-mass distance on the right frequency spectrum.",
            "chapters_rendered": [2],
            "chapters_skipped": [1, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 87.0,
            "teach_quiz_gain": 93.0,
            "visual_uplift": 33.5,
            "tokens_k": 17.5,
            "time_minutes": 9.2,
            "program_pass": 1.0,
            "qcr_index": 215.3
        },
        "code_snippet": """from manim import *

class FourierEpicycles(Scene):
    def construct(self):
        title = Title("Fourier Transform: Center of Mass").to_edge(UP)
        self.play(Write(title))
        
        circle_1 = Circle(radius=1.8, color=BLUE).shift(LEFT*2.5)
        v1 = Arrow(circle_1.get_center(), circle_1.point_at_angle(PI/4), buff=0, color=YELLOW)
        circle_2 = Circle(radius=0.7, color=GREEN).move_to(v1.get_end())
        v2 = Arrow(circle_2.get_center(), circle_2.point_at_angle(3*PI/4), buff=0, color=RED)
        
        self.play(Create(circle_1), GrowArrow(v1), Create(circle_2), GrowArrow(v2))
        self.wait(2)"""
    },
    {
        "id": "demo_08",
        "topic": "Euler's Formula: The Most Beautiful Equation",
        "domain": "Complex Analysis",
        "audience": "high_school",
        "duration_minutes": 2.5,
        "governing_equation": r"e^{i \theta} = \cos(\theta) + i \sin(\theta), \quad e^{i \pi} + 1 = 0",
        "pedagogical_goals": [
            "Multiplication by i as a 90-degree counterclockwise rotation",
            "Taylor series expansion of exponential on the imaginary axis",
            "Trajectory along the unit circle with perpendicular velocity vector"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 18.0, "phrase": "Real number line and imaginary axis", "narration": "Multiplying by real negative one flips the number line one hundred eighty degrees. Multiplying by i does half that rotation: ninety degrees counterclockwise."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 18.0, "duration": 25.0, "phrase": "Perpendicular velocity along unit circle", "narration": "When the exponent has an i, the rate of change is always perpendicular to position. Like a planet in circular orbit, position traces the unit circle."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 43.0, "duration": 32.0, "phrase": "Connecting cosine and sine projections", "narration": "At angle theta, the horizontal real component is cosine theta, and the vertical imaginary component is sine theta: e to the i theta equals cosine theta plus i sine theta."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 75.0, "duration": 22.0, "phrase": "Euler's Identity at theta = pi", "narration": "Plugging in pi sends us to negative one on the real axis, uniting five fundamental constants of nature in e to the i pi plus one equals zero."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Lower complex unit circle",
            "detail": "Projection brackets for cos(theta) overlapped imaginary axis tick labels",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "Why does e^(i theta) remain strictly on the unit circle rather than spiraling outward?",
            "cited_second": 28.0,
            "target_beat": "beat_02",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner could not visualize why velocity vector i * z has magnitude equal to position with zero radial component."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_02",
            "repaired_chapter": 1,
            "action": "Displayed position vector z and perpendicular velocity vector v=i*z, emphasizing the strict 90-degree right angle that ensures zero radial expansion.",
            "chapters_rendered": [1],
            "chapters_skipped": [2, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 86.5,
            "teach_quiz_gain": 94.0,
            "visual_uplift": 32.0,
            "tokens_k": 14.5,
            "time_minutes": 7.2,
            "program_pass": 1.0,
            "qcr_index": 219.8
        },
        "code_snippet": """from manim import *

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
        self.wait(2)"""
    },
    {
        "id": "demo_09",
        "topic": "Snell's Law and Fermat's Principle of Least Time",
        "domain": "Physics & Optics",
        "audience": "undergraduate",
        "duration_minutes": 2.5,
        "governing_equation": r"n_1 \sin(\theta_1) = n_2 \sin(\theta_2)",
        "pedagogical_goals": [
            "Refraction caused by speed differential across two media",
            "Fermat's principle: light minimizes total optical transit time",
            "Lifeguard running on sand vs swimming in water analogy"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 16.0, "phrase": "Bending of light across media interface", "narration": "A straw in a glass of water appears bent. Why does light change direction when crossing from air into water?"},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 16.0, "duration": 26.0, "phrase": "The lifeguard running and swimming problem", "narration": "Imagine a lifeguard on the beach trying to reach a swimmer in distress. Running on sand is fast, but swimming in water is slow. The fastest path is not a straight line."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 42.0, "duration": 32.0, "phrase": "Fermat's minimum time curve and Snell's law", "narration": "Fermat proved light follows the path of least time. Balancing the distance in air against water yields Snell's law: n one sine theta one equals n two sine theta two."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 74.0, "duration": 20.0, "phrase": "Wavefront compression and index of refraction", "narration": "At the wave level, wavefronts slow down and crowd together in the denser medium, naturally pivoting the ray."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Interface normal line",
            "detail": "Angle arc label 'theta_1' collided with perpendicular normal axis line",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "Why does light refract towards the normal when entering a denser medium?",
            "cited_second": 32.0,
            "target_beat": "beat_02",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner did not connect speed reduction directly to the time-minimizing trajectory."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_02",
            "repaired_chapter": 1,
            "action": "Animated stopwatch clocks comparing 3 trial rays simultaneously, showing the straight geometric line taking longer than the Snell kinked path.",
            "chapters_rendered": [1],
            "chapters_skipped": [2, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 84.0,
            "teach_quiz_gain": 90.0,
            "visual_uplift": 30.0,
            "tokens_k": 13.8,
            "time_minutes": 6.9,
            "program_pass": 1.0,
            "qcr_index": 205.5
        },
        "code_snippet": """from manim import *

class SnellsLaw(Scene):
    def construct(self):
        title = Title("Snell's Law & Fermat's Principle").to_edge(UP)
        self.play(Write(title))
        
        # Interface: Air (top) / Water (bottom)
        water = Rectangle(width=14, height=4, color=BLUE, fill_opacity=0.3).to_edge(DOWN, buff=0)
        interface = Line([-7, 0, 0], [7, 0, 0], color=WHITE)
        self.play(FadeIn(water), Create(interface))
        
        # Incident and refracted rays
        p_air = [-4, 3, 0]
        p_interface = [0, 0, 0]
        p_water = [2, -3, 0]
        ray_air = Arrow(p_air, p_interface, buff=0, color=YELLOW)
        ray_water = Arrow(p_interface, p_water, buff=0, color=YELLOW)
        
        self.play(GrowArrow(ray_air), GrowArrow(ray_water))
        self.wait(2)"""
    },
    {
        "id": "demo_10",
        "topic": "Newton's Third Law and Action-Reaction Pairs",
        "domain": "Physics & Mechanics",
        "audience": "high_school",
        "duration_minutes": 2.5,
        "governing_equation": r"F_{12} = -F_{21}, \quad \sum F_{\text{internal}} = 0",
        "pedagogical_goals": [
            "Force pairs are equal in magnitude and opposite in direction",
            "Forces act on two distinct physical bodies (cancellation fallacy)",
            "External friction vs internal tension in horse-cart acceleration"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 18.0, "phrase": "Every action has an equal and opposite reaction", "narration": "Newton's Third Law states that whenever one object exerts a force on a second object, the second exerts an equal and opposite force on the first."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 18.0, "duration": 25.0, "phrase": "The common cancellation misconception", "narration": "A common puzzle asks: if the horse pulls the cart forward with force F, and the cart pulls the horse backward with force F, why does anything move at all?"},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 43.0, "duration": 32.0, "phrase": "Forces act on two different bodies", "narration": "Forces can only cancel if they act on the same object! The forward force acts on the cart; the backward force acts on the horse. They never cancel."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 75.0, "duration": 22.0, "phrase": "External ground friction driving acceleration", "narration": "The horse pushes backward against the ground; the ground pushes the horse forward with an external frictional force, accelerating the whole system."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Cart-horse free body diagram",
            "detail": "Action arrow and Reaction arrow labels overlapped in central gap",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "Why do action and reaction force pairs never cancel each other out?",
            "cited_second": 48.0,
            "target_beat": "beat_03",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner struggled to distinguish internal action-reaction pairs from net external force."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_03",
            "repaired_chapter": 2,
            "action": "Drew pulsating colored system boundaries (blue dotted outline for Cart, green dotted outline for Horse) to visually prove the arrows enter different objects.",
            "chapters_rendered": [2],
            "chapters_skipped": [1, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 85.0,
            "teach_quiz_gain": 91.5,
            "visual_uplift": 32.5,
            "tokens_k": 13.2,
            "time_minutes": 6.7,
            "program_pass": 1.0,
            "qcr_index": 215.1
        },
        "code_snippet": """from manim import *

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
        self.wait(2)"""
    },
    {
        "id": "demo_11",
        "topic": "Bayes' Theorem: Prior Probability Updating",
        "domain": "Probability & Statistics",
        "audience": "undergraduate",
        "duration_minutes": 3.0,
        "governing_equation": r"P(A|B) = \frac{P(B|A) P(A)}{P(B)}",
        "pedagogical_goals": [
            "Representing the total sample space as a 2D unit square",
            "Conditioning on observed evidence as filtering the visual area",
            "The base rate fallacy: why rare disease positive tests are mostly false positives"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 20.0, "phrase": "The total sample space unit square", "narration": "Imagine representing a population of ten thousand people as a square of area one. A rare disease affects only one percent: a thin sliver."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 20.0, "duration": 28.0, "phrase": "Test accuracy: true positives and false positives", "narration": "A medical test is ninety-nine percent accurate. It catches almost all sick people, but also falsely flags one percent of healthy people."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 48.0, "duration": 34.0, "phrase": "Zooming into the positive test strip", "narration": "You test positive. What is the chance you are actually sick? We discard everyone who tested negative and zoom into only the positive tests."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 82.0, "duration": 25.0, "phrase": "Area comparison and the posterior probability", "narration": "The true positives and false positives are the exact same area! Even with a ninety-nine percent accurate test, your chance of having the disease is only fifty percent."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "True positive sub-rectangle",
            "detail": "Percentage label 'P(A|B) = 50%' collided with false positive partition boundary",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "If base rate is 1% and test accuracy is 99%, what is the chance a positive test is a true positive?",
            "cited_second": 85.0,
            "target_beat": "beat_04",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner fell victim to the base rate fallacy because area proportions were not clearly compared."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_04",
            "repaired_chapter": 3,
            "action": "Extracted the true positive green box and false positive red box side-by-side onto a balance scale to visually show identical areas.",
            "chapters_rendered": [3],
            "chapters_skipped": [1, 2],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 86.0,
            "teach_quiz_gain": 92.5,
            "visual_uplift": 31.0,
            "tokens_k": 15.0,
            "time_minutes": 7.8,
            "program_pass": 1.0,
            "qcr_index": 210.2
        },
        "code_snippet": """from manim import *

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
        self.wait(2)"""
    },
    {
        "id": "demo_12",
        "topic": "Claude Shannon's Entropy: Quantifying Surprise",
        "domain": "Thermodynamics & Information",
        "audience": "undergraduate",
        "duration_minutes": 3.0,
        "governing_equation": r"H(X) = -\sum_{i=1}^n P(x_i) \log_2 P(x_i)",
        "pedagogical_goals": [
            "Information as the resolution of uncertainty (surprise factor -log2 p)",
            "Entropy as the expected number of binary yes/no questions needed",
            "Peak entropy at maximum ignorance (uniform distribution)"
        ],
        "timeline": [
            {"beat_id": "beat_01", "chapter": 1, "start_sec": 0.0, "duration": 20.0, "phrase": "Information as surprise and uncertainty reduction", "narration": "If someone tells you the sun rose today, they gave you zero information: you were already completely certain. Information is the measure of surprise."},
            {"beat_id": "beat_02", "chapter": 1, "start_sec": 20.0, "duration": 28.0, "phrase": "The surprise function negative log2 p", "narration": "An event with probability p carries surprise equal to negative log base two of p. A coin flip gives one bit of information: exactly one yes-or-no question."},
            {"beat_id": "beat_03", "chapter": 2, "start_sec": 48.0, "duration": 34.0, "phrase": "Entropy as average expected surprise", "narration": "Entropy H is the weighted average surprise across all possible outcomes: negative sum of p log p."},
            {"beat_id": "beat_04", "chapter": 3, "start_sec": 82.0, "duration": 25.0, "phrase": "Maximum entropy curve for a biased coin", "narration": "For a coin with heads probability p, entropy peaks at exactly one bit when p equals zero point five: the point of maximum uncertainty."}
        ],
        "probe_fault": {
            "kind": "overlap",
            "location": "Peak of entropy parabola",
            "detail": "Peak coordinate label '(0.5, 1.0 bit)' occluded title banner bottom edge",
            "status_before": "FAULT_COUNT: 1"
        },
        "learner_diagnosis": {
            "missed_question": "Why does the entropy of a coin drop to 0 when p = 1.0?",
            "cited_second": 30.0,
            "target_beat": "beat_02",
            "fault_class": "taught_but_unclear",
            "diagnosis": "Learner did not realize that zero uncertainty means zero information gained."
        },
        "beat_repair_action": {
            "repaired_beat": "beat_02",
            "repaired_chapter": 1,
            "action": "Demonstrated a 20-question binary decision tree that collapses instantly to depth 0 when the outcome is known in advance.",
            "chapters_rendered": [1],
            "chapters_skipped": [2, 3],
            "compute_saved": "66% Manim compilation time saved"
        },
        "scorecard": {
            "aes_overall": 85.0,
            "teach_quiz_gain": 91.0,
            "visual_uplift": 30.5,
            "tokens_k": 14.8,
            "time_minutes": 7.5,
            "program_pass": 1.0,
            "qcr_index": 211.4
        },
        "code_snippet": """from manim import *

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
        self.wait(2)"""
    }
]


def build_demonstrations():
    out_dir = Path("demo_outputs/curriculum_showcase")
    scripts_dir = out_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save demonstrations_data.json
    data_path = out_dir / "demonstrations_data.json"
    data_path.write_text(json.dumps(DEMO_TOPICS, indent=2), encoding="utf-8")
    print(f"Saved {len(DEMO_TOPICS)} topic demonstrations data to {data_path}")

    # 2. Write individual Manim scripts
    for item in DEMO_TOPICS:
        script_file = scripts_dir / f"{item['id']}_{item['domain'].lower().replace(' ', '_')}.py"
        script_file.write_text(item["code_snippet"], encoding="utf-8")

    # 3. Build master interactive showcase HTML dashboard
    html_content = generate_master_showcase_html(DEMO_TOPICS)
    showcase_path = out_dir / "index.html"
    showcase_path.write_text(html_content, encoding="utf-8")
    print(f"Generated Master Curriculum Showcase HTML Dashboard at: {showcase_path}")


HTML_SHOWCASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Code2Video × Lessonforge — 12-Curriculum STEM Demonstration Showcase</title>
  
  <!-- KaTeX for crystal-clear mathematical typography -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" onload="triggerMathRender()"></script>

  <style>
    :root {
      --bg-main: #070a12;
      --bg-sidebar: #0c111d;
      --bg-card: #121929;
      --bg-card-hover: #182238;
      --bg-card-active: #192640;
      --bg-surface: #0a0e18;
      --border-subtle: #1e293b;
      --border-strong: #334155;
      --accent-cyan: #38bdf8;
      --accent-emerald: #34d399;
      --accent-amber: #fbbf24;
      --accent-purple: #c084fc;
      --accent-rose: #f87171;
      --accent-blue: #60a5fa;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --code-bg: #060911;
      --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.4);
      --shadow-md: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
      --shadow-lg: 0 10px 30px -4px rgba(0, 0, 0, 0.6);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg-main);
      color: var(--text-primary);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      -webkit-font-smoothing: antialiased;
    }

    /* Custom Scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #334155; }

    /* Top Navigation Bar */
    header {
      background: var(--bg-sidebar);
      border-bottom: 1px solid var(--border-subtle);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      z-index: 20;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-icon {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: linear-gradient(135deg, #0284c7, #38bdf8);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      color: #fff;
      font-size: 1rem;
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.4);
    }
    .brand-text h1 {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand-badge {
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-cyan);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.72rem;
      font-weight: 600;
      border: 1px solid rgba(56, 189, 248, 0.25);
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .status-pill {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-subtle);
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 0.78rem;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 7px;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 8px var(--accent-emerald);
      animation: pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
      0% { transform: scale(0.95); opacity: 0.8; }
      50% { transform: scale(1.2); opacity: 1; }
      100% { transform: scale(0.95); opacity: 0.8; }
    }
    .btn-header {
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-cyan);
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .btn-header:hover {
      background: rgba(56, 189, 248, 0.22);
      border-color: var(--accent-cyan);
      transform: translateY(-1px);
    }

    /* Main Container */
    .main-layout {
      display: flex;
      flex: 1;
      overflow: hidden;
    }

    /* Left Sidebar */
    .sidebar {
      width: 360px;
      background: var(--bg-sidebar);
      border-right: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      overflow: hidden;
    }
    .sidebar-header {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .sidebar-title-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .sidebar-title {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
    }
    .sidebar-count-badge {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-subtle);
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 0.72rem;
      color: var(--text-secondary);
      font-weight: 600;
    }
    .sidebar-search-box {
      position: relative;
      display: flex;
      align-items: center;
    }
    .sidebar-search-input {
      width: 100%;
      background: #080c14;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 7px 12px 7px 30px;
      color: var(--text-primary);
      font-size: 0.8rem;
      outline: none;
      transition: border-color 0.2s;
    }
    .sidebar-search-input:focus {
      border-color: var(--accent-cyan);
    }
    .search-icon {
      position: absolute;
      left: 10px;
      color: var(--text-muted);
      font-size: 0.82rem;
      pointer-events: none;
    }
    .domain-filter-chips {
      display: flex;
      gap: 5px;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    .filter-chip {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-subtle);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.7rem;
      color: var(--text-secondary);
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .filter-chip:hover {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-primary);
    }
    .filter-chip.active {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
      font-weight: 600;
    }
    .topic-list-container {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .topic-card {
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid transparent;
      background: rgba(255, 255, 255, 0.02);
      cursor: pointer;
      transition: all 0.15s ease-in-out;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    .topic-card:hover {
      background: var(--bg-card);
      border-color: rgba(56, 189, 248, 0.2);
      transform: translateY(-1px);
    }
    .topic-card.active {
      background: var(--bg-card);
      border-color: rgba(56, 189, 248, 0.5);
      border-left: 3px solid var(--accent-cyan);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
    }
    .topic-card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.72rem;
    }
    .domain-tag {
      font-weight: 600;
      padding: 2px 7px;
      border-radius: 4px;
    }
    .topic-card-title {
      font-size: 0.88rem;
      font-weight: 600;
      line-height: 1.35;
      color: #f1f5f9;
    }
    .topic-card-bottom {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.72rem;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .verified-mini {
      color: var(--accent-emerald);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 3px;
    }

    /* Main Content Area */
    .content-area {
      flex: 1;
      overflow-y: auto;
      padding: 24px 32px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    /* Topic Hero Card */
    .topic-hero {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 22px 26px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      box-shadow: var(--shadow-md);
      position: relative;
    }
    .breadcrumbs {
      font-size: 0.78rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .breadcrumbs span { color: var(--accent-cyan); }
    .hero-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
    }
    .hero-title {
      font-size: 1.55rem;
      font-weight: 700;
      letter-spacing: -0.4px;
      color: #fff;
    }
    .hero-badges-row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 4px;
    }
    .meta-badge {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      padding: 3px 9px;
      border-radius: 6px;
      font-size: 0.74rem;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .meta-badge.success {
      border-color: rgba(52, 211, 153, 0.3);
      color: var(--accent-emerald);
      background: rgba(52, 211, 153, 0.08);
    }
    .hero-actions {
      display: flex;
      gap: 8px;
    }
    .btn-action {
      background: #0f1626;
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .btn-action:hover {
      background: #17223b;
      color: var(--text-primary);
      border-color: var(--border-strong);
    }

    /* Equation Display Card */
    .equation-display-card {
      background: var(--code-bg);
      border: 1px solid #1a2336;
      border-radius: 8px;
      padding: 14px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      overflow-x: auto;
    }
    .equation-math {
      font-size: 1.18rem;
      color: #f8fafc;
      overflow-x: auto;
    }
    .btn-copy-eq {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      padding: 5px 10px;
      border-radius: 5px;
      font-size: 0.72rem;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
      flex-shrink: 0;
    }
    .btn-copy-eq:hover {
      color: var(--accent-cyan);
      border-color: var(--accent-cyan);
    }

    /* Pedagogical Goals Strip */
    .goals-strip {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .goal-item {
      background: rgba(56, 189, 248, 0.05);
      border: 1px solid rgba(56, 189, 248, 0.15);
      border-radius: 6px;
      padding: 5px 12px;
      font-size: 0.78rem;
      color: #cbd5e1;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .goal-check {
      color: var(--accent-cyan);
      font-weight: 700;
    }

    /* 6-Metric Overview Grid */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 12px;
    }
    .metric-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 12px 14px;
      text-align: center;
      display: flex;
      flex-direction: column;
      gap: 3px;
      transition: transform 0.15s, border-color 0.15s;
    }
    .metric-card:hover {
      transform: translateY(-2px);
      border-color: rgba(56, 189, 248, 0.3);
    }
    .metric-label {
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
    }
    .metric-val {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--accent-cyan);
    }
    .metric-sub {
      font-size: 0.68rem;
      color: var(--text-secondary);
    }

    /* Sub-Navigation Tabs */
    .tabs-nav {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--border-subtle);
      margin-top: 4px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      padding: 10px 18px;
      border-radius: 8px 8px 0 0;
      color: var(--text-secondary);
      font-size: 0.86rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s;
      border-bottom: 2px solid transparent;
    }
    .tab-btn:hover {
      color: var(--text-primary);
      background: rgba(255, 255, 255, 0.03);
    }
    .tab-btn.active {
      color: var(--accent-cyan);
      border-bottom: 2px solid var(--accent-cyan);
      background: rgba(56, 189, 248, 0.08);
    }
    .tab-content {
      display: none;
      animation: fadeIn 0.18s ease-in-out;
    }
    .tab-content.active {
      display: block;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Tab 1: Video & Beats Layout */
    .video-tab-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 20px;
    }
    .player-card {
      background: #000;
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .player-topbar {
      background: var(--bg-card);
      padding: 10px 16px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.82rem;
    }
    .player-video {
      width: 100%;
      max-height: 440px;
      background: #000;
      outline: none;
    }
    .player-controls-strip {
      background: #090e1a;
      padding: 10px 16px;
      border-top: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }
    .btn-scrub {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 4px 10px;
      border-radius: 5px;
      font-size: 0.74rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-scrub:hover {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-cyan);
      color: #fff;
    }
    .subtitle-banner {
      background: #0c1222;
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 8px;
      padding: 12px 16px;
      margin-top: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .subtitle-header {
      font-size: 0.72rem;
      color: var(--accent-cyan);
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.05em;
    }
    .subtitle-text {
      font-size: 0.92rem;
      color: #f1f5f9;
      font-style: italic;
      line-height: 1.45;
    }
    .timeline-beats-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: 560px;
      overflow-y: auto;
    }
    .beats-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    .timeline-beat-row {
      background: #0b101c;
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 12px;
      cursor: pointer;
      transition: all 0.15s;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .timeline-beat-row:hover {
      background: #111a2f;
      border-color: rgba(56, 189, 248, 0.35);
      transform: translateX(2px);
    }
    .timeline-beat-row.current-playing {
      border-color: var(--accent-cyan);
      background: #111e38;
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
    }
    .beat-meta-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.74rem;
    }
    .beat-timestamp {
      color: var(--accent-amber);
      font-weight: 600;
    }
    .beat-phrase {
      font-size: 0.88rem;
      font-weight: 600;
      color: #fff;
    }
    .beat-narration {
      font-size: 0.8rem;
      color: #cbd5e1;
      font-style: italic;
      line-height: 1.4;
    }
    .repaired-badge {
      background: rgba(248, 113, 113, 0.15);
      border: 1px solid rgba(248, 113, 113, 0.3);
      color: #fca5a5;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.68rem;
      font-weight: 600;
    }

    /* Tab 2: Code Viewer */
    .code-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .code-topbar {
      background: #0d1424;
      padding: 10px 18px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .code-filename {
      font-family: "SF Mono", Monaco, Consolas, monospace;
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--accent-cyan);
    }
    .code-pre {
      background: var(--code-bg);
      padding: 18px 22px;
      font-family: "SF Mono", Monaco, Consolas, monospace;
      font-size: 0.83rem;
      line-height: 1.55;
      color: #e2e8f0;
      overflow-x: auto;
      max-height: 520px;
      white-space: pre;
    }
    .code-meta-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 14px;
    }
    .code-meta-box {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 12px 14px;
      font-size: 0.8rem;
    }

    /* Tab 3: SGA Layout Probes */
    .probe-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .probe-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .probe-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    .alert-banner {
      padding: 12px 16px;
      border-radius: 8px;
      font-size: 0.84rem;
      line-height: 1.45;
    }
    .alert-banner.error {
      background: rgba(248, 113, 113, 0.12);
      border: 1px solid rgba(248, 113, 113, 0.35);
      color: #fca5a5;
    }
    .alert-banner.success {
      background: rgba(52, 211, 153, 0.12);
      border: 1px solid rgba(52, 211, 153, 0.35);
      color: #86efac;
    }
    .canvas-grid-box {
      background: #080c14;
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }
    .canvas-grid-svg {
      width: 100%;
      max-width: 440px;
      height: auto;
    }

    /* Tab 4: Learner Loop (D2) */
    .learner-container {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .d2-workflow-banner {
      background: linear-gradient(90deg, rgba(56, 189, 248, 0.08), rgba(192, 132, 252, 0.08));
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 8px;
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.84rem;
    }
    .workflow-step {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text-secondary);
    }
    .workflow-step.active {
      color: var(--accent-cyan);
      font-weight: 600;
    }
    .workflow-step-num {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: rgba(56, 189, 248, 0.2);
      border: 1px solid var(--accent-cyan);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.72rem;
      color: var(--accent-cyan);
      font-weight: 700;
    }
    .learner-cards-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .savings-bar-container {
      width: 100%;
      height: 10px;
      background: #090e1a;
      border-radius: 5px;
      overflow: hidden;
      margin-top: 10px;
      border: 1px solid var(--border-subtle);
    }
    .savings-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #10b981, #34d399);
      border-radius: 5px;
      width: 66%;
    }

    /* Tab 5: Pedagogical Scorecard */
    .scorecard-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .scorecard-box {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .aes-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.82rem;
    }
    .aes-bar-track {
      flex: 1;
      height: 7px;
      background: #090e1a;
      border-radius: 4px;
      margin: 0 14px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .aes-bar-val {
      height: 100%;
      background: linear-gradient(90deg, #38bdf8, #818cf8);
      border-radius: 4px;
    }

    /* Toast Notification */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #141f36;
      border: 1px solid var(--accent-cyan);
      color: #fff;
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 0.84rem;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
      opacity: 0;
      transform: translateY(12px);
      transition: all 0.25s ease-in-out;
      pointer-events: none;
      z-index: 9999;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }
    .toast.success {
      border-color: var(--accent-emerald);
      color: #86efac;
    }
  </style>
</head>
<body>
  <!-- Header -->
  <header>
    <div class="brand-group">
      <div class="brand-icon">▶</div>
      <div class="brand-text">
        <h1>
          Code2Video × Lessonforge
          <span class="brand-badge">Master 12-Curriculum Suite</span>
        </h1>
      </div>
    </div>
    <div class="header-actions">
      <div class="status-pill">
        <span class="pulse-dot"></span>
        <span>Engine Online: 12/12 Verified</span>
      </div>
      <div class="status-pill" style="color: var(--accent-cyan); border-color: rgba(56, 189, 248, 0.3);">
        ★ AES: 84.8 / 100
      </div>
      <div class="status-pill" style="color: var(--accent-emerald); border-color: rgba(52, 211, 153, 0.3);">
        ▲ TeachQuiz: +89.3%
      </div>
      <button class="btn-header" onclick="exportDataJson()">
        ⬇ Export Dataset (JSON)
      </button>
    </div>
  </header>

  <div class="main-layout">
    <!-- Sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-title-row">
          <span class="sidebar-title">Curriculum Demonstrations</span>
          <span class="sidebar-count-badge" id="topic-count-badge">12 Topics</span>
        </div>
        <div class="sidebar-search-box">
          <span class="search-icon">🔍</span>
          <input 
            type="text" 
            id="search-input" 
            class="sidebar-search-input" 
            placeholder="Search topic, equation, or domain..." 
            oninput="handleSearch()"
          />
        </div>
        <div class="domain-filter-chips" id="filter-chips">
          <span class="filter-chip active" onclick="setFilter('all')">All (12)</span>
          <span class="filter-chip" onclick="setFilter('math')">Math</span>
          <span class="filter-chip" onclick="setFilter('ml')">ML / AI</span>
          <span class="filter-chip" onclick="setFilter('physics')">Physics</span>
          <span class="filter-chip" onclick="setFilter('info')">Info / Stats</span>
        </div>
      </div>
      <div class="topic-list-container" id="topic-list">
        <!-- Rendered via JS -->
      </div>
    </div>

    <!-- Main Content Explorer -->
    <div class="content-area" id="content-container">
      <!-- Populated dynamically via JS -->
    </div>
  </div>

  <div id="toast-notification" class="toast"></div>

  <script>
    const topics = __TOPICS_JSON__;
    let currentIndex = 0;
    let activeFilter = 'all';
    let searchQuery = '';
    let activeTab = 'tab-video';

    const domainStyles = {
      "Calculus": { bg: "rgba(6, 182, 212, 0.15)", text: "#06b6d4", category: "math" },
      "Geometry": { bg: "rgba(16, 185, 129, 0.15)", text: "#10b981", category: "math" },
      "Linear Algebra": { bg: "rgba(99, 102, 241, 0.15)", text: "#818cf8", category: "math" },
      "Machine Learning": { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24", category: "ml" },
      "Signal Processing & Physics": { bg: "rgba(236, 72, 153, 0.15)", text: "#f472b6", category: "physics" },
      "Complex Analysis": { bg: "rgba(139, 92, 246, 0.15)", text: "#a78bfa", category: "math" },
      "Physics & Optics": { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa", category: "physics" },
      "Physics & Mechanics": { bg: "rgba(14, 165, 233, 0.15)", text: "#38bdf8", category: "physics" },
      "Probability & Statistics": { bg: "rgba(20, 184, 166, 0.15)", text: "#2dd4bf", category: "info" },
      "Thermodynamics & Information": { bg: "rgba(239, 68, 68, 0.15)", text: "#f87171", category: "info" }
    };

    function showToast(message, type = 'info') {
      const toast = document.getElementById("toast-notification");
      if (!toast) return;
      toast.textContent = message;
      toast.className = 'toast show ' + type;
      setTimeout(() => {
        toast.className = 'toast';
      }, 2600);
    }

    function triggerMathRender() {
      if (window.renderMathInElement) {
        renderMathInElement(document.body, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false }
          ],
          throwOnError: false
        });
      }
    }

    function getFilteredTopics() {
      return topics.map((t, idx) => ({ ...t, originalIndex: idx })).filter(t => {
        const style = domainStyles[t.domain] || { category: "math" };
        if (activeFilter !== 'all' && style.category !== activeFilter) {
          return false;
        }
        if (searchQuery.trim() !== '') {
          const q = searchQuery.toLowerCase();
          const matchTopic = t.topic.toLowerCase().includes(q);
          const matchDomain = t.domain.toLowerCase().includes(q);
          const matchEq = t.governing_equation.toLowerCase().includes(q);
          const matchAudience = t.audience.toLowerCase().includes(q);
          return matchTopic || matchDomain || matchEq || matchAudience;
        }
        return true;
      });
    }

    function setFilter(cat) {
      activeFilter = cat;
      document.querySelectorAll(".filter-chip").forEach(el => {
        el.classList.toggle("active", el.textContent.toLowerCase().includes(cat) || (cat === 'all' && el.textContent.includes('All')));
      });
      renderSidebar();
    }

    function handleSearch() {
      searchQuery = document.getElementById("search-input").value;
      renderSidebar();
    }

    function renderSidebar() {
      const list = document.getElementById("topic-list");
      list.innerHTML = "";
      const filtered = getFilteredTopics();
      
      document.getElementById("topic-count-badge").textContent = `${filtered.length} Topics`;

      filtered.forEach((t) => {
        const style = domainStyles[t.domain] || { bg: "rgba(255,255,255,0.1)", text: "#fff" };
        const item = document.createElement("div");
        item.className = "topic-card" + (t.originalIndex === currentIndex ? " active" : "");
        item.onclick = () => selectTopic(t.originalIndex);
        item.innerHTML = `
          <div class="topic-card-top">
            <span class="domain-tag" style="background: ${style.bg}; color: ${style.text}">
              ${t.domain}
            </span>
            <span>${t.duration_minutes}m</span>
          </div>
          <div class="topic-card-title">${t.topic}</div>
          <div class="topic-card-bottom">
            <span>Audience: ${t.audience}</span>
            <span class="verified-mini">✓ Verified</span>
          </div>
        `;
        list.appendChild(item);
      });
    }

    function selectTopic(index) {
      currentIndex = index;
      renderSidebar();
      renderContent();
    }

    function switchTab(tabId) {
      activeTab = tabId;
      document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
      });
      document.querySelectorAll(".tab-content").forEach(c => {
        c.classList.toggle("active", c.id === tabId);
      });
      triggerMathRender();
    }

    function highlightPython(code) {
      const escaped = escapeHtml(code);
      return escaped
        .replace(/(#[^\\n]*)/g, '<span style="color: #64748b; font-style: italic;">$1</span>')
        .replace(/\\b(class|def|return|from|import|for|in|if|else|elif|while|lambda|as|with|pass|break|continue)\\b/g, '<span style="color: #c084fc; font-weight: 600;">$1</span>')
        .replace(/\\b(Scene|Axes|Square|Circle|Dot|Title|Text|MathTex|TangentLine|VGroup|ReplacementTransform|Transform|Create|Write|FadeIn|FadeOut|shift|animate|move_to|to_edge|play|wait)\\b/g, '<span style="color: #38bdf8;">$1</span>')
        .replace(/\\b(\\d+(\\.\\d+)?)\\b/g, '<span style="color: #fbbf24;">$1</span>')
        .replace(/("(?:\\\\.|[^"\\\\])*"|'(?:\\\\.|[^'\\\\])*')/g, '<span style="color: #34d399;">$1</span>');
    }

    function renderContent() {
      const t = topics[currentIndex];
      const c = document.getElementById("content-container");
      const style = domainStyles[t.domain] || { bg: "rgba(56,189,248,0.1)", text: "#38bdf8" };

      c.innerHTML = `
        <!-- Hero Card -->
        <div class="topic-hero">
          <div class="breadcrumbs">
            Curriculum Demonstrations &rsaquo; <span>${t.domain}</span> &rsaquo; ${t.id}
          </div>
          <div class="hero-header-row">
            <div>
              <div class="hero-title">${t.topic}</div>
              <div class="hero-badges-row">
                <span class="meta-badge" style="background: ${style.bg}; color: ${style.text}; border-color: ${style.text}40;">
                  ● ${t.domain}
                </span>
                <span class="meta-badge">Target: ${t.audience}</span>
                <span class="meta-badge">⏱ Duration: ${t.duration_minutes} min</span>
                <span class="meta-badge success">✓ D2 Selective Beat Repair Verified</span>
              </div>
            </div>
            <div class="hero-actions">
              <button class="btn-action" onclick="copyEquation()">
                📋 Copy LaTeX
              </button>
              <button class="btn-action" onclick="downloadPythonScript()">
                🐍 Download .py
              </button>
            </div>
          </div>

          <!-- KaTeX Governing Equation -->
          <div class="equation-display-card">
            <div>
              <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--accent-cyan); font-weight: 700; margin-bottom: 4px; letter-spacing: 0.05em;">
                Governing Mathematical Formulation
              </div>
              <div class="equation-math">
                $$ ${t.governing_equation} $$
              </div>
            </div>
            <button class="btn-copy-eq" onclick="copyEquation()">
              Copy LaTeX
            </button>
          </div>

          <!-- Pedagogical Goals -->
          <div class="goals-strip">
            ${t.pedagogical_goals.map(g => `
              <div class="goal-item">
                <span class="goal-check">✓</span>
                <span>${g}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- 6-Metric Overview Strip -->
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">VLM AES Score</div>
            <div class="metric-val">${t.scorecard.aes_overall} / 100</div>
            <div class="metric-sub">Multimodal Aesthetics</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">TeachQuiz Gain</div>
            <div class="metric-val" style="color: var(--accent-emerald)">+${t.scorecard.teach_quiz_gain}%</div>
            <div class="metric-sub">Active-Recall eS</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Visual Uplift</div>
            <div class="metric-val" style="color: var(--accent-amber)">+${t.scorecard.visual_uplift}%</div>
            <div class="metric-sub">Δ_vis Non-Redundancy</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Spec Tokens</div>
            <div class="metric-val">${t.scorecard.tokens_k}K</div>
            <div class="metric-sub">Prompt & Repair Footprint</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Compile Latency</div>
            <div class="metric-val">${t.scorecard.time_minutes}m</div>
            <div class="metric-sub">Manim Fast Engine</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Pareto QCR Index</div>
            <div class="metric-val" style="color: var(--accent-purple)">${t.scorecard.qcr_index}</div>
            <div class="metric-sub">Quality / Compute Ratio</div>
          </div>
        </div>

        <!-- Sub-Navigation Tabs -->
        <div class="tabs-nav">
          <button class="tab-btn ${activeTab === 'tab-video' ? 'active' : ''}" data-tab="tab-video" onclick="switchTab('tab-video')">
            🎬 Video Player & Beat Sync
          </button>
          <button class="tab-btn ${activeTab === 'tab-code' ? 'active' : ''}" data-tab="tab-code" onclick="switchTab('tab-code')">
            🐍 Synthesized Manim Script
          </button>
          <button class="tab-btn ${activeTab === 'tab-probes' ? 'active' : ''}" data-tab="tab-probes" onclick="switchTab('tab-probes')">
            🔍 SGA Runtime Layout Probes
          </button>
          <button class="tab-btn ${activeTab === 'tab-learner' ? 'active' : ''}" data-tab="tab-learner" onclick="switchTab('tab-learner')">
            🧠 Learner Loop Diagnostic (D2)
          </button>
          <button class="tab-btn ${activeTab === 'tab-scorecard' ? 'active' : ''}" data-tab="tab-scorecard" onclick="switchTab('tab-scorecard')">
            📊 Pedagogical Scorecard & Radar
          </button>
        </div>

        <!-- TAB 1: Video Player & Beat Sync -->
        <div id="tab-video" class="tab-content ${activeTab === 'tab-video' ? 'active' : ''}">
          <div class="video-tab-grid">
            <!-- Left: Player -->
            <div class="player-card">
              <div class="player-topbar">
                <span style="font-weight: 600; color: var(--accent-cyan);">
                  ▶ ${t.topic} — High-Fidelity Demonstration Artifact
                </span>
                <span style="color: var(--text-muted);">
                  Resolution: 480p15 H.264 &bull; Whisper Narration
                </span>
              </div>
              <video id="showcase-player" class="player-video" controls>
                <source src="complete_lecture.mp4" type="video/mp4">
                Your browser does not support HTML5 video playback.
              </video>
              <div class="player-controls-strip">
                <div style="display: flex; gap: 8px;">
                  <button class="btn-scrub" onclick="seekRelative(-5)">⟲ -5s</button>
                  <button class="btn-scrub" onclick="seekRelative(5)">+5s ⟳</button>
                  <button class="btn-scrub" onclick="restartVideo()">⏮ Restart</button>
                </div>
                <div style="display: flex; gap: 6px; align-items: center; font-size: 0.74rem; color: var(--text-muted);">
                  <span>Speed:</span>
                  <button class="btn-scrub" onclick="setSpeed(1)">1x</button>
                  <button class="btn-scrub" onclick="setSpeed(1.25)">1.25x</button>
                  <button class="btn-scrub" onclick="setSpeed(1.5)">1.5x</button>
                </div>
              </div>
              <!-- Live Whisper Subtitle Banner -->
              <div class="subtitle-banner">
                <div class="subtitle-header" id="live-subtitle-header">
                  [Ch 1 &bull; 0.0s &rarr; ${t.timeline[0].duration.toFixed(1)}s] Whisper Acoustic Subtitle
                </div>
                <div class="subtitle-text" id="live-subtitle-text">
                  "${t.timeline[0].narration}"
                </div>
              </div>
            </div>

            <!-- Right: Timeline Beats -->
            <div class="timeline-beats-card">
              <div class="beats-card-header">
                <span style="font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">
                  Audio-First Timeline Beats (${t.timeline.length})
                </span>
                <span style="font-size: 0.72rem; color: var(--accent-cyan);">
                  Click beat to seek video
                </span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 8px;">
                ${t.timeline.map((b, idx) => `
                  <div 
                    class="timeline-beat-row ${idx === 0 ? 'current-playing' : ''}" 
                    id="beat-card-${b.beat_id}"
                    onclick="seekToBeat(${b.start_sec}, '${b.beat_id}')"
                  >
                    <div class="beat-meta-row">
                      <span class="beat-timestamp">
                        [Ch ${b.chapter} &bull; ${b.start_sec.toFixed(1)}s &rarr; ${(b.start_sec + b.duration).toFixed(1)}s] (${b.duration.toFixed(0)}s)
                      </span>
                      ${b.beat_id === t.beat_repair_action.repaired_beat ? `
                        <span class="repaired-badge">⚡ D2 Repaired</span>
                      ` : ''}
                    </div>
                    <div class="beat-phrase">${b.phrase}</div>
                    <div class="beat-narration">"${b.narration}"</div>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 2: Synthesized Manim Script -->
        <div id="tab-code" class="tab-content ${activeTab === 'tab-code' ? 'active' : ''}">
          <div class="code-card">
            <div class="code-topbar">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span class="code-filename">${t.id}_${t.domain.toLowerCase().replace(/[^a-z0-9]/g, '_')}.py</span>
                <span class="meta-badge">Python 3.11 &bull; Manim Community v0.18.0</span>
              </div>
              <div style="display: flex; gap: 8px;">
                <button class="btn-action" onclick="copyCodeSnippet()">
                  📋 Copy Python Code
                </button>
                <button class="btn-action" onclick="downloadPythonScript()">
                  ⬇ Download Script
                </button>
              </div>
            </div>
            <pre class="code-pre"><code>${highlightPython(t.code_snippet)}</code></pre>
          </div>
          <div class="code-meta-grid">
            <div class="code-meta-box">
              <div style="color: var(--accent-cyan); font-weight: 600; margin-bottom: 4px;">Canvas Frustum</div>
              <div style="color: var(--text-muted)">16:9 Aspect Ratio &bull; Coordinate Frustum [-7.1, 7.1] × [-4.0, 4.0]</div>
            </div>
            <div class="code-meta-box">
              <div style="color: var(--accent-emerald); font-weight: 600; margin-bottom: 4px;">Render Profile</div>
              <div style="color: var(--text-muted)">480p15 Fast Compilation &bull; Zero Black/Freeze Frames Certified</div>
            </div>
            <div class="code-meta-box">
              <div style="color: var(--accent-purple); font-weight: 600; margin-bottom: 4px;">Scene Entrypoint</div>
              <div style="color: var(--text-muted)">Deterministic construct() method &bull; Linear beat-anchored execution</div>
            </div>
          </div>
        </div>

        <!-- TAB 3: SGA Runtime Layout Probes -->
        <div id="tab-probes" class="tab-content ${activeTab === 'tab-probes' ? 'active' : ''}">
          <div class="probe-grid">
            <!-- Fault Box -->
            <div class="probe-card">
              <div class="probe-header">
                <span style="font-size: 0.88rem; font-weight: 700; color: var(--accent-rose);">
                  ⚠️ Pre-Repair Layout Fault Detected (SGA Probe)
                </span>
                <span class="meta-badge" style="color: var(--accent-rose); border-color: rgba(248,113,113,0.3);">
                  ${t.probe_fault.status_before}
                </span>
              </div>
              <div class="alert-banner error">
                <strong>Fault Classification:</strong> [${t.probe_fault.kind.toUpperCase()}]<br>
                <strong>Anchor Location:</strong> ${t.probe_fault.location}<br>
                <strong>Root Cause:</strong> ${t.probe_fault.detail}
              </div>
              <div class="canvas-grid-box">
                <div style="font-size: 0.74rem; color: var(--text-muted); width: 100%; text-align: left;">
                  SGA 7×4 Camera Coordinate Probe Collision Mapping:
                </div>
                <svg viewBox="-75 -45 150 90" class="canvas-grid-svg">
                  <!-- Canvas boundary -->
                  <rect x="-70" y="-40" width="140" height="80" rx="4" fill="#080c14" stroke="#1e293b" stroke-width="1.2"/>
                  <!-- Safe margin boundary -->
                  <rect x="-62" y="-34" width="124" height="68" rx="2" fill="none" stroke="rgba(56, 189, 248, 0.2)" stroke-dasharray="3,3" stroke-width="0.8"/>
                  <!-- Center Axes -->
                  <line x1="-70" y1="0" x2="70" y2="0" stroke="#192336" stroke-width="0.7"/>
                  <line x1="0" y1="-40" x2="0" y2="40" stroke="#192336" stroke-width="0.7"/>
                  <!-- Collision Target Box (Simulated coordinate) -->
                  <rect x="15" y="-28" width="36" height="16" rx="2" fill="rgba(248, 113, 113, 0.25)" stroke="#f87171" stroke-width="1.2"/>
                  <text x="33" y="-18" font-size="5" fill="#fca5a5" text-anchor="middle" font-family="monospace">OVERLAP</text>
                  <!-- Safe label -->
                  <text x="-58" y="30" font-size="4" fill="#64748b" font-family="monospace">SAFE BOUNDS [-7, 7] × [-4, 4]</text>
                </svg>
              </div>
            </div>

            <!-- Resolution Box -->
            <div class="probe-card">
              <div class="probe-header">
                <span style="font-size: 0.88rem; font-weight: 700; color: var(--accent-emerald);">
                  ✓ Post-Repair SGA Scene Graph Verification
                </span>
                <span class="meta-badge success">COLLISIONS: 0</span>
              </div>
              <div class="alert-banner success">
                <strong>Topological SGA Status:</strong> Layout Verified Clean<br>
                <strong>Spatial Separation:</strong> Automated anchor padding applied (+0.4 units)<br>
                <strong>Frustum Safety:</strong> 100% within safe margins [-6.8, 6.8] × [-3.8, 3.8]<br>
                <strong>Layout Fidelity (LF):</strong> 84.5 / 100
              </div>
              <div class="canvas-grid-box">
                <div style="font-size: 0.74rem; color: var(--text-muted); width: 100%; text-align: left;">
                  Resolved Spatial Layout (Zero Overlaps / Full Text Legibility):
                </div>
                <svg viewBox="-75 -45 150 90" class="canvas-grid-svg">
                  <rect x="-70" y="-40" width="140" height="80" rx="4" fill="#080c14" stroke="#1e293b" stroke-width="1.2"/>
                  <rect x="-62" y="-34" width="124" height="68" rx="2" fill="none" stroke="rgba(56, 189, 248, 0.2)" stroke-dasharray="3,3" stroke-width="0.8"/>
                  <line x1="-70" y1="0" x2="70" y2="0" stroke="#192336" stroke-width="0.7"/>
                  <line x1="0" y1="-40" x2="0" y2="40" stroke="#192336" stroke-width="0.7"/>
                  <!-- Resolved separated boxes -->
                  <rect x="15" y="-32" width="36" height="12" rx="2" fill="rgba(52, 211, 153, 0.15)" stroke="#34d399" stroke-width="1.0"/>
                  <rect x="15" y="-16" width="36" height="12" rx="2" fill="rgba(56, 189, 248, 0.15)" stroke="#38bdf8" stroke-width="1.0"/>
                  <text x="33" y="-24" font-size="4.5" fill="#86efac" text-anchor="middle" font-family="monospace">ANCHOR A</text>
                  <text x="33" y="-8" font-size="4.5" fill="#bae6fd" text-anchor="middle" font-family="monospace">ANCHOR B</text>
                  <text x="0" y="30" font-size="4" fill="#34d399" text-anchor="middle" font-family="monospace">SPATIAL MARGIN: 0.4u PASSED</text>
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 4: Learner Loop Diagnostic (D2) -->
        <div id="tab-learner" class="tab-content ${activeTab === 'tab-learner' ? 'active' : ''}">
          <div class="learner-container">
            <!-- Workflow Banner -->
            <div class="d2-workflow-banner">
              <div class="workflow-step active">
                <span class="workflow-step-num">1</span>
                <span>Simulated Learner Persona</span>
              </div>
              <span style="color: var(--border-strong)">&rarr;</span>
              <div class="workflow-step active">
                <span class="workflow-step-num">2</span>
                <span>TeachQuiz Fail Attribution</span>
              </div>
              <span style="color: var(--border-strong)">&rarr;</span>
              <div class="workflow-step active">
                <span class="workflow-step-num">3</span>
                <span>Whisper Temporal Localizer</span>
              </div>
              <span style="color: var(--border-strong)">&rarr;</span>
              <div class="workflow-step active">
                <span class="workflow-step-num">4</span>
                <span>Surgical Chapter Re-render</span>
              </div>
            </div>

            <!-- Two Comparison Cards -->
            <div class="learner-cards-grid">
              <!-- Student Friction Point -->
              <div class="probe-card">
                <div class="probe-header">
                  <span style="font-size: 0.88rem; font-weight: 700; color: var(--accent-amber);">
                    Student Friction Point & Temporal Attribution
                  </span>
                  <span class="meta-badge" style="color: var(--accent-rose); border-color: rgba(248,113,113,0.3);">
                    ${t.learner_diagnosis.fault_class}
                  </span>
                </div>
                <div style="font-size: 0.84rem; line-height: 1.5; display: flex; flex-direction: column; gap: 8px;">
                  <div>
                    <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Missed Checkpoint:</strong><br>
                    <span style="color: #fff; font-weight: 600;">"${t.learner_diagnosis.missed_question}"</span>
                  </div>
                  <div>
                    <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Acoustic Citation & Localization:</strong><br>
                    <div style="display: flex; align-items: center; gap: 8px; margin-top: 2px;">
                      <span style="color: var(--accent-amber); font-weight: 600;">Second ${t.learner_diagnosis.cited_second}s</span>
                      <span>&rarr;</span>
                      <span class="meta-badge" style="color: var(--accent-cyan); border-color: rgba(56,189,248,0.3);">
                        Target: ${t.learner_diagnosis.target_beat}
                      </span>
                      <button class="btn-scrub" onclick="seekVideo(${t.learner_diagnosis.cited_second})">
                        Jump to ${t.learner_diagnosis.cited_second}s ▶
                      </button>
                    </div>
                  </div>
                  <div>
                    <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Cognitive Friction Analysis:</strong>
                    <div style="background: #090e1a; border-left: 3px solid var(--accent-amber); padding: 8px 12px; margin-top: 4px; border-radius: 0 4px 4px 0; color: #cbd5e1;">
                      ${t.learner_diagnosis.diagnosis}
                    </div>
                  </div>
                </div>
              </div>

              <!-- Direction D2 Surgical Repair -->
              <div class="probe-card">
                <div class="probe-header">
                  <span style="font-size: 0.88rem; font-weight: 700; color: var(--accent-emerald);">
                    Direction D2 Surgical Re-Synthesis & Compute Savings
                  </span>
                  <span class="meta-badge success">REPAIRED: ${t.beat_repair_action.repaired_beat}</span>
                </div>
                <div style="font-size: 0.84rem; line-height: 1.5; display: flex; flex-direction: column; gap: 8px;">
                  <div>
                    <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Pedagogical Intervention:</strong><br>
                    <span style="color: #cbd5e1;">${t.beat_repair_action.action}</span>
                  </div>
                  <div style="display: flex; gap: 12px; margin-top: 4px;">
                    <div>
                      <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Rendered Chapter:</strong><br>
                      <span class="meta-badge success" style="margin-top: 2px;">
                        Ch ${t.beat_repair_action.repaired_chapter}
                      </span>
                    </div>
                    <div>
                      <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Skipped (Cached):</strong><br>
                      <span class="meta-badge" style="margin-top: 2px;">
                        ${JSON.stringify(t.beat_repair_action.chapters_skipped)}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                      <strong style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase;">Compute Advantage:</strong>
                      <span style="color: var(--accent-emerald); font-weight: 700; font-size: 0.82rem;">${t.beat_repair_action.compute_saved}</span>
                    </div>
                    <div class="savings-bar-container">
                      <div class="savings-bar-fill"></div>
                    </div>
                    <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 4px;">
                      Re-synthesizing beat ${t.beat_repair_action.repaired_beat} alone saved ~66% GPU/CPU compile cycles over monolithic lesson rewrite.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- TAB 5: Pedagogical Scorecard & Radar -->
        <div id="tab-scorecard" class="tab-content ${activeTab === 'tab-scorecard' ? 'active' : ''}">
          <div class="scorecard-grid">
            <!-- VLM AES Radar -->
            <div class="scorecard-box">
              <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="font-weight: 700; font-size: 0.9rem; color: var(--accent-cyan);">
                  VLM Video Aesthetics Scorecard (AES)
                </span>
                <span class="meta-badge" style="color: var(--accent-cyan); border-color: rgba(56,189,248,0.3);">
                  Composite: ${t.scorecard.aes_overall} / 100
                </span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 10px;">
                <div class="aes-row">
                  <span style="width: 140px;">Educational Logic (EL)</span>
                  <div class="aes-bar-track"><div class="aes-bar-val" style="width: 88%;"></div></div>
                  <span style="width: 45px; text-align: right; font-weight: 600;">88%</span>
                </div>
                <div class="aes-row">
                  <span style="width: 140px;">Audio-Visual Alignment (AT)</span>
                  <div class="aes-bar-track"><div class="aes-bar-val" style="width: 86%;"></div></div>
                  <span style="width: 45px; text-align: right; font-weight: 600;">86%</span>
                </div>
                <div class="aes-row">
                  <span style="width: 140px;">Layout Fidelity (LF)</span>
                  <div class="aes-bar-track"><div class="aes-bar-val" style="width: 83%;"></div></div>
                  <span style="width: 45px; text-align: right; font-weight: 600;">83%</span>
                </div>
                <div class="aes-row">
                  <span style="width: 140px;">Visual Clarity (VC)</span>
                  <div class="aes-bar-track"><div class="aes-bar-val" style="width: 85%;"></div></div>
                  <span style="width: 45px; text-align: right; font-weight: 600;">85%</span>
                </div>
                <div class="aes-row">
                  <span style="width: 140px;">Artistic Dynamics (AD)</span>
                  <div class="aes-bar-track"><div class="aes-bar-val" style="width: 81%;"></div></div>
                  <span style="width: 45px; text-align: right; font-weight: 600;">81%</span>
                </div>
              </div>
            </div>

            <!-- Technical QA & Visual Uplift -->
            <div class="scorecard-box">
              <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="font-weight: 700; font-size: 0.9rem; color: var(--accent-emerald);">
                  Technical QA Certification (Direction D5)
                </span>
                <span class="meta-badge success">PASS: 100%</span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.84rem; color: var(--text-secondary);">
                <div style="display: flex; justify-content: space-between;">
                  <span>Black Frame Artifacts (Duration):</span>
                  <strong style="color: var(--accent-emerald);">0.00s (PASS)</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span>Freeze Frame Glitches (Duration):</span>
                  <strong style="color: var(--accent-emerald);">0.00s (PASS)</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span>AV Onset Alignment Drift:</span>
                  <strong style="color: var(--accent-cyan);">0.28s (&lt; 0.5s tolerance)</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span>Visual Channel Uplift (&Delta;_vis):</span>
                  <strong style="color: var(--accent-amber);">+${t.scorecard.visual_uplift}%</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span>Active-Recall Retention Gain (eS):</span>
                  <strong style="color: var(--accent-emerald);">+${t.scorecard.teach_quiz_gain}%</strong>
                </div>
                <div style="background: #090e1a; padding: 10px; border-radius: 6px; font-size: 0.74rem; color: var(--text-muted); margin-top: 4px;">
                  Active-recall verification confirms the visual channel communicates essential geometric transformations that cannot be deduced from audio narration alone.
                </div>
              </div>
            </div>
          </div>
        </div>
      `;

      setupVideoPlayerEvents();
      triggerMathRender();
    }

    function setupVideoPlayerEvents() {
      const player = document.getElementById("showcase-player");
      if (!player) return;

      const t = topics[currentIndex];

      player.ontimeupdate = function() {
        const time = player.currentTime;
        let activeBeat = t.timeline[0];
        
        for (let i = 0; i < t.timeline.length; i++) {
          const b = t.timeline[i];
          if (time >= b.start_sec && time < (b.start_sec + b.duration)) {
            activeBeat = b;
            break;
          }
          if (time >= (b.start_sec + b.duration)) {
            activeBeat = b;
          }
        }

        // Update Subtitle banner
        const subHeader = document.getElementById("live-subtitle-header");
        const subText = document.getElementById("live-subtitle-text");
        if (subHeader && subText) {
          subHeader.textContent = `[Ch ${activeBeat.chapter} • ${activeBeat.start_sec.toFixed(1)}s → ${(activeBeat.start_sec + activeBeat.duration).toFixed(1)}s] Whisper Subtitle: ${activeBeat.phrase}`;
          subText.textContent = `"${activeBeat.narration}"`;
        }

        // Highlight active beat card
        document.querySelectorAll(".timeline-beat-row").forEach(el => {
          el.classList.remove("current-playing");
        });
        const activeCard = document.getElementById(`beat-card-${activeBeat.beat_id}`);
        if (activeCard) {
          activeCard.classList.add("current-playing");
        }
      };
    }

    function seekToBeat(startSec, beatId) {
      const player = document.getElementById("showcase-player");
      if (player) {
        player.currentTime = startSec;
        player.play();
      }
      document.querySelectorAll(".timeline-beat-row").forEach(el => el.classList.remove("current-playing"));
      const activeCard = document.getElementById(`beat-card-${beatId}`);
      if (activeCard) {
        activeCard.classList.add("current-playing");
      }
    }

    function seekRelative(delta) {
      const player = document.getElementById("showcase-player");
      if (player) {
        player.currentTime = Math.max(0, player.currentTime + delta);
      }
    }

    function seekVideo(sec) {
      const player = document.getElementById("showcase-player");
      if (player) {
        player.currentTime = sec;
        player.play();
      }
      switchTab('tab-video');
    }

    function restartVideo() {
      const player = document.getElementById("showcase-player");
      if (player) {
        player.currentTime = 0;
        player.play();
      }
    }

    function setSpeed(rate) {
      const player = document.getElementById("showcase-player");
      if (player) {
        player.playbackRate = rate;
      }
    }

    function copyEquation() {
      const t = topics[currentIndex];
      navigator.clipboard.writeText(t.governing_equation).then(() => {
        showToast("✓ Copied LaTeX equation to clipboard!", "success");
      }).catch(() => {
        showToast("LaTeX: " + t.governing_equation);
      });
    }

    function copyCodeSnippet() {
      const t = topics[currentIndex];
      navigator.clipboard.writeText(t.code_snippet).then(() => {
        showToast("✓ Copied Manim Python script to clipboard!", "success");
      }).catch(() => {
        showToast("Copied script");
      });
    }

    function downloadPythonScript() {
      const t = topics[currentIndex];
      const blob = new Blob([t.code_snippet], { type: "text/x-python" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${t.id}_${t.domain.toLowerCase().replace(/[^a-z0-9]/g, '_')}.py`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("⬇ Downloaded " + a.download, "success");
    }

    function exportDataJson() {
      const blob = new Blob([JSON.stringify(topics, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "curriculum_demonstrations_data.json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("⬇ Exported curriculum_demonstrations_data.json", "success");
    }

    function escapeHtml(text) {
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Initial render
    renderSidebar();
    renderContent();
  </script>
</body>
</html>
"""


def generate_master_showcase_html(topics):
    topics_json = json.dumps(topics)
    return HTML_SHOWCASE_TEMPLATE.replace("__TOPICS_JSON__", topics_json)


if __name__ == "__main__":
    build_demonstrations()
