"""
Asset Manager Module.
Maintains persistent visual asset cache (D_asset), mathematical templates,
geometric constructs, and reference materials (Code2Video Section 4.1).
"""

from typing import Dict, List, Optional
import os


class AssetManager:
    """Manages visual assets, formula snippets, and geometric templates."""

    def __init__(self, asset_dir: str = "demo_outputs/assets"):
        self.asset_dir = asset_dir
        os.makedirs(self.asset_dir, exist_ok=True)
        self.asset_cache: Dict[str, str] = {}
        self._initialize_built_in_templates()

    def _initialize_built_in_templates(self):
        """Populates common Manim reusable asset snippets."""
        self.asset_cache["svm_hyperplane"] = """# Optimal hyperplane construct
hyperplane = Line(LEFT * 2.5 + DOWN * 1.5, RIGHT * 2.5 + UP * 1.5, color=WHITE, stroke_width=4)
gutter_pos = Line(LEFT * 2.5 + DOWN * 0.5, RIGHT * 2.5 + UP * 2.5, color=BLUE, stroke_width=2, stroke_opacity=0.7)
gutter_neg = Line(LEFT * 2.5 + DOWN * 2.5, RIGHT * 2.5 + UP * 0.5, color=RED, stroke_width=2, stroke_opacity=0.7)
"""
        self.asset_cache["coordinate_system"] = """# 2D Cartesian plane
axes = Axes(
    x_range=[-3, 3, 1],
    y_range=[-3, 3, 1],
    x_length=4.5,
    y_length=4.5,
    axis_config={"color": GREY_B, "stroke_width": 2}
)
"""
        self.asset_cache["complex_plane"] = """# Complex plane with unit circle
axes = ComplexPlane(
    x_range=[-2, 2, 1],
    y_range=[-2, 2, 1],
    x_length=4.0,
    y_length=4.0
).add_coordinates()
unit_circle = Circle(radius=1.0, color=BLUE_B, stroke_width=2)
"""

    def get_template(self, name: str) -> Optional[str]:
        return self.asset_cache.get(name)

    def register_template(self, name: str, code_snippet: str):
        self.asset_cache[name] = code_snippet

