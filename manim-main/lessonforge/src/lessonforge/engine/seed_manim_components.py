"""
Seed the ChromaDB manim_components collection with 15 expert Manim animation patterns.
Run from stem_animation_lab/ directory:
    python seed_manim_components.py

Requires CHROMADB_ENABLED=1 or just run standalone (the script sets it automatically).
"""

import os, sys
os.environ["CHROMADB_ENABLED"] = "1"

import chromadb

from lessonforge import paths as _paths
CHROMA_PATH = str(_paths.sub("chroma_db"))

COMPONENTS = [
    {
        "id": "elastic_entry_01",
        "document": "elastic bouncy FadeIn entry animation for shapes text title pop-in effect",
        "class_name": "ElasticEntry",
        "summary": "Kurzgesagt-style elastic bounce entry: FadeIn(mobj, scale=0.1, rate_func=rate_functions.ease_out_elastic). Play add_sound('pop.mp3') before each appearance.",
        "class_code": """\
with self.voiceover(text="Watch this concept appear!") as tracker:
    title = Text("Newton's Second Law").scale(0.8).to_edge(UP, buff=0.6)
    formula = MathTex(r"F = ma").scale(1.2)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(title, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.4,
    )
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(formula, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.6,
    )
""",
    },
    {
        "id": "line_draw_01",
        "document": "draw line path arrow Create animation progressive graph force direction",
        "class_name": "LineDrawer",
        "summary": "Use Create(mobj, run_time=tracker.duration) for lines, arrows, and axes so the viewer watches them being drawn. Never FadeIn a line.",
        "class_code": """\
with self.voiceover(text="The force acts along this direction.") as tracker:
    arrow = Arrow(start=LEFT * 2, end=RIGHT * 2, color=YELLOW)
    label = Text("Force F").scale(0.7).next_to(arrow, UP, buff=0.3)
    self.add_sound("whoosh.mp3")
    self.play(Create(arrow), run_time=tracker.duration * 0.6)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(label, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.4,
    )
""",
    },
    {
        "id": "axes_graph_01",
        "document": "coordinate system axes graph function plot velocity position sine cosine",
        "class_name": "AxesWithGraph",
        "summary": "Axes with a function curve drawn progressively using Create(graph, rate_func=ease_out_sine). Axis labels use get_x_axis_label and next_to with explicit buff.",
        "class_code": """\
with self.voiceover(text="Here is how velocity changes over time.") as tracker:
    axes = Axes(
        x_range=[0, 4, 1], y_range=[-2, 2, 1],
        x_length=6, y_length=4,
        axis_config={"color": WHITE},
    ).scale(0.8)
    x_label = axes.get_x_axis_label("t (s)").scale(0.7)
    y_label = axes.get_y_axis_label("v (m/s)").scale(0.7)
    graph = axes.plot(lambda x: np.sin(x * PI / 2), color=TEAL)
    self.add_sound("whoosh.mp3")
    self.play(Create(axes), run_time=tracker.duration * 0.3)
    self.play(
        FadeIn(x_label, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(y_label, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.2,
    )
    self.play(Create(graph, rate_func=rate_functions.ease_out_sine), run_time=tracker.duration * 0.5)
""",
    },
    {
        "id": "camera_pan_01",
        "document": "camera pan shift side diagram equation coexist space layout room",
        "class_name": "CameraPanEquation",
        "summary": "When diagram must stay on screen alongside a new equation, pan camera.frame RIGHT to create empty space instead of cluttering.",
        "class_code": """\
with self.voiceover(text="And the mathematical form is F equals ma.") as tracker:
    equation = MathTex(r"F = ma").scale(1.3).move_to(RIGHT * 3)
    self.play(
        self.camera.frame.animate.shift(RIGHT * 2),
        run_time=tracker.duration * 0.3,
    )
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(equation, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.7,
    )
""",
    },
    {
        "id": "screen_clear_01",
        "document": "clear screen FadeOut all mobjects clean canvas before heavy math equation new concept",
        "class_name": "ScreenClearBeforeMath",
        "summary": "Before a heavy equation, FadeOut non-essential mobjects so the screen is clean. Use Group(*self.mobjects) to clear everything at once.",
        "class_code": """\
with self.voiceover(text="Now let us look at the equation carefully.") as tracker:
    self.play(
        FadeOut(Group(*self.mobjects)),
        run_time=tracker.duration * 0.3,
    )
    equation = MathTex(r"\frac{d^2x}{dt^2} = -\omega^2 x").scale(1.2)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(equation, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.7,
    )
""",
    },
    {
        "id": "force_vector_01",
        "document": "physics free body diagram Newton force weight normal friction arrows labels",
        "class_name": "ForceVectorDiagram",
        "summary": "Free body diagram: Create() for arrows, elastic FadeIn for labels. Each label uses next_to with explicit direction and buff=0.2 to avoid overlap.",
        "class_code": """\
with self.voiceover(text="Three forces act on this block simultaneously.") as tracker:
    block = Square(side_length=1.0, color=BLUE, fill_opacity=0.5).move_to(ORIGIN)
    weight   = Arrow(start=ORIGIN, end=DOWN  * 1.5, color=RED)
    normal   = Arrow(start=ORIGIN, end=UP    * 1.5, color=GREEN)
    friction = Arrow(start=ORIGIN, end=LEFT  * 1.2, color=YELLOW)
    w_lbl = Text("W = mg").scale(0.55).next_to(weight,   RIGHT, buff=0.2)
    n_lbl = Text("N")     .scale(0.55).next_to(normal,   RIGHT, buff=0.2)
    f_lbl = Text("f")     .scale(0.55).next_to(friction, UP,    buff=0.2)
    self.add_sound("pop.mp3")
    self.play(FadeIn(block, scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.2)
    self.add_sound("whoosh.mp3")
    self.play(Create(weight), Create(normal), Create(friction), run_time=tracker.duration * 0.5)
    self.play(
        FadeIn(w_lbl, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(n_lbl, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(f_lbl, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.3,
    )
""",
    },
    {
        "id": "equation_evolution_01",
        "document": "equation algebra derivation step by step TransformMatchingTex evolve parts slide",
        "class_name": "EquationEvolution",
        "summary": "Build equations incrementally using TransformMatchingTex so matching sub-expressions slide in place and new parts appear. Keeps the visual continuity.",
        "class_code": """\
with self.voiceover(text="We start with F equals ma, then isolate acceleration.") as tracker:
    eq1 = MathTex("F", "=", "m", "a").scale(1.2)
    eq2 = MathTex(r"\frac{F}{m}", "=", "a").scale(1.2)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(eq1, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.4,
    )
    self.play(TransformMatchingTex(eq1, eq2), run_time=tracker.duration * 0.6)
""",
    },
    {
        "id": "atom_molecule_01",
        "document": "atom molecule chemistry element proton electron nucleus orbit bond",
        "class_name": "AtomDisplay",
        "summary": "Atom as labeled circle nucleus + orbit circle drawn with Create + electron dot. Labels use next_to with buff=0.1.",
        "class_code": """\
with self.voiceover(text="A hydrogen atom has one proton and one electron.") as tracker:
    nucleus   = Circle(radius=0.3, color=RED, fill_opacity=0.8)
    p_label   = Text("p+").scale(0.45).move_to(nucleus.get_center())
    orbit     = Circle(radius=1.2, color=BLUE_D)
    electron  = Dot(radius=0.12, color=YELLOW).move_to(RIGHT * 1.2)
    e_label   = Text("e-").scale(0.4).next_to(electron, UP, buff=0.1)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(nucleus, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(p_label, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.3,
    )
    self.add_sound("whoosh.mp3")
    self.play(Create(orbit), run_time=tracker.duration * 0.4)
    self.play(
        FadeIn(electron, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(e_label,  scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.3,
    )
""",
    },
    {
        "id": "misconception_contrast_01",
        "document": "misconception wrong right contrast compare before after incorrect correct side by side",
        "class_name": "MisconceptionContrast",
        "summary": "Wrong belief on left (red ✗), correct model on right (green ✓), dividing line drawn with Create. Camera stays wide to show both sides.",
        "class_code": """\
with self.voiceover(text="Many students think heavier objects fall faster. That is wrong.") as tracker:
    wrong_text = Text("Heavier falls faster", color=RED).scale(0.7).move_to(LEFT * 3 + UP * 0.5)
    cross = Text("✗", color=RED).scale(1.5).next_to(wrong_text, DOWN, buff=0.2)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(wrong_text, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(cross,      scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration,
    )

with self.voiceover(text="All objects fall at the same rate in a vacuum.") as tracker:
    correct_text = Text("All fall equally", color=GREEN).scale(0.7).move_to(RIGHT * 3 + UP * 0.5)
    tick     = Text("✓", color=GREEN).scale(1.5).next_to(correct_text, DOWN, buff=0.2)
    divider  = Line(UP * 2, DOWN * 2, color=GRAY)
    self.add_sound("whoosh.mp3")
    self.play(Create(divider), run_time=tracker.duration * 0.3)
    self.add_sound("pop.mp3")
    self.play(
        FadeIn(correct_text, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(tick,         scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.7,
    )
""",
    },
    {
        "id": "hook_curiosity_01",
        "document": "hook curiosity question mark reveal surprise opening engagement mystery",
        "class_name": "CuriosityHook",
        "summary": "Hook scene: large question mark appears elastically, then ReplacementTransforms into the topic title to build curiosity before explanation.",
        "class_code": """\
with self.voiceover(text="Have you ever wondered why the sky is blue?") as tracker:
    q_mark = Text("?", color=TEAL).scale(4)
    sub_q  = Text("Why is the sky blue?").scale(0.8).move_to(DOWN * 2)
    self.add_sound("pop.mp3")
    self.play(FadeIn(q_mark, scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.5)
    self.play(FadeIn(sub_q,  scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.5)

with self.voiceover(text="Today we will find out!") as tracker:
    topic = Text("Rayleigh Scattering", color=TEAL).scale(1.1)
    self.play(
        ReplacementTransform(q_mark, topic),
        FadeOut(sub_q),
        run_time=tracker.duration,
    )
""",
    },
    {
        "id": "geometry_construction_01",
        "document": "geometry triangle angle line perpendicular proof construction right angle bisect",
        "class_name": "GeometryConstruction",
        "summary": "Build a geometric figure step-by-step: base with Create, then vertex, then RightAngle mark, then elastic labels. Each step timed to tracker.duration fraction.",
        "class_code": """\
with self.voiceover(text="Let us construct a right-angled triangle.") as tracker:
    A = Dot(LEFT * 2 + DOWN, color=WHITE)
    B = Dot(RIGHT * 2 + DOWN, color=WHITE)
    C = Dot(RIGHT * 2 + UP * 1.5, color=WHITE)
    base       = Line(A.get_center(), B.get_center(), color=WHITE)
    height     = Line(B.get_center(), C.get_center(), color=WHITE)
    hypotenuse = Line(A.get_center(), C.get_center(), color=TEAL)
    right_mark = RightAngle(base, height, length=0.25, color=YELLOW)
    a_lbl = Text("A").scale(0.6).next_to(A, LEFT,  buff=0.2)
    b_lbl = Text("B").scale(0.6).next_to(B, DOWN,  buff=0.2)
    c_lbl = Text("C").scale(0.6).next_to(C, UP,    buff=0.2)
    self.add_sound("whoosh.mp3")
    self.play(Create(base),       run_time=tracker.duration * 0.2)
    self.play(Create(height),     run_time=tracker.duration * 0.2)
    self.play(Create(hypotenuse, rate_func=rate_functions.ease_out_sine), run_time=tracker.duration * 0.2)
    self.play(
        FadeIn(right_mark, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(a_lbl,      scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(b_lbl,      scale=0.1, rate_func=rate_functions.ease_out_elastic),
        FadeIn(c_lbl,      scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.4,
    )
""",
    },
    {
        "id": "wave_oscillation_01",
        "document": "wave oscillation sine cosine periodic frequency amplitude wavelength sound light",
        "class_name": "WaveOscillation",
        "summary": "Sine wave drawn progressively on axes with Create(wave, rate_func=linear). Amplitude arrow with DoubleArrow and label next_to RIGHT.",
        "class_code": """\
with self.voiceover(text="A wave repeats its pattern at regular intervals.") as tracker:
    axes = Axes(
        x_range=[0, 4 * PI, PI], y_range=[-1.5, 1.5, 0.5],
        x_length=7, y_length=3,
        axis_config={"color": GRAY},
    ).scale(0.8)
    wave      = axes.plot(lambda x: np.sin(x), color=TEAL, x_range=[0, 4 * PI])
    amp_arrow = DoubleArrow(axes.c2p(PI / 2, 0), axes.c2p(PI / 2, 1), color=YELLOW, buff=0)
    amp_lbl   = Text("A").scale(0.6).next_to(amp_arrow, RIGHT, buff=0.15)
    self.add_sound("whoosh.mp3")
    self.play(Create(axes),                            run_time=tracker.duration * 0.25)
    self.play(Create(wave, rate_func=rate_functions.linear), run_time=tracker.duration * 0.5)
    self.play(
        Create(amp_arrow),
        FadeIn(amp_lbl, scale=0.1, rate_func=rate_functions.ease_out_elastic),
        run_time=tracker.duration * 0.25,
    )
""",
    },
    {
        "id": "recap_summary_01",
        "document": "recap summary key points takeaways lesson end review bullet list",
        "class_name": "RecapSummary",
        "summary": "Recap: title appears first, then 3 bullet points pop in one at a time with elastic FadeIn. VGroup arranged DOWN with aligned_edge=LEFT.",
        "class_code": """\
with self.voiceover(text="Let us recap the three key ideas from today.") as tracker:
    title = Text("Key Takeaways", color=TEAL).scale(0.9).to_edge(UP, buff=0.6)
    bullets = VGroup(
        Text("1. Force = mass × acceleration").scale(0.65),
        Text("2. More mass needs more force").scale(0.65),
        Text("3. Direction of force = direction of acceleration").scale(0.65),
    ).arrange(DOWN, aligned_edge=LEFT, buff=0.35).move_to(ORIGIN)
    self.add_sound("pop.mp3")
    self.play(FadeIn(title, scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.2)
    for bullet in bullets:
        self.add_sound("pop.mp3")
        self.play(FadeIn(bullet, scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.27)
""",
    },
    {
        "id": "counting_quantity_01",
        "document": "counting quantity row objects comparison balancing molecules atoms equal number",
        "class_name": "CountingRow",
        "summary": "Show N copies of an object in a row, built one-by-one with elastic FadeIn. Good for counting atoms in a balanced equation or comparing quantities.",
        "class_code": """\
with self.voiceover(text="We have two molecules of hydrogen on the left side.") as tracker:
    h2_molecule = lambda: VGroup(
        Circle(radius=0.25, color=BLUE_D, fill_opacity=0.7),
        Text("H₂").scale(0.5),
    )
    row = VGroup(*[h2_molecule() for _ in range(2)]).arrange(RIGHT, buff=0.5).move_to(LEFT * 3)
    for mol in row:
        self.add_sound("pop.mp3")
        self.play(
            FadeIn(mol, scale=0.1, rate_func=rate_functions.ease_out_elastic),
            run_time=tracker.duration / 2,
        )
""",
    },
    {
        "id": "active_recall_01",
        "document": "active recall question pause challenge quiz blank wait student think",
        "class_name": "ActiveRecall",
        "summary": "Active recall: fade out all visuals, show a question with YELLOW color and a hint line, then self.wait(5) outside the voiceover block.",
        "class_code": """\
with self.voiceover(text="Pause and think — what is the value of g? [PAUSE: RECALL]") as tracker:
    self.play(FadeOut(Group(*self.mobjects)), run_time=tracker.duration * 0.3)
    question = Text("g = ?", color=YELLOW).scale(1.5).move_to(UP * 0.5)
    hint     = Text("Think before continuing...").scale(0.6).move_to(DOWN)
    self.add_sound("pop.mp3")
    self.play(FadeIn(question, scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.4)
    self.play(FadeIn(hint,     scale=0.1, rate_func=rate_functions.ease_out_elastic), run_time=tracker.duration * 0.3)
self.wait(5)
""",
    },
]


def seed():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = client.get_or_create_collection(
        name="manim_components",
        metadata={"description": "Expert Manim component examples for codegen inspiration"},
    )

    existing = set(col.get(ids=[c["id"] for c in COMPONENTS])["ids"])
    to_add = [c for c in COMPONENTS if c["id"] not in existing]

    if not to_add:
        print(f"Collection already has all {len(COMPONENTS)} components. Nothing to add.")
        return

    col.upsert(
        ids=[c["id"] for c in to_add],
        documents=[c["document"] for c in to_add],
        metadatas=[
            {
                "class_name": c["class_name"],
                "summary":    c["summary"],
                "class_code": c["class_code"],
            }
            for c in to_add
        ],
    )
    print(f"Seeded {len(to_add)} components into manim_components. Total: {col.count()}")
    print("\nComponents added:")
    for c in to_add:
        summary = c["summary"][:60].encode("ascii", errors="replace").decode("ascii")
        print(f"  {c['id']:30s}  {summary}...")


if __name__ == "__main__":
    seed()
