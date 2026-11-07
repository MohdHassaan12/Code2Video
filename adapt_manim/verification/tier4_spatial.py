"""
Tier 4: Discrete Spatial Layout & Occupancy Table Verification.
Analyzes 6x6 grid anchor assignments, detects element collisions, area overlaps,
and visual imbalance (Code2Video Section 4.3).
Compute Cost: ~2ms, 0 tokens.
"""

import re
from typing import List, Tuple, Dict, Set, Any
from adapt_manim.core.types import (
    VerificationTier, VerificationIssue, IssueSeverity,
    OccupancyTable, OccupancyRecord
)
from adapt_manim.core.base_scene import BaseSceneHelper


class Tier4SpatialVerifier:
    """Verifies discrete 6x6 anchor placement and generates occupancy reports."""

    @classmethod
    def verify(cls, code: str) -> Tuple[List[VerificationIssue], OccupancyTable]:
        issues: List[VerificationIssue] = []
        records: List[OccupancyRecord] = []
        occupied_points: Set[str] = set()
        point_to_records: Dict[str, List[OccupancyRecord]] = {}

        lines = code.split("\n")

        # 1. Parse place_at_grid calls: self.place_at_grid(obj, 'B2')
        pattern_point = re.compile(r"self\.place_at_grid\(\s*([a-zA-Z0-9_]+)\s*,\s*['\"]([A-F][1-6])['\"](?:\s*,\s*scale_factor=([0-9.]+))?", re.IGNORECASE)
        for idx, line in enumerate(lines):
            match = pattern_point.search(line)
            if match:
                obj_name = match.group(1)
                anchor = match.group(2).upper()
                scale = float(match.group(3)) if match.group(3) else 1.0

                rec = OccupancyRecord(
                    object_name=obj_name,
                    anchor=anchor,
                    points_covered=[anchor],
                    scale_factor=scale,
                    code_line=idx + 1
                )
                records.append(rec)
                point_to_records.setdefault(anchor, []).append(rec)
                occupied_points.add(anchor)

        # 2. Parse place_in_area calls: self.place_in_area(obj, 'A1', 'C3')
        pattern_area = re.compile(r"self\.place_in_area\(\s*([a-zA-Z0-9_]+)\s*,\s*['\"]([A-F][1-6])['\"]\s*,\s*['\"]([A-F][1-6])['\"](?:\s*,\s*scale_factor=([0-9.]+))?", re.IGNORECASE)
        for idx, line in enumerate(lines):
            match = pattern_area.search(line)
            if match:
                obj_name = match.group(1)
                tl = match.group(2).upper()
                br = match.group(3).upper()
                scale = float(match.group(4)) if match.group(4) else 1.0

                try:
                    covered = BaseSceneHelper.get_area_points(tl, br)
                except ValueError:
                    covered = [tl, br]

                rec = OccupancyRecord(
                    object_name=obj_name,
                    anchor=f"{tl}:{br}",
                    points_covered=covered,
                    scale_factor=scale,
                    code_line=idx + 1
                )
                records.append(rec)
                for pt in covered:
                    point_to_records.setdefault(pt, []).append(rec)
                    occupied_points.add(pt)

        # 3. Detect Collisions (multiple point objects sharing same anchor)
        collisions: List[Dict[str, Any]] = []
        all_anchors = BaseSceneHelper.get_all_anchor_names()
        vacant = [a for a in all_anchors if a not in occupied_points]

        for pt, pt_recs in point_to_records.items():
            if len(pt_recs) > 1:
                # Check if they are distinct objects
                names = [r.object_name for r in pt_recs]
                if len(set(names)) > 1:
                    conflicting_obj = pt_recs[-1].object_name
                    line_num = pt_recs[-1].code_line
                    # Find nearest vacant anchor
                    vacant_anchor = BaseSceneHelper.find_nearest_vacant_anchor(pt, list(occupied_points)) or "C4"

                    issues.append(VerificationIssue(
                        tier=VerificationTier.TIER4_SPATIAL,
                        severity=IssueSeverity.WARNING,
                        message=f"Visual overlap collision at anchor {pt} between {names}. Relocate '{conflicting_obj}' to nearest vacant anchor {vacant_anchor}.",
                        line_number=line_num,
                        offending_code=lines[line_num - 1] if 0 <= line_num - 1 < len(lines) else "",
                        suggested_scope="autogrid",
                        suggested_fix=f"Relocate '{conflicting_obj}' to '{vacant_anchor}'"
                    ))
                    collisions.append({
                        "anchor": pt,
                        "objects": names,
                        "suggested_relocation": vacant_anchor
                    })

        # 4. Check for canvas utilization
        if len(records) > 0 and len(occupied_points) == 1:
            issues.append(VerificationIssue(
                tier=VerificationTier.TIER4_SPATIAL,
                severity=IssueSeverity.INFO,
                message="Visual imbalance: Animation elements are confined to a single anchor. Consider distributing across adjacent anchors.",
                suggested_scope="block",
                suggested_fix="Expand elements across complementary grid anchors."
            ))

        table = OccupancyTable(
            records=records,
            collisions=collisions,
            vacant_points=vacant
        )

        return (issues, table)
