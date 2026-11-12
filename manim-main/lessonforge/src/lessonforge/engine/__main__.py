"""Entry point: ``python -m lessonforge.engine`` (also ``lessonforge serve``).

Also launchable as ``uvicorn lessonforge.engine:app --port 5000``.
"""
import os

from . import app, sweep_old_artifacts  # noqa: F401  (app used by uvicorn target string)

if __name__ == "__main__":
    import uvicorn

    # Clear out render scratch/output left over from previous sessions.
    # SWEEP_MAX_AGE_HOURS controls how much video history the /timeline page keeps
    # (default 24h; raise it to keep more of the render progression).
    sweep_old_artifacts(float(os.getenv("SWEEP_MAX_AGE_HOURS", "24")))
    # Localhost by default ON PURPOSE: /api/compile_video executes Python posted by
    # the client, so binding to 0.0.0.0 publishes remote code execution to whoever
    # can reach the port. Set LAB_HOST=0.0.0.0 only behind authentication, or on a
    # network where you trust every host that can route to you.
    uvicorn.run("lessonforge.engine:app", host=os.getenv("LAB_HOST", "127.0.0.1"),
                port=int(os.getenv("LAB_PORT", "5000")), reload=False)
