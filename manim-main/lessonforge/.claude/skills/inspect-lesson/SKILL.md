---
name: inspect-lesson
description: Look inside an existing lesson (by job id) stage by stage and say what is wrong with it and where in the code each fault comes from. Spends nothing and changes nothing. Use for "why is this video bad", "review lesson X", or before deciding what to fix.
argument-hint: "<job id>  [more job ids…]"
---

# Inspect a lesson: what is wrong, and where it comes from

Lessons: $ARGUMENTS

Nothing here calls a paid model, renders, or edits code.

1. For each job id:
   `python scripts/agent/dossier.py <job id>` (writes `<lesson>/dossier/`). A job id is looked up in the
   improver's own workspace first, then in the app's list (`$IMPROVER_LIVE_HOME/lessons`).
2. In one message, start in parallel: `frame-reviewer` on each dossier folder, and `stage-auditor`
   twice per lesson (stage groups **words** and **picture and sync**).
3. With more than one lesson, or when a finding looks general, run
   `python scripts/agent/survey.py --last 30 --grep "<word from the symptom>"` to see how many lessons
   share it.
4. Write `<lesson>/dossier/INSPECTION.md`, in plain short sentences for the owner:
   - the frame score (mean, beats scoring 0 or 1) and the three worst moments with their times;
   - each fault, worst first: what a learner sees or hears → which stage causes it → the file and
     function → how many recent lessons share it → the one change you would make;
   - what you would fix first, and whether it needs the owner's decision.
5. Print the path of `INSPECTION.md` and its summary. Do not start fixing: that is `/make-best-video`.
