"""The content harness: topic → Socratic intake → teaching framework → script → video.

    intake.py       the questions (who is it for, what should they be able to do, how
                    should it sound, which language, how long) and the brief they fill
    frameworks.py   three ways of explaining the same idea, by level of learner
    writer.py       brief + framework → a lesson contract (model-written, code-checked;
                    a deterministic outline when no model is configured)
    scripted.py     the other way in: a script the requester wrote → the same contract
                    (their words spoken as written; a model designs only the screen)
    service.py      sessions and generation jobs (script → speech → render → checks)
    api.py          FastAPI routes under /api/harness, mounted on the engine server

Everything the harness produces is a ``lessonforge.longform`` lesson, so a generated
lesson is narrated first and rendered against measured audio like a hand-made one.
"""
