"""
Procedural Visual Asset Generator for Code2Video External Database D_asset.
Generates clean, transparent PNG mathematical and scientific icons
matching Figure 7 in the Code2Video paper (Show Lab, NUS).
"""

import os
from PIL import Image, ImageDraw


def generate_assets(output_dir: str = "assets"):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Coordinate Axes
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # X and Y axis with arrows
    d.line([(30, 226), (226, 226)], fill="#58C4DD", width=4)
    d.line([(30, 226), (30, 30)], fill="#58C4DD", width=4)
    d.polygon([(226, 226), (214, 220), (214, 232)], fill="#58C4DD")
    d.polygon([(30, 30), (24, 42), (36, 42)], fill="#58C4DD")
    # Grid ticks
    for x in range(60, 220, 30):
        d.line([(x, 222), (x, 230)], fill="#888888", width=2)
    for y in range(60, 220, 30):
        d.line([(26, y), (34, y)], fill="#888888", width=2)
    img.save(os.path.join(output_dir, "coordinate_axes.png"))

    # 2. Unit Circle
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([(28, 28), (228, 228)], outline="#83C167", width=4)
    d.line([(128, 20), (128, 236)], fill="#555555", width=2)
    d.line([(20, 128), (236, 128)], fill="#555555", width=2)
    # Radius vector at 45 deg
    d.line([(128, 128), (198, 58)], fill="#FC6255", width=3)
    d.ellipse([(195, 55), (201, 61)], fill="#FC6255")
    img.save(os.path.join(output_dir, "unit_circle.png"))

    # 3. Neural Node
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([(48, 48), (208, 208)], fill="#1E3A8A", outline="#60A5FA", width=6)
    # Sigmoid curve inside
    points = []
    import math
    for px in range(70, 186):
        norm_x = (px - 128) / 15.0
        sig_y = 1.0 / (1.0 + math.exp(-norm_x))
        py = 186 - sig_y * 116
        points.append((px, py))
    d.line(points, fill="#FCD34D", width=4)
    img.save(os.path.join(output_dir, "neural_node.png"))

    # 4. Vector Arrow
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(40, 216), (200, 56)], fill="#F59E0B", width=6)
    d.polygon([(216, 40), (190, 48), (208, 66)], fill="#F59E0B")
    img.save(os.path.join(output_dir, "vector_arrow.png"))

    # 5. Bell Curve (Gaussian)
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(20, 220), (236, 220)], fill="#888888", width=3)
    curve = []
    for px in range(20, 236):
        nx = (px - 128) / 35.0
        gy = math.exp(-0.5 * nx * nx)
        py = 220 - gy * 160
        curve.append((px, py))
    d.line(curve, fill="#A855F7", width=5)
    img.save(os.path.join(output_dir, "bell_curve.png"))

    # 6. Right Triangle
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(40, 216), (216, 216), (40, 60)], fill="#10B98133", outline="#10B981", width=5)
    d.rectangle([(40, 196), (60, 216)], outline="#10B981", width=2)
    img.save(os.path.join(output_dir, "right_triangle.png"))

    print(f"✓ Generated 6 canonical visual assets in '{output_dir}/'")


if __name__ == "__main__":
    generate_assets()

