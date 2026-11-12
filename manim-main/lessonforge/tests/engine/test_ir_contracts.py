"""Contract harness for the formal IR schemas (reference-architecture Appendix A).

No manim, no API keys, no network, no app-package import (engine/schemas.py is loaded
standalone so the bootstrap self-heal never runs).

What it pins:
  A. Drift gate — schemas/storyboard-ir.schema.json must match the live Pydantic
     export byte-for-byte (normalized). A schema change must be a *decision*:
     edit engine/schemas.py, then re-run with --regen and commit both files together.
  B. Golden storyboard fixture — a full board exercising every positioning strategy,
     structured animation events and math_evolution must validate and round-trip.
  C. Degenerate boards — wrong type literals / missing required fields must be
     rejected by the models (the typed layer under storyboard_shape_problems, which
     has its own harness in test_storyboard_gate.py).
  D. Sidecar contract — the exact shapes written by app/render.py's three
     _write_video_sidecar call sites must satisfy render-verification-ir.schema.json,
     and broken shapes must not (validator is hand-rolled: no jsonschema dep).

Usage:
  .venv/bin/python stem_animation_lab/test_ir_contracts.py
  .venv/bin/python stem_animation_lab/test_ir_contracts.py --regen   # after an
      intentional model change: rewrites schemas/storyboard-ir.schema.json
"""
import importlib.util
import json
import os
import sys

LAB = os.path.dirname(os.path.abspath(__import__("lessonforge").__file__))  # the installed package dir
SCHEMA_DIR = os.path.join(LAB, "schemas")
STORYBOARD_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "storyboard-ir.schema.json")
SIDECAR_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "render-verification-ir.schema.json")


