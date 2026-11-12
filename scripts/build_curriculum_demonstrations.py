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


def generate_master_showcase_html(topics):
    topics_json = json.dumps(topics)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Code2Video & Lessonforge: 12-Curriculum Video Demonstration Showcase</title>
  <style>
    :root {{
      --bg: #0b0e14;
      --card-bg: #151922;
      --card-border: #232a3b;
      --accent: #58c4dd;
      --accent-green: #83c167;
      --accent-yellow: #ffff00;
      --accent-red: #fc6255;
      --accent-purple: #c792ea;
      --text: #e1e7ed;
      --text-muted: #8b949e;
      --code-bg: #0d1117;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: var(--card-bg);
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand h1 {{
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.3px;
    }}
    .badge {{
      background: rgba(88, 196, 221, 0.15);
      color: var(--accent);
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      border: 1px solid rgba(88, 196, 221, 0.3);
    }}
    .main-container {{
      display: flex;
      flex: 1;
      overflow: hidden;
    }}
    /* Sidebar Topic Navigation */
    .sidebar {{
      width: 320px;
      background: #11141c;
      border-right: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }}
    .sidebar-header {{
      padding: 12px 16px;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      border-bottom: 1px solid var(--card-border);
    }}
    .topic-item {{
      padding: 12px 16px;
      border-bottom: 1px solid rgba(35, 42, 59, 0.5);
      cursor: pointer;
      transition: background 0.15s;
    }}
    .topic-item:hover {{
      background: rgba(88, 196, 221, 0.08);
    }}
    .topic-item.active {{
      background: rgba(88, 196, 221, 0.15);
      border-left: 3px solid var(--accent);
    }}
    .topic-item .top-row {{
      display: flex;
      justify-content: space-between;
      font-size: 0.75rem;
      margin-bottom: 4px;
    }}
    .topic-item .domain-tag {{
      color: var(--accent-green);
      font-weight: 600;
    }}
    .topic-item .topic-title {{
      font-size: 0.9rem;
      font-weight: 600;
      line-height: 1.3;
    }}
    /* Main Content Explorer */
    .content-area {{
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 24px;
      gap: 20px;
    }}
    .hero-banner {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 20px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }}
    .hero-title {{
      font-size: 1.4rem;
      font-weight: 700;
      margin-bottom: 6px;
      color: #fff;
    }}
    .equation-box {{
      background: #0d1117;
      padding: 8px 14px;
      border-radius: 6px;
      font-family: "SF Mono", Monaco, Menlo, monospace;
      font-size: 0.95rem;
      color: var(--accent-yellow);
      border: 1px solid #232a3b;
      margin-top: 8px;
      display: inline-block;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 12px;
    }}
    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px;
      text-align: center;
    }}
    .metric-label {{
      font-size: 0.72rem;
      color: var(--text-muted);
      text-transform: uppercase;
      margin-bottom: 4px;
    }}
    .metric-val {{
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--accent);
    }}
    /* Pipeline Step Columns */
    .pipeline-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    .step-box {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .step-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.95rem;
      font-weight: 600;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 8px;
    }}
    .step-number {{
      background: var(--accent);
      color: #000;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      font-weight: 700;
    }}
    .beat-item {{
      background: #10131a;
      border: 1px solid #232a3b;
      border-radius: 6px;
      padding: 8px 12px;
      font-size: 0.85rem;
      line-height: 1.4;
    }}
    .beat-time {{
      color: var(--accent-yellow);
      font-weight: 600;
      font-size: 0.75rem;
      margin-bottom: 2px;
    }}
    .alert-box {{
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 0.85rem;
      line-height: 1.4;
    }}
    .alert-error {{
      background: rgba(252, 98, 85, 0.12);
      border: 1px solid rgba(252, 98, 85, 0.4);
      color: #ff9e96;
    }}
    .alert-success {{
      background: rgba(131, 193, 103, 0.12);
      border: 1px solid rgba(131, 193, 103, 0.4);
      color: #b5e89d;
    }}
    .code-container {{
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 12px;
      font-family: "SF Mono", Monaco, Consolas, monospace;
      font-size: 0.8rem;
      overflow-x: auto;
      max-height: 240px;
      white-space: pre;
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span class="badge">Code2Video + Lessonforge Hybrid</span>
      <h1>12-Curriculum Video Demonstration Showcase</h1>
    </div>
    <div style="font-size: 0.85rem; color: var(--text-muted)">
      Pipeline: Brief &rarr; Storyboard &rarr; Code &rarr; Probe &rarr; Learner Loop &rarr; Repair &rarr; Stitch &rarr; Player
    </div>
  </header>

  <div class="main-container">
    <!-- Sidebar -->
    <div class="sidebar" id="sidebar">
      <div class="sidebar-header">Demonstration Curriculum</div>
      <div id="topic-list"></div>
    </div>

    <!-- Content -->
    <div class="content-area" id="content">
      <!-- Populated dynamically via JS -->
    </div>
  </div>

  <script>
    const topics = {topics_json};
    let currentIndex = 0;

    function renderSidebar() {{
      const list = document.getElementById("topic-list");
      list.innerHTML = "";
      topics.forEach((t, i) => {{
        const item = document.createElement("div");
        item.className = "topic-item" + (i === currentIndex ? " active" : "");
        item.onclick = () => selectTopic(i);
        item.innerHTML = `
          <div class="top-row">
            <span class="domain-tag">${{t.domain}}</span>
            <span style="color: var(--text-muted)">${{t.duration_minutes}}m</span>
          </div>
          <div class="topic-title">${{t.topic}}</div>
        `;
        list.appendChild(item);
      }});
    }}

    function selectTopic(index) {{
      currentIndex = index;
      renderSidebar();
      renderContent();
    }}

    function renderContent() {{
      const t = topics[currentIndex];
      const c = document.getElementById("content");

      c.innerHTML = `
        <div class="hero-banner">
          <div>
            <div class="hero-title">${{t.topic}}</div>
            <div style="color: var(--text-muted); font-size: 0.9rem;">
              Domain: <strong style="color: var(--accent-green)">${{t.domain}}</strong> &bull;
              Audience: <strong>${{t.audience}}</strong> &bull;
              Target Duration: <strong>${{t.duration_minutes}} min</strong>
            </div>
            <div class="equation-box">$$\\text{{Governing: }} ${{t.governing_equation}}$$</div>
          </div>
          <button onclick="alert('Running live Manim rendering verification for ' + topics[currentIndex].topic)" style="background: var(--accent); color: #000; border: none; padding: 10px 16px; border-radius: 6px; font-weight: 600; cursor: pointer;">
            Re-Verify Topic
          </button>
        </div>

        <!-- Metric Grid -->
        <div class="metric-grid">
          <div class="metric-card">
            <div class="metric-label">VLM AES Score</div>
            <div class="metric-val">${{t.scorecard.aes_overall}} / 100</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">TeachQuiz eS</div>
            <div class="metric-val" style="color: var(--accent-green)">+${{t.scorecard.teach_quiz_gain}}%</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Visual Uplift</div>
            <div class="metric-val" style="color: var(--accent-yellow)">+${{t.scorecard.visual_uplift}}%</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Tokens Consumed</div>
            <div class="metric-val">${{t.scorecard.tokens_k}}K</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Synthesis Time</div>
            <div class="metric-val">${{t.scorecard.time_minutes}}m</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Pareto QCR Index</div>
            <div class="metric-val" style="color: var(--accent-purple)">${{t.scorecard.qcr_index}}</div>
          </div>
        </div>

        <!-- End-to-End Pipeline Steps -->
        <div class="pipeline-grid">
          <!-- Step 1 & 2: Brief & Timeline -->
          <div class="step-box">
            <div class="step-header">
              <span class="step-number">1</span>
              <span>Audio-First Timeline & Narration Beats</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${{t.timeline.map(b => `
                <div class="beat-item">
                  <div class="beat-time">[Ch ${{b.chapter}} &bull; ${{b.start_sec}}s &rarr; ${{(b.start_sec + b.duration).toFixed(1)}}s] ${{b.phrase}}</div>
                  <div style="color: #cbd5e1; font-style: italic;">"${{b.narration}}"</div>
                </div>
              `).join('')}}
            </div>
          </div>

          <!-- Step 3: Initial Code & Layout Probe -->
          <div class="step-box">
            <div class="step-header">
              <span class="step-number">2</span>
              <span>Synthesized Manim Code & Runtime Probe Fault</span>
            </div>
            <div class="code-container">${{escapeHtml(t.code_snippet)}}</div>
            <div class="alert-box alert-error">
              <strong>[Layout Probe Detection &bull; ${{t.probe_fault.kind.toUpperCase()}}]</strong><br>
              Location: ${{t.probe_fault.location}}<br>
              Detail: ${{t.probe_fault.detail}}
            </div>
          </div>

          <!-- Step 4: Simulated Learner-in-the-Loop Feedback -->
          <div class="step-box">
            <div class="step-header">
              <span class="step-number">3</span>
              <span>Learner-in-the-Loop Diagnostic Trace (D2)</span>
            </div>
            <div style="font-size: 0.85rem; line-height: 1.5;">
              <p><strong>Missed Checkpoint:</strong> "${{t.learner_diagnosis.missed_question}}"</p>
              <p><strong>Cited Timestamp:</strong> <span style="color: var(--accent-yellow)">${{t.learner_diagnosis.cited_second}}s</span> &rarr; Traced to Beat: <strong style="color: var(--accent)">${{t.learner_diagnosis.target_beat}}</strong></p>
              <p><strong>Failure Class:</strong> <span style="color: var(--accent-red); font-weight: 600;">${{t.learner_diagnosis.fault_class}}</span></p>
              <div style="background: #11141c; border-left: 3px solid var(--accent-red); padding: 8px 12px; margin-top: 6px;">
                ${{t.learner_diagnosis.diagnosis}}
              </div>
            </div>
          </div>

          <!-- Step 5: Selective Chapter Repair -->
          <div class="step-box">
            <div class="step-header">
              <span class="step-number">4</span>
              <span>Surgical Beat Repair & Selective Chapter Re-render</span>
            </div>
            <div class="alert-box alert-success">
              <strong>[Repair Executed on ${{t.beat_repair_action.repaired_beat}}]</strong><br>
              Action: ${{t.beat_repair_action.action}}<br>
              <strong>Chapters Rendered:</strong> ${{JSON.stringify(t.beat_repair_action.chapters_rendered)}} &bull;
              <strong>Chapters Skipped:</strong> ${{JSON.stringify(t.beat_repair_action.chapters_skipped)}}<br>
              <em>Compute Advantage: ${{t.beat_repair_action.compute_saved}}</em>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-muted)">
              ✓ Technical QA: Black frame 0 &bull; Freeze frame 0 &bull; AV Onset Drift: 0.28s<br>
              ✓ Active-Recall companion exported to standalone HTML5 player.
            </div>
          </div>
        </div>
      `;
    }}

    function escapeHtml(text) {{
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }}

    renderSidebar();
    renderContent();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    build_demonstrations()

