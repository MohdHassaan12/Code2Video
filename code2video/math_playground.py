"""
Interactive Mathematical Parameter Playground Module.
Exports standalone dynamic HTML5 Canvas / JavaScript parameter exploration widgets
for mathematical concepts, transforming static formulas into explorable explanations:
- Euler's Formula Phasor Rotation ($e^{i\\theta} = \\cos\\theta + i\\sin\\theta$)
- Support Vector Machine Margin & Hyperplane ($w^T x + b = 0$)
- Fourier Series Epicycles & Harmonics
- Pythagorean Geometric Rearrangement
"""

import os
from typing import Dict, Any, Optional


class MathPlaygroundGenerator:
    """Generates interactive browser-based mathematical exploratory sandboxes."""

    @classmethod
    def generate_euler_playground(cls, output_path: str) -> str:
        """Generates an interactive Euler's Formula Unit Circle Phasor widget."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Euler's Formula - Interactive Phasor Playground</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: #0f1117; color: #e1e7ed; margin: 0; padding: 24px; display: flex; flex-direction: column; align-items: center; }
    h1 { font-size: 1.4rem; color: #58c4dd; margin-bottom: 8px; }
    p { color: #8b949e; font-size: 0.9rem; max-width: 600px; text-align: center; margin-bottom: 20px; }
    canvas { background: #1a1d24; border: 1px solid #30363d; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
    .controls { margin-top: 18px; display: flex; gap: 16px; align-items: center; background: #1a1d24; padding: 12px 20px; border-radius: 8px; border: 1px solid #30363d; }
    label { font-size: 0.95rem; font-weight: 600; }
    input[type=range] { width: 220px; accent-color: #58c4dd; }
    .val-badge { background: rgba(88,196,221,0.2); color: #58c4dd; padding: 4px 10px; border-radius: 4px; font-family: monospace; font-weight: bold; }
  </style>
</head>
<body>
  <h1>Euler's Formula: e^{iθ} = cos(θ) + i·sin(θ)</h1>
  <p>Drag the slider to rotate the complex phasor along the unit circle in the complex plane.</p>
  <canvas id="cv" width="500" height="400"></canvas>
  <div class="controls">
    <label for="theta">Angle θ:</label>
    <input type="range" id="theta" min="0" max="6.283" step="0.02" value="0.785">
    <span id="badge" class="val-badge">θ = 0.79 rad (45°)</span>
  </div>
  <script>
    const cv = document.getElementById('cv');
    const ctx = cv.getContext('2d');
    const slider = document.getElementById('theta');
    const badge = document.getElementById('badge');

    const cx = 250, cy = 200, R = 140;

    function draw() {
      const th = parseFloat(slider.value);
      const deg = Math.round(th * 180 / Math.PI);
      const cosVal = Math.cos(th).toFixed(2);
      const sinVal = Math.sin(th).toFixed(2);
      badge.textContent = `θ = ${th.toFixed(2)} rad (${deg}°) | e^{iθ} = ${cosVal} + ${sinVal}i`;

      ctx.clearRect(0, 0, cv.width, cv.height);

      // Grid & Axes
      ctx.strokeStyle = '#30363d';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(30, cy); ctx.lineTo(470, cy);
      ctx.moveTo(cx, 20); ctx.lineTo(cx, 380);
      ctx.stroke();

      // Axis Labels
      ctx.fillStyle = '#8b949e';
      ctx.font = '12px sans-serif';
      ctx.fillText('Re (Real)', 420, cy - 8);
      ctx.fillText('Im (Imaginary)', cx + 8, 35);

      // Unit Circle
      ctx.strokeStyle = '#444c56';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.stroke();

      // Cosine projection (horizontal)
      const px = cx + R * Math.cos(th);
      const py = cy - R * Math.sin(th);

      ctx.strokeStyle = '#83c167'; // green
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cx, cy); ctx.lineTo(px, cy);
      ctx.stroke();

      // Sine projection (vertical)
      ctx.strokeStyle = '#ffff00'; // yellow
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(px, cy); ctx.lineTo(px, py);
      ctx.stroke();

      // Phasor vector
      ctx.strokeStyle = '#58c4dd'; // cyan
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cx, cy); ctx.lineTo(px, py);
      ctx.stroke();

      // Dot on circle
      ctx.fillStyle = '#fc6255';
      ctx.beginPath();
      ctx.arc(px, py, 6, 0, Math.PI * 2);
      ctx.fill();
    }

    slider.oninput = draw;
    draw();
  </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path

    @classmethod
    def generate_svm_playground(cls, output_path: str) -> str:
        """Generates an interactive Support Vector Machine margin sandbox."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SVM - Interactive Maximum Margin Hyperplane</title>
  <style>
    body { font-family: -apple-system, sans-serif; background: #0f1117; color: #e1e7ed; margin: 0; padding: 24px; display: flex; flex-direction: column; align-items: center; }
    h1 { font-size: 1.4rem; color: #58c4dd; margin-bottom: 8px; }
    canvas { background: #1a1d24; border: 1px solid #30363d; border-radius: 8px; }
    .controls { margin-top: 18px; display: flex; gap: 16px; align-items: center; background: #1a1d24; padding: 12px 20px; border-radius: 8px; }
    input[type=range] { width: 180px; accent-color: #58c4dd; }
    .val-badge { color: #83c167; font-family: monospace; font-weight: bold; }
  </style>
</head>
<body>
  <h1>Support Vector Machine: Maximum Margin Hyperplane</h1>
  <canvas id="cv" width="500" height="400"></canvas>
  <div class="controls">
    <label>Angle Slope:</label>
    <input type="range" id="slope" min="-1.5" max="1.5" step="0.05" value="-0.6">
    <label>Margin Width:</label>
    <input type="range" id="margin" min="15" max="60" step="1" value="35">
    <span id="badge" class="val-badge">Margin = 35px</span>
  </div>
  <script>
    const cv = document.getElementById('cv');
    const ctx = cv.getContext('2d');
    const sSlider = document.getElementById('slope');
    const mSlider = document.getElementById('margin');
    const badge = document.getElementById('badge');

    // Data points (+1 and -1 classes)
    const pts1 = [[120, 100], [160, 120], [200, 80], [140, 150]];
    const pts2 = [[320, 310], [360, 270], [390, 320], [300, 260]];

    function draw() {
      const m = parseFloat(sSlider.value);
      const margin = parseFloat(mSlider.value);
      badge.textContent = `Margin γ = ${(2.0 / (margin/10)).toFixed(2)}`;

      ctx.clearRect(0, 0, cv.width, cv.height);

      // Draw margin street (filled polygon)
      const cx = 250, cy = 200;
      const angle = Math.atan(m);
      const nx = -Math.sin(angle) * margin;
      const ny = Math.cos(angle) * margin;

      ctx.fillStyle = 'rgba(88, 196, 221, 0.08)';
      ctx.beginPath();
      ctx.moveTo(0, cy - m * cx - ny);
      ctx.lineTo(500, cy + m * (500 - cx) - ny);
      ctx.lineTo(500, cy + m * (500 - cx) + ny);
      ctx.lineTo(0, cy - m * cx + ny);
      ctx.closePath();
      ctx.fill();

      // Hyperplane (w^T x + b = 0)
      ctx.strokeStyle = '#58c4dd';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(0, cy - m * cx);
      ctx.lineTo(500, cy + m * (500 - cx));
      ctx.stroke();

      // Dashed margin boundaries
      ctx.strokeStyle = '#83c167';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(0, cy - m * cx + ny);
      ctx.lineTo(500, cy + m * (500 - cx) + ny);
      ctx.moveTo(0, cy - m * cx - ny);
      ctx.lineTo(500, cy + m * (500 - cx) - ny);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw points
      ctx.fillStyle = '#fc6255';
      pts1.forEach(([x, y]) => {
        ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill();
      });

      ctx.fillStyle = '#83c167';
      pts2.forEach(([x, y]) => {
        ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill();
      });
    }

    sSlider.oninput = draw;
    mSlider.oninput = draw;
    draw();
  </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path