def _load_schemas_module():
    """Load engine/schemas.py WITHOUT importing the app package (no bootstrap)."""
    spec = importlib.util.spec_from_file_location(
        "ir_contract_schemas", os.path.join(LAB, "engine", "schemas.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _live_storyboard_schema(mod):
    schema = mod.StoryboardResponse.model_json_schema()
    # Stamp the published contract's identity on the export.
    schema["$id"] = "gyansetu:storyboard-ir"
    schema["title"] = "Storyboard IR — the canonical Scene DSL"
    return schema


def _normalized(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


GOLDEN_BOARD = {
    "topic": "Distance between two points",
    "key_theorems": ["d = sqrt((x2-x1)^2 + (y2-y1)^2)"],
    "key_terms": ["Distance Formula", "Hypotenuse", "Coordinate Plane"],
    "style_profile": "3blue1brown/minimalist/neon",
    "aspect_ratio": "widescreen",
    "visual_storyboard": [
        {
            "scene_index": 1,
            "description": "Plot two points on a coordinate plane and reveal the distance formula.",
            "layout_template": "TitleStageCaption",
            "elements": [
                {
                    "id": "title", "type": "text", "content": "Distance Between Two Points",
                    "entrance_animation": "FadeIn", "exit_animation": "FadeOut",
                    "safe_zone_alignment": "TOP_CENTER",
                },
                {
                    "id": "plane", "type": "coordinate_system",
                    "content": "coordinate plane x:-5-5, y:-4-4",
                    "entrance_animation": "Create", "exit_animation": "FadeOut",
                    "absolute_position": [0.0, -0.5],
                },
                {
                    "id": "point_a", "type": "shape", "content": "point A",
                    "color": "#00FFCC",
                    "entrance_animation": "GrowFromCenter", "exit_animation": "FadeOut",
                    "absolute_position": [-3.0, 2.0],
                },
                {
                    "id": "label_a", "type": "text", "content": "A(-3, 2)",
                    "entrance_animation": "FadeIn", "exit_animation": "FadeOut",
                    "relative_positioning": {
                        "relative_to": "point_a", "direction": "UP_LEFT", "buffer": 0.3,
                    },
                },
                {
                    "id": "formula", "type": "math_evolution",
                    "content": "d^2 = a^2 + b^2 → d = \\sqrt{a^2 + b^2}",
                    "entrance_animation": "Write", "exit_animation": "FadeOut",
                    "safe_zone_alignment": "BOTTOM_CENTER",
                },
            ],
            "narration_cues": [
                {
                    "cue": "Chalo dekhte hain do points ke beech ki doori. [PAUSE: 300]",
                    "animation_events": [
                        {"action": "show", "target": "title"},
                        {"action": "show", "target": "plane"},
                    ],
                },
                {
                    "cue": "Point A yahan hai, coordinates minus teen aur do.",
                    "animation_events": [
                        {"action": "show", "target": "point_a"},
                        {"action": "show", "target": "label_a"},
                        {"action": "highlight", "target": "point_a", "color": "YELLOW"},
                    ],
                },
                {
                    "cue": "Pythagoras se hi distance formula milta hai.",
                    "event": "FadeOut(title)",
                    "animation_events": [
                        {"action": "show", "target": "formula"},
                        {"action": "hide", "target": "title"},
                    ],
                },
            ],
            "wait_time": 1.5,
        },
    ],
}


# The three _write_video_sidecar call-site shapes (app/render.py) + a real
# historical sidecar (static/videos/STEMAnimation_2f638ed2.mp4.json).
SIDECAR_PARALLEL = {"job_id": "j1", "repair_rounds": 1, "violations_remaining": 0,
                    "animation_beats": 12, "scenes_repaired": 1, "vision_findings": 0}
SIDECAR_SEQUENTIAL = {"job_id": "j2", "repair_rounds": 0, "violations_remaining": 2,
                      "animation_beats": 8, "vision_findings": 1, "voice_degraded": 3}
SIDECAR_HISTORICAL = {"job_id": "audit_run", "repair_rounds": 2,
                      "violations_remaining": 11, "animation_beats": 17}


def _validate_against(schema, doc):
    """Minimal validator for the subset our schemas use: type / required /
    minimum / minLength on a flat object. Returns list of error strings."""
    errors = []
    if not isinstance(doc, dict):
        return ["document is not an object"]
    for req in schema.get("required", []):
        if req not in doc:
            errors.append(f"missing required field: {req}")
    type_map = {"integer": int, "number": (int, float), "string": str,
                "boolean": bool, "object": dict, "array": list}
    for key, rules in schema.get("properties", {}).items():
        if key not in doc:
            continue
        val = doc[key]
        expected = rules.get("type")
        if expected in type_map:
            py = type_map[expected]
            ok = isinstance(val, py) and not (expected in ("integer", "number")
                                              and isinstance(val, bool))
            if not ok:
                errors.append(f"{key}: expected {expected}, got {type(val).__name__}")
                continue
        if "minimum" in rules and isinstance(val, (int, float)) and val < rules["minimum"]:
            errors.append(f"{key}: {val} below minimum {rules['minimum']}")
        if "minLength" in rules and isinstance(val, str) and len(val) < rules["minLength"]:
            errors.append(f"{key}: shorter than minLength {rules['minLength']}")
    return errors


def main():
    mod = _load_schemas_module()
    live = _live_storyboard_schema(mod)

    if "--regen" in sys.argv:
        os.makedirs(SCHEMA_DIR, exist_ok=True)
        with open(STORYBOARD_SCHEMA_PATH, "w", encoding="utf-8") as f:
            json.dump(live, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        print(f"regenerated {os.path.relpath(STORYBOARD_SCHEMA_PATH, LAB)} "
              f"from engine/schemas.py — commit it with the model change")
        return 0

    passed, failed = 0, 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"[{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))

    # A. Drift gate ----------------------------------------------------------
    exists = os.path.exists(STORYBOARD_SCHEMA_PATH)
    check("A1 storyboard-ir.schema.json is committed", exists)
    if exists:
        with open(STORYBOARD_SCHEMA_PATH, encoding="utf-8") as f:
            committed = json.load(f)
        check("A2 committed schema matches live Pydantic export (no drift)",
              _normalized(committed) == _normalized(live),
              "engine/schemas.py changed — rerun with --regen and commit both files")
    else:
        check("A2 committed schema matches live Pydantic export (no drift)", False,
              "run --regen first")
    check("A3 schema requires topic + visual_storyboard",
          {"topic", "visual_storyboard"} <= set(live.get("required", [])))

    # B. Golden fixture ------------------------------------------------------
    try:
        board = mod.StoryboardResponse.model_validate(GOLDEN_BOARD)
        check("B1 golden storyboard validates through the models", True)
    except Exception as e:
        board = None
        check("B1 golden storyboard validates through the models", False, str(e)[:200])
    if board is not None:
        dumped = board.model_dump()
        scene = dumped["visual_storyboard"][0]
        check("B2 round-trip preserves scenes, element ids and cue count",
              len(dumped["visual_storyboard"]) == 1
              and [e["id"] for e in scene["elements"]]
              == ["title", "plane", "point_a", "label_a", "formula"]
              and len(scene["narration_cues"]) == 3)
        check("B3 defaults materialize (scale 0.7, relative buffer kept, aspect widescreen)",
              scene["elements"][0]["scale"] == 0.7
              and scene["elements"][3]["relative_positioning"]["buffer"] == 0.3
              and dumped["aspect_ratio"] == "widescreen")

    # C. Degenerate boards rejected by the typed layer -----------------------
    def rejects(mutate):
        import copy
        bad = copy.deepcopy(GOLDEN_BOARD)
        mutate(bad)
        try:
            mod.StoryboardResponse.model_validate(bad)
            return False
        except Exception:
            return True

    check("C1 unknown element type literal is rejected",
          rejects(lambda b: b["visual_storyboard"][0]["elements"][0]
                  .__setitem__("type", "hologram")))
    check("C2 scene without narration_cues is rejected",
          rejects(lambda b: b["visual_storyboard"][0].pop("narration_cues")))
    check("C3 unknown animation event action is rejected",
          rejects(lambda b: b["visual_storyboard"][0]["narration_cues"][1]
                  ["animation_events"][2].__setitem__("action", "explode")))
    check("C4 relative_positioning without relative_to is rejected",
          rejects(lambda b: b["visual_storyboard"][0]["elements"][3]
                  ["relative_positioning"].pop("relative_to")))

    # D. Sidecar contract ----------------------------------------------------
    with open(SIDECAR_SCHEMA_PATH, encoding="utf-8") as f:
        sidecar_schema = json.load(f)
    check("D1 sidecar schema requires exactly the durable core",
          set(sidecar_schema.get("required", []))
          == {"job_id", "repair_rounds", "violations_remaining"})
    check("D2 parallel-path sidecar shape passes",
          _validate_against(sidecar_schema, SIDECAR_PARALLEL) == [])
    check("D3 sequential + historical sidecar shapes pass",
          _validate_against(sidecar_schema, SIDECAR_SEQUENTIAL) == []
          and _validate_against(sidecar_schema, SIDECAR_HISTORICAL) == [])
    check("D4 sidecar missing violations_remaining fails",
          _validate_against(sidecar_schema,
                            {"job_id": "x", "repair_rounds": 0}) != [])
    check("D5 string repair_rounds fails",
          _validate_against(sidecar_schema,
                            {"job_id": "x", "repair_rounds": "2",
                             "violations_remaining": 0}) != [])
    check("D6 negative violations_remaining fails",
          _validate_against(sidecar_schema,
                            {"job_id": "x", "repair_rounds": 0,
                             "violations_remaining": -1}) != [])
    check("D7 string vision_findings fails (typed as integer)",
          _validate_against(sidecar_schema,
                            {"job_id": "x", "repair_rounds": 0,
                             "violations_remaining": 0,
                             "vision_findings": "2"}) != [])

    # E. Provider-layer completeness gate (P8: a non-`stop` finish is partial content)
    import types
    llm_path = os.path.join(LAB, "engine", "llm.py")
    with open(llm_path, encoding="utf-8") as f:
        llm_src = f.read()
    check("E1 finish_reason=length is rejected at the provider",
          'if finish == "length":' in llm_src)
    check("E2 finish_reason=error/content_filter are rejected too "
          "(measured 2026-07-21: an accepted finish=error board reached the shape gate)",
          'if finish in ("error", "content_filter"):' in llm_src)
    check("E3 storyboard task is exempt from the request-level token ceiling "
          "(uncapped by default 2026-07-31 — the ceiling was also a video-length "
          "ceiling; restore with LLM_MAX_TOKENS_STORYBOARD)",
          "def _max_tokens_for_task" in llm_src
          and 'if task == "storyboard":' in llm_src
          and "LLM_MAX_TOKENS_STORYBOARD" in llm_src
          and "if max_tokens:" in llm_src)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
