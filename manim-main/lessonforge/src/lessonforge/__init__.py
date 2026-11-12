"""lessonforge — narrated STEM lesson videos with Manim.

Two production paths over one toolchain:

* ``lessonforge.engine`` — brief/source → storyboard IR → deterministic transpiler →
  Manim render → layout probe → accept-if-better repair (FastAPI server + Studio UI).
* ``lessonforge.longform`` — a reviewed lesson script → speech first → measured
  timeline → chapter renders → captions, chapter markers and media checks.

``lessonforge.bridge`` joins them: any lesson contract can be rendered through the
engine's transpiler without hand-written scene code.

Importing this top-level package is deliberately side-effect free (no manim, no
server, no workspace creation) so contract/schema tooling stays cheap.
"""

__version__ = "0.1.0"
