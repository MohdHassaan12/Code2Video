"""
Spoken-to-Visual Grounding Matrix Module (Direction D9+).
Implements fine-grained semantic and temporal grounding between spoken narration
and on-screen visual animations, eliminating the 'talking head' decoration trap.

Key Capabilities:
1. Spoken Entity Extraction: Identifies mathematical symbols, quantities, and pedagogical terms from narration.
2. Visual Mobject AST Extraction: Discovers rendered objects, labels, and animation triggers from Manim code.
3. Temporal Alignment: Correlates spoken utterance windows with visual animation moments (Mayer's Contiguity).
4. Grounding Matrix Computation: Calculates Grounding Ratio, detects ungrounded spoken concepts and orphan visuals.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SpokenEntity:
    entity_id: str
    term: str
    category: str  # "variable", "formula", "number", "concept", "theorem"
    start_sec: float
    end_sec: float
    phrase: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "term": self.term,
            "category": self.category,
            "start_sec": round(self.start_sec, 2),
            "end_sec": round(self.end_sec, 2),
            "phrase": self.phrase,
        }


@dataclass
class VisualEntity:
    obj_name: str
    mobject_class: str
    source_line: int
    animation_timestamp: float
    action_type: str  # "Write", "Create", "Indicate", "Transform", "FadeIn", "Circumscribe"
    raw_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obj_name": self.obj_name,
            "mobject_class": self.mobject_class,
            "source_line": self.source_line,
            "animation_timestamp": round(self.animation_timestamp, 2),
            "action_type": self.action_type,
            "raw_label": self.raw_label,
        }


@dataclass
class GroundingMatch:
    spoken_entity: SpokenEntity
    visual_entity: Optional[VisualEntity]
    time_delta_sec: float
    is_grounded: bool
    status: str  # "grounded_exact", "grounded_semantic", "temporal_drift", "ungrounded_missing"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.spoken_entity.term,
            "category": self.spoken_entity.category,
            "spoken_time": round(self.spoken_entity.start_sec, 2),
            "visual_obj": self.visual_entity.obj_name if self.visual_entity else None,
            "visual_class": self.visual_entity.mobject_class if self.visual_entity else None,
            "visual_time": round(self.visual_entity.animation_timestamp, 2) if self.visual_entity else None,
            "time_delta_sec": round(self.time_delta_sec, 2),
            "is_grounded": self.is_grounded,
            "status": self.status,
        }


@dataclass
class GroundingMatrixReport:
    topic: str
    total_spoken_entities: int
    grounded_count: int
    ungrounded_count: int
    grounding_ratio: float  # 0.0 - 1.0
    grounding_score: float  # 0 - 100
    mayer_contiguity_score: float  # 0 - 100
    passed: bool
    matches: List[GroundingMatch] = field(default_factory=list)
    ungrounded_entities: List[Dict[str, Any]] = field(default_factory=list)
    orphan_visuals: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "total_spoken_entities": self.total_spoken_entities,
            "grounded_count": self.grounded_count,
            "ungrounded_count": self.ungrounded_count,
            "grounding_ratio": round(self.grounding_ratio, 3),
            "grounding_score": round(self.grounding_score, 1),
            "mayer_contiguity_score": round(self.mayer_contiguity_score, 1),
            "passed": self.passed,
            "matches": [m.to_dict() for m in self.matches],
            "ungrounded_entities": self.ungrounded_entities,
            "orphan_visuals": self.orphan_visuals,
        }


class SpokenVisualGroundingMatrix:
    """
    Computes strict semantic & temporal audio-visual grounding (Direction D9+).
    Ensures that mathematical concepts and numbers spoken in narration are verified
    as rendered and animated on screen.
    """

    MATH_TERM_PATTERNS = [
        # Variables & symbols (e.g. w, b, theta, x, y, dx, dt, f(x), e^{i pi})
        (r"\b([a-zA-Z])\b", "variable"),
        (r"\b(theta|omega|alpha|beta|gamma|lambda|sigma|pi|phi|delta)\b", "variable"),
        (r"\b(dx|dy|dt|df|dh)\b", "variable"),
        (r"\b(f\(x\)|g\(x\)|y\s*=\s*f\(x\))\b", "formula"),
        (r"\b(e\^\{?i\s*\\?pi\}?|\be\^\{i\\theta\}|\bw\^T\s*x\s*\+\s*b)\b", "formula"),
        # Numbers & constants
        (r"\b(\d+(?:\.\d+)?)\b", "number"),
        # Key pedagogical STEM concepts
        (r"\b(derivative|integral|limit|tangent|secant|slope|vector|matrix|hyperplane|margin|eigenvalue|eigenvector|gradient|normal)\b", "concept"),
        (r"\b(pythagorean|euler|fourier|taylor|gauss|bayes|newton|schrodinger|laplace)\b", "theorem"),
    ]

    VISUAL_MOBJECT_CLASSES = {
        "MathTex", "Tex", "Text", "Dot", "Line", "Arrow", "Vector", "CurvedArrow",
        "Axes", "NumberPlane", "Circle", "Square", "Rectangle", "Polygon",
        "DashedLine", "SurroundingRectangle", "DoubleArrow", "Brace", "ParametricFunction"
    }

    ACTION_CALLS = {
        "Write", "Create", "Indicate", "Circumscribe", "Wiggle", "Transform",
        "ReplacementTransform", "FadeIn", "GrowFromCenter", "SpinInFromNothing"
    }

    @classmethod
    def extract_spoken_entities(
        cls,
        narration_text: str,
        timeline: Optional[List[Dict[str, Any]]] = None,
        default_duration: float = 60.0
    ) -> List[SpokenEntity]:
        """
        Parses narration utterances and extracts salient pedagogical terms with temporal bounds.
        """
        entities: List[SpokenEntity] = []
        entity_counter = 0

        # Case 1: Structured timeline with beats/cues
        if timeline and len(timeline) > 0:
            accumulated_time = 0.0
            for beat in timeline:
                beat_text = beat.get("narration") or beat.get("say") or beat.get("phrase", "")
                beat_start = float(beat.get("start_sec", beat.get("start", accumulated_time)))
                beat_duration = float(beat.get("duration_sec", beat.get("duration", 5.0)))
                beat_end = beat_start + beat_duration
                accumulated_time = beat_end

                found_terms = cls._scan_text_for_terms(beat_text)
                time_step = beat_duration / max(1, len(found_terms) + 1)

                for idx, (term, cat) in enumerate(found_terms):
                    entity_counter += 1
                    t_start = beat_start + (idx * time_step)
                    t_end = t_start + time_step
                    entities.append(SpokenEntity(
                        entity_id=f"ent_{entity_counter:03d}",
                        term=term,
                        category=cat,
                        start_sec=t_start,
                        end_sec=t_end,
                        phrase=beat_text[:80]
                    ))
            return entities

        # Case 2: Raw plain text without timeline (divide uniformly)
        sentences = [s.strip() for s in re.split(r"[.!?]+", narration_text) if s.strip()]
        total_sents = max(1, len(sentences))
        sent_duration = default_duration / total_sents

        for s_idx, sent in enumerate(sentences):
            sent_start = s_idx * sent_duration
            found_terms = cls._scan_text_for_terms(sent)
            time_step = sent_duration / max(1, len(found_terms) + 1)

            for t_idx, (term, cat) in enumerate(found_terms):
                entity_counter += 1
                t_start = sent_start + (t_idx * time_step)
                entities.append(SpokenEntity(
                    entity_id=f"ent_{entity_counter:03d}",
                    term=term,
                    category=cat,
                    start_sec=t_start,
                    end_sec=t_start + time_step,
                    phrase=sent[:80]
                ))

        return entities

    @classmethod
    def _scan_text_for_terms(cls, text: str) -> List[Tuple[str, str]]:
        found = []
        seen = set()
        for pattern_str, cat in cls.MATH_TERM_PATTERNS:
            for match in re.finditer(pattern_str, text, re.IGNORECASE):
                val = match.group(0).strip()
                # Skip trivial single-character words like 'a', 'I' if not math context
                if cat == "variable" and val.lower() in ("a", "i") and len(val) == 1:
                    continue
                norm = val.lower()
                if norm not in seen:
                    seen.add(norm)
                    found.append((val, cat))
        return found

    @classmethod
    def extract_visual_entities(cls, code: str) -> List[VisualEntity]:
        """
        Extracts visual Mobjects, labels, and animation occurrences from Python code using AST.
        """
        visuals: List[VisualEntity] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Fallback regex extraction if code contains syntax flaws
            return cls._fallback_regex_extract_visuals(code)

        # Map variable name -> (class_name, line_number, raw_label)
        assigned_mobjects: Dict[str, Tuple[str, int, Optional[str]]] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Target variable name
                target_name = None
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        target_name = t.id
                        break

                if not target_name:
                    continue

                # Check if value is a known Mobject constructor
                if isinstance(node.value, ast.Call):
                    func_name = None
                    if isinstance(node.value.func, ast.Name):
                        func_name = node.value.func.id
                    elif isinstance(node.value.func, ast.Attribute):
                        func_name = node.value.func.attr

                    if func_name and func_name in cls.VISUAL_MOBJECT_CLASSES:
                        label = None
                        if node.value.args and isinstance(node.value.args[0], ast.Constant):
                            label = str(node.value.args[0].value)
                        assigned_mobjects[target_name] = (func_name, node.lineno, label)

        # Estimate animation timestamp by sequential self.play / self.wait calls
        current_time = 0.0
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                method_name = None
                if isinstance(call.func, ast.Attribute):
                    method_name = call.func.attr

                if method_name == "wait":
                    wait_dur = 1.0
                    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, (int, float)):
                        wait_dur = float(call.args[0].value)
                    current_time += wait_dur

                elif method_name == "play":
                    # Check animations inside play
                    play_runtime = 1.0
                    # Check run_time keyword
                    for kw in call.keywords:
                        if kw.arg == "run_time" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, (int, float)):
                            play_runtime = float(kw.value.value)

                    for anim_arg in call.args:
                        anim_func = None
                        target_var = None

                        if isinstance(anim_arg, ast.Call):
                            if isinstance(anim_arg.func, ast.Name):
                                anim_func = anim_arg.func.id
                            elif isinstance(anim_arg.func, ast.Attribute):
                                anim_func = anim_arg.func.attr

                            if anim_arg.args:
                                first_arg = anim_arg.args[0]
                                if isinstance(first_arg, ast.Name):
                                    target_var = first_arg.id

                        if target_var and target_var in assigned_mobjects:
                            cls_name, orig_line, label = assigned_mobjects[target_var]
                            visuals.append(VisualEntity(
                                obj_name=target_var,
                                mobject_class=cls_name,
                                source_line=node.lineno,
                                animation_timestamp=current_time,
                                action_type=anim_func or "play",
                                raw_label=label
                            ))
                        elif target_var:
                            visuals.append(VisualEntity(
                                obj_name=target_var,
                                mobject_class="Mobject",
                                source_line=node.lineno,
                                animation_timestamp=current_time,
                                action_type=anim_func or "play",
                                raw_label=None
                            ))

                    current_time += play_runtime

        return visuals

    @classmethod
    def _fallback_regex_extract_visuals(cls, code: str) -> List[VisualEntity]:
        visuals = []
        assign_pat = re.compile(r"(\w+)\s*=\s*(MathTex|Tex|Text|Dot|Line|Arrow|Axes|Circle|Polygon)\((?:['\"](.*?)['\"])?", re.IGNORECASE)
        mobjects = {}
        for line_no, line in enumerate(code.split("\n"), 1):
            m = assign_pat.search(line)
            if m:
                mobjects[m.group(1)] = (m.group(2), line_no, m.group(3))

        play_pat = re.compile(r"self\.play\((Write|Create|Indicate|Circumscribe|Transform|FadeIn)\((\w+)\)", re.IGNORECASE)
        curr_time = 0.0
        for line_no, line in enumerate(code.split("\n"), 1):
            if "self.wait" in line:
                curr_time += 1.0
            pm = play_pat.search(line)
            if pm:
                action, var = pm.group(1), pm.group(2)
                cls_name, orig_line, label = mobjects.get(var, ("Mobject", line_no, None))
                visuals.append(VisualEntity(
                    obj_name=var,
                    mobject_class=cls_name,
                    source_line=line_no,
                    animation_timestamp=curr_time,
                    action_type=action,
                    raw_label=label
                ))
                curr_time += 1.5
        return visuals

    @classmethod
    def compute_grounding_matrix(
        cls,
        topic: str,
        narration_text: str,
        code: str,
        timeline: Optional[List[Dict[str, Any]]] = None,
        temporal_tolerance_sec: float = 4.0
    ) -> GroundingMatrixReport:
        """
        Computes the complete Grounding Matrix between spoken narration and visual animations.
        """
        spoken_entities = cls.extract_spoken_entities(narration_text, timeline=timeline)
        visual_entities = cls.extract_visual_entities(code)

        matches: List[GroundingMatch] = []
        matched_visual_indices: Set[int] = set()

        for spoken in spoken_entities:
            best_match: Optional[VisualEntity] = None
            best_idx: Optional[int] = None
            min_drift = float("inf")
            is_grounded = False
            status = "ungrounded_missing"

            # Search across visual entities for matching symbol or semantic representation
            for v_idx, vis in enumerate(visual_entities):
                term_clean = spoken.term.strip().lower()
                label_clean = (vis.raw_label or "").strip().lower()
                var_clean = vis.obj_name.strip().lower()

                # Semantic or textual match
                var_tokens = set(re.split(r"[_\s]+", var_clean))
                label_tokens = set(re.split(r"[^a-zA-Z0-9]+", label_clean)) if label_clean else set()

                text_match = False
                if label_clean and (term_clean in label_tokens or term_clean == label_clean):
                    text_match = True
                elif term_clean == var_clean or term_clean in var_tokens:
                    text_match = True
                elif len(term_clean) > 2 and ((label_clean and term_clean in label_clean) or term_clean in var_clean):
                    text_match = True
                elif spoken.category == "concept" and len(term_clean) > 3 and term_clean in vis.mobject_class.lower():
                    text_match = True

                if text_match:
                    drift = abs(vis.animation_timestamp - spoken.start_sec)
                    if drift < min_drift:
                        min_drift = drift
                        best_match = vis
                        best_idx = v_idx

            if best_match is not None:
                if best_idx is not None:
                    matched_visual_indices.add(best_idx)
                if min_drift <= temporal_tolerance_sec:
                    is_grounded = True
                    status = "grounded_exact" if min_drift <= 1.5 else "grounded_semantic"
                else:
                    # Semantic match found but displaced in time
                    is_grounded = False
                    status = "temporal_drift"
            else:
                min_drift = 999.0

            matches.append(GroundingMatch(
                spoken_entity=spoken,
                visual_entity=best_match,
                time_delta_sec=min_drift if best_match else 0.0,
                is_grounded=is_grounded,
                status=status
            ))

        # Collect ungrounded items and orphan visuals
        ungrounded = [m.spoken_entity.to_dict() for m in matches if not m.is_grounded]
        orphan_visuals = [
            v.to_dict() for idx, v in enumerate(visual_entities)
            if idx not in matched_visual_indices
        ]

        total_spoken = len(spoken_entities)
        grounded_count = sum(1 for m in matches if m.is_grounded)
        ungrounded_count = total_spoken - grounded_count

        grounding_ratio = (grounded_count / total_spoken) if total_spoken > 0 else 1.0
        grounding_score = min(100.0, grounding_ratio * 100.0)

        # Mayer contiguity score penalized by temporal drift
        aligned_drifts = [m.time_delta_sec for m in matches if m.is_grounded]
        avg_drift = sum(aligned_drifts) / max(1, len(aligned_drifts))
        contiguity_score = max(0.0, 100.0 - (avg_drift * 12.0)) if aligned_drifts else 50.0

        passed = (grounding_ratio >= 0.70 and contiguity_score >= 60.0)

        return GroundingMatrixReport(
            topic=topic,
            total_spoken_entities=total_spoken,
            grounded_count=grounded_count,
            ungrounded_count=ungrounded_count,
            grounding_ratio=grounding_ratio,
            grounding_score=grounding_score,
            mayer_contiguity_score=contiguity_score,
            passed=passed,
            matches=matches,
            ungrounded_entities=ungrounded,
            orphan_visuals=orphan_visuals
        )
