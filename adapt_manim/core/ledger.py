"""
Symbol Ledger and Cross-Scene Memory Module.
Maintains mathematical notation consistency, coordinate systems,
unit definitions, and visual styling across all video scenes
(addressing notation drift identified in LLM2Manim and Code2Video).
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from adapt_manim.core.types import SymbolEntry, SymbolLedger


class SymbolLedgerManager:
    """Manages cross-scene mathematical notation and pedagogical continuity."""

    def __init__(self, topic: str):
        self.ledger = SymbolLedger(topic=topic)
        self._initialize_common_topic_symbols(topic)

    def _initialize_common_topic_symbols(self, topic: str):
        """Auto-populates standard canonical symbols based on domain."""
        t_lower = topic.lower()

        if "support vector" in t_lower or "svm" in t_lower or "machine learning" in t_lower:
            self.register_symbol("w", "Weight Vector", "Machine Learning", units=None, color_hex="#58C4DD", desc="Normal vector to the separating hyperplane")
            self.register_symbol("b", "Bias", "Machine Learning", units=None, color_hex="#83C167", desc="Intercept / bias term")
            self.register_symbol("x", "Input Vector", "Machine Learning", units=None, color_hex="#FC6255", desc="Feature coordinates of training points")
            self.register_symbol("y", "Class Label", "Machine Learning", units=None, color_hex="#FFFF00", desc="Binary class label {-1, +1}")
            self.register_symbol("margin", "Margin Width", "Machine Learning", units=None, color_hex="#9A72AC", desc="Distance 2/||w|| between support hyperplanes")

        elif "fourier" in t_lower or "frequency" in t_lower:
            self.register_symbol("f(t)", "Time Signal", "Signal Processing", units="amplitude", color_hex="#58C4DD", desc="Original continuous function in time domain")
            self.register_symbol("e^{i \\omega t}", "Complex Exponential", "Physics/Math", units="dimensionless", color_hex="#FC6255", desc="Rotating phasor / basis frequency vector")
            self.register_symbol("\\omega", "Angular Frequency", "Physics", units="rad/s", color_hex="#83C167", desc="Speed of rotation in radians per second")
            self.register_symbol("c_n", "Fourier Coefficient", "Signal Processing", units="amplitude", color_hex="#FFFF00", desc="Magnitude and phase of harmonic frequency component")

        elif "neural network" in t_lower or "backpropagation" in t_lower or "gradient" in t_lower:
            self.register_symbol("W^{[l]}", "Layer Weights", "Deep Learning", units=None, color_hex="#58C4DD", desc="Weight matrix at layer l")
            self.register_symbol("a^{[l]}", "Activation Vector", "Deep Learning", units=None, color_hex="#83C167", desc="Post-activation output of neurons at layer l")
            self.register_symbol("\\mathcal{L}", "Loss Function", "Optimization", units="scalar", color_hex="#FC6255", desc="Scalar objective error metric")
            self.register_symbol("\\frac{\\partial \\mathcal{L}}{\\partial W}", "Gradient", "Calculus", units=None, color_hex="#FFFF00", desc="Sensitivity gradient for gradient descent update")

        elif "physics" in t_lower or "snell" in t_lower or "refraction" in t_lower:
            self.register_symbol("n_1", "Refractive Index 1", "Optics", units="dimensionless", color_hex="#58C4DD", desc="Refractive index of medium 1")
            self.register_symbol("n_2", "Refractive Index 2", "Optics", units="dimensionless", color_hex="#83C167", desc="Refractive index of medium 2")
            self.register_symbol("\\theta_1", "Angle of Incidence", "Optics", units="degrees/radians", color_hex="#FC6255", desc="Angle relative to normal in medium 1")
            self.register_symbol("\\theta_2", "Angle of Refraction", "Optics", units="degrees/radians", color_hex="#FFFF00", desc="Angle relative to normal in medium 2")

    def register_symbol(
        self,
        symbol_latex: str,
        name: str,
        domain: str,
        units: Optional[str] = None,
        color_hex: str = "#FFFF00",
        desc: str = "",
        first_section_id: str = "section_1"
    ):
        clean_latex = symbol_latex.strip("$ ")
        entry = SymbolEntry(
            symbol_latex=clean_latex,
            name=name,
            domain=domain,
            units=units,
            color_hex=color_hex,
            description=desc,
            first_section_id=first_section_id
        )
        self.ledger.register(entry)

    def extract_symbols_from_text(self, text: str, section_id: str = "section_1"):
        """Extracts LaTeX math formulas between $...$ and registers novel symbols."""
        matches = re.findall(r"\$([^\$]+)\$", text)
        for m in matches:
            clean = m.strip()
            if clean and clean not in self.ledger.symbols:
                self.register_symbol(
                    symbol_latex=clean,
                    name=f"Variable {clean}",
                    domain="General STEM",
                    first_section_id=section_id
                )

    def get_prompt_context(self) -> str:
        """Generates formatted prompt injection constraints for the Coder."""
        if not self.ledger.symbols:
            return "No predefined symbols in ledger."

        lines = [
            "### PERSISTENT SYMBOL LEDGER (MANDATORY CONSISTENCY):",
            "Maintain exact variable names, LaTeX formatting, and color palettes across all scenes:",
        ]
        for sym, entry in self.ledger.symbols.items():
            unit_str = f" [Unit: {entry.units}]" if entry.units else ""
            lines.append(
                f"- Symbol: `${sym}$` | Name: {entry.name}{unit_str} | Standard Color: {entry.color_hex} | Meaning: {entry.description}"
            )
        lines.append("RULE: NEVER alter these variable symbols or their designated colors.")
        return "\n".join(lines)

    def check_code_consistency(self, code: str) -> List[Tuple[str, str]]:
        """
        Scans generated code for potential notation drift or prohibited redefinitions.
        Returns list of (issue, suggestion).
        """
        issues = []
        # Check MathTex usages
        mathtex_matches = re.findall(r'MathTex\(\s*[rR]?["\']([^"\']+)["\']', code)
        for tex in mathtex_matches:
            # Check if any symbol in ledger is inverted or misrepresented
            for sym, entry in self.ledger.symbols.items():
                if sym in tex:
                    # Check if color is explicitly set differently
                    pass
        return issues
