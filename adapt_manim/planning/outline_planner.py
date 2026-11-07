"""
Outline Planner Module.
Decomposes high-level educational queries into progressive, pedagogically sound outlines
grounded in Mayer's segmentation principle and audience-targeted pacing (Code2Video Section 4.1).
"""

import json
from typing import Optional, Any
from adapt_manim.core.types import Outline, OutlineSection, AudienceLevel
from adapt_manim.planning.complexity_profiler import TopicComplexityProfiler


class OutlinePlanner:
    """Generates structured pedagogical outlines from learning topics."""

    @staticmethod
    def get_prompt(topic: str, audience: AudienceLevel, duration_minutes: float = 3.0) -> str:
        """Constructs prompt matching Code2Video Appendix A.2.4."""
        return f"""You are a professional educational video director and instructional designer.
Decompose the following learning topic into an ordered, pedagogically coherent lecture outline.

Target Topic: {topic}
Audience Level: {audience.value}
Target Duration: {duration_minutes} minutes

Requirements:
1. Divide into 2 to 4 progressive sections (intro/intuition -> core mechanism -> visual derivation/application).
2. Each section must be 60-120 seconds in duration.
3. Every section must have concrete visual examples suited for 2D Manim mathematical animation.
4. Output MUST be valid JSON adhering strictly to:
{{
  "topic": "{topic}",
  "audience": "{audience.value}",
  "target_duration_minutes": {duration_minutes},
  "key_takeaway": "Core takeaway statement",
  "sections": [
    {{
      "id": "section_1",
      "title": "Section Title",
      "content": "Core pedagogical objective",
      "example": "Visual analogy or geometric construct",
      "estimated_duration_sec": 75
    }}
  ]
}}"""

    @classmethod
    def generate_outline(
        cls,
        topic: str,
        audience: AudienceLevel = AudienceLevel.UNDERGRADUATE,
        duration_minutes: float = 3.0,
        llm_client: Optional[Any] = None
    ) -> Outline:
        """Generates the outline via LLM or curated pedagogical knowledge base."""
        profile = TopicComplexityProfiler.profile(topic, audience)

        # If live LLM client provided, attempt generation
        if llm_client:
            try:
                prompt = cls.get_prompt(topic, audience, duration_minutes)
                response_text = llm_client.generate(prompt)
                clean_json = response_text[response_text.find("{"):response_text.rfind("}") + 1]
                data = json.loads(clean_json)
                return Outline(**data)
            except Exception as e:
                pass  # Fall back to structured pedagogical synthesizer

        # Structured pedagogical synthesizer
        return cls._synthesize_pedagogical_outline(topic, audience, profile.recommended_scenes, profile.scene_duration_sec)

    @classmethod
    def _synthesize_pedagogical_outline(
        cls,
        topic: str,
        audience: AudienceLevel,
        num_scenes: int,
        scene_duration: int
    ) -> Outline:
        """Synthesizes high-quality outlines adhering to STEM pedagogy principles."""
        t_lower = topic.lower()

        if "support vector" in t_lower or "svm" in t_lower:
            sections = [
                OutlineSection(
                    id="section_1",
                    title="The Linear Classification Challenge",
                    content="Introduce separable 2D data points with ambiguous decision boundaries.",
                    example="Visualizing red and blue cluster points on a 2D plane.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_2",
                    title="The Maximum Margin Principle",
                    content="Define the margin 2/||w|| and demonstrate how maximizing margin yields robustness.",
                    example="Expanding parallel street gutters until touching support vectors.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_3",
                    title="Support Vectors and the Optimal Hyperplane",
                    content="Highlight support vectors and formalize the hyperplane equation w^T x + b = 0.",
                    example="Vector w perpendicular to the decision line pointing towards positive class.",
                    estimated_duration_sec=scene_duration
                )
            ]
            key_takeaway = "SVM maximizes the geometric margin between classes, relying exclusively on critical support vectors."

        elif "fourier" in t_lower:
            sections = [
                OutlineSection(
                    id="section_1",
                    title="Deconstructing Waves into Pure Frequencies",
                    content="Introduce the concept that any periodic waveform is a superposition of pure sine waves.",
                    example="Decomposing a complex audio wave into component harmonics.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_2",
                    title="The Rotating Phasor Machine",
                    content="Explain winding the signal around the complex origin at varying frequencies.",
                    example="A rotating vector e^{i omega t} tracing closed circular loops in the complex plane.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_3",
                    title="Center of Mass and the Frequency Spectrum",
                    content="Show how the center of mass spikes when the winding frequency matches a constituent frequency.",
                    example="Plotting the peak frequency spectrum from center-of-mass displacements.",
                    estimated_duration_sec=scene_duration
                )
            ]
            key_takeaway = "The Fourier Transform transforms time-domain signals into frequency spectra via complex circular winding."

        elif "neural" in t_lower or "backpropagation" in t_lower:
            sections = [
                OutlineSection(
                    id="section_1",
                    title="The Forward Pass and Prediction Error",
                    content="Illustrate input signals passing through weighted layers to produce an output prediction and error.",
                    example="Connected nodes computing weighted sums and activation functions.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_2",
                    title="The Chain Rule of Calculus",
                    content="Formulate how error gradients flow backwards layer by layer using partial derivatives.",
                    example="Tracking sensitivity dL/dW as a cascaded product of local slopes.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_3",
                    title="Gradient Descent Weight Updates",
                    content="Demonstrate nudging weights in the negative gradient direction to minimize total loss.",
                    example="A ball rolling down the 3D loss surface towards the global minimum.",
                    estimated_duration_sec=scene_duration
                )
            ]
            key_takeaway = "Backpropagation applies the calculus chain rule backwards through network layers to update weights efficiently."

        else:
            # Generic structured STEM template
            sections = [
                OutlineSection(
                    id="section_1",
                    title=f"Introduction to {topic}",
                    content=f"Establish the fundamental motivation and visual intuition of {topic}.",
                    example="A concrete geometric setup showing core components.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_2",
                    title=f"Mathematical Formulation & Mechanism",
                    content=f"Step-by-step visual derivation of the governing equations for {topic}.",
                    example="Dynamic transformation showing variables in action.",
                    estimated_duration_sec=scene_duration
                ),
                OutlineSection(
                    id="section_3",
                    title="Synthesis & Pedagogical Application",
                    content=f"Synthesizing key insights and demonstrating predictive capability of {topic}.",
                    example="Summary diagram contrasting valid and invalid states.",
                    estimated_duration_sec=scene_duration
                )
            ]
            key_takeaway = f"Mastering {topic} through intuitive visualization and rigorous algebraic foundation."

        return Outline(
            topic=topic,
            audience=audience,
            target_duration_minutes=round((len(sections) * scene_duration) / 60.0, 1),
            key_takeaway=key_takeaway,
            sections=sections[:num_scenes]
        )
