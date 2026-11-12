"""The prompts every lesson is written with are pinned byte for byte.

The subject-kit work (``lessonforge.kits``) promises that nothing a kit adds changes these four texts: a kit's rules
travel in a per-lesson addendum, never inside them. A changed hash here means a prompt changed on purpose or by
accident; either way the prompt cache prefix changed too, so update the hash only with the change in view.
"""
import hashlib

from lessonforge.harness import improver, pack, writer

PINNED = {
    "writer.FIGURE_RULES": "10c0c7fffc2c474dc3b29860fd09e8b967ccc114804a3389d34807f6d8c99b57",
    "writer.SYSTEM": "62b2eea570b542407e5304075eb729e38d6868eb47422874c124cc4c22b675a2",
    "pack.SYSTEM": "836fa0e1bdd3eb601c7b2e2a1a0def664a163c283819a1d0348d9dd64f433a62",
    "improver._system()": "8474696996a0c416757a172350d3f19895d67a315185158e3b61c22a15aa01cc",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _texts() -> dict[str, str]:
    return {"writer.FIGURE_RULES": writer.FIGURE_RULES, "writer.SYSTEM": writer.SYSTEM, "pack.SYSTEM": pack.SYSTEM,
            "improver._system()": improver._system()}


def test_the_four_prompts_are_byte_for_byte_what_they_were():
    found = {name: _sha(text) for name, text in _texts().items()}
    assert found == PINNED


def test_the_figure_rules_are_inside_the_writer_system_prompt():
    assert writer.FIGURE_RULES in writer.SYSTEM
