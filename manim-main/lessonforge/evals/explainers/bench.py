"""Concept-explainer story benchmark.

1. Band: where good YouTube explainers fall on each story measure (practice channels only).
2. Scramble test (held-out channels only): break a real explainer's story in known places and check each measure
   (and the jump finder) notices. A measure that cannot tell a scrambled explainer from the real one is not used.
3. Our lessons: each measure against the band, and the sentences that jump.
"""
import json, sys, random, hashlib, statistics as st
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src")); from lessonforge.harness import storyflow as sf

CORPUS, OURS, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
HELD_SHARE = 0.3
def held_out(channel: str) -> bool:
    return int(hashlib.sha1(channel.lower().encode()).hexdigest(), 16) % 100 < HELD_SHARE * 100

from sentence_transformers import SentenceTransformer
_m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
_cache = {}
def embed(texts):
    import numpy as np
    miss = [t for t in texts if t not in _cache]
    if miss:
        for t, v in zip(miss, _m.encode(miss, batch_size=64, show_progress_bar=False)): _cache[t] = v
    return np.array([_cache[t] for t in texts])

videos = []
for f in sorted((CORPUS / "videos").glob("*.json")):
    d = json.loads(f.read_text()); s = sf.sentences_from_cues(d["cues"])
    if len(s) < 25 or sum(len(x["text"].split()) for x in s) < 400: continue
    d["sents"] = s; d["held"] = held_out(d["channel"]); videos.append(d)
print(len(videos), "videos;", sum(v["held"] for v in videos), "held out;", len({v["channel"] for v in videos}), "channels")

KEYS = {"jump_rate": -1, "tie_rate": 1, "adjacent_similarity": 1, "weak_seam_rate": -1, "neighbour_gain": 1,
        "new_terms_per_100w": 0, "max_new_terms_3_sentences": 0, "spine_cover": 1, "questions_per_100w": 0, "mean_sentence_words": 0,
        "short_sentence_share": 0, "cause_per_100w": 0, "contrast_per_100w": 0, "sequence_per_100w": 0, "example_per_100w": 0,
        "recap_per_100w": 0, "numbers_per_100w": 0, "you_we_per_100w": 0, "wpm": 0}
rows = []
for v in videos:
    m = sf.measure(v["sents"], v.get("duration"), embed); v["m"] = m
    rows.append({"id": v["id"], "channel": v["channel"], "topic": v.get("topic"), "title": v["title"], "held": v["held"], "set": v.get("set", "youtube"), **{k: m.get(k) for k in KEYS}})
(OUT / "corpus_scores.json").write_text(json.dumps(rows, indent=1))

def q(xs, p):
    xs = sorted(x for x in xs if x is not None); return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None
practice = [r for r in rows if not r["held"]]
band = {k: {"p10": q([r[k] for r in practice], .1), "p50": q([r[k] for r in practice], .5), "p90": q([r[k] for r in practice], .9)} for k in KEYS}
school = [r for r in rows if r["set"].startswith("khan-middle")]
band_school = {k: {"p10": q([r[k] for r in school], .1), "p50": q([r[k] for r in school], .5), "p90": q([r[k] for r in school], .9)} for k in KEYS}
(OUT / "band.json").write_text(json.dumps({"practice_channels": band, "khan_middle_school": band_school}, indent=1))

# ── scramble test ──
rng = random.Random(7)
def perturb(sents, kind, donor):
    s = [dict(x) for x in sents]; n = len(s); seams = set()
    if kind == "swap_blocks":
        a = rng.randrange(2, n // 2 - 6); b = rng.randrange(n // 2, n - 6)
        s = s[:a] + s[b:b + 6] + s[a + 6:b] + s[a:a + 6] + s[b + 6:]
        seams = {a, a + 6, b, b + 6}
    elif kind == "skip_steps":       # leave out every other sentence in a stretch: the steps between ideas go missing
        a = rng.randrange(2, n // 2); keep = [i for i in range(n) if not (a <= i < a + 16 and (i - a) % 2 == 1)]
        s2 = [s[i] for i in keep]; seams = {j for j, i in enumerate(keep) if a < i < a + 17}; s = s2
    elif kind == "intrude":
        spots = sorted(rng.sample(range(3, n - 1), 4))
        for k, at in enumerate(spots):
            s[at] = dict(rng.choice(donor)); seams |= {at, at + 1}
    elif kind == "shuffle":
        rng.shuffle(s); seams = set(range(1, n))
    for i, x in enumerate(s): x["start"] = float(i)
    return s, seams

result = {"kinds": {}, "finder": {}}
held = [v for v in videos if v["held"]]
for kind in ("skip_steps", "swap_blocks", "intrude", "shuffle"):
    wins = {k: [] for k, d in KEYS.items() if d}; tp = fn = fp = tn = 0
    for v in held:
        donor = rng.choice([w for w in videos if w.get("topic") != v.get("topic")])["sents"]
        s2, seams = perturb(v["sents"], kind, donor)
        m2 = sf.measure(s2, None, embed)
        for k in wins:
            a, b = v["m"].get(k), m2.get(k)
            if a is None or b is None: continue
            wins[k].append(1.0 if (a - b) * KEYS[k] > 0 else 0.5 if a == b else 0.0)
        flagged = set(sf.rule_jumps(s2))
        base_flag = {j["i"] for j in v["m"]["jumps"]}
        tp += len(flagged & seams); fn += len(seams - flagged)
        if kind != "shuffle":
            others = set(range(1, len(s2))) - seams; fp += len(flagged & others); tn += len(others - flagged)
    result["kinds"][kind] = {k: round(st.mean(x), 3) for k, x in wins.items() if x}
    result["finder"][kind] = {"seams_found": round(tp / max(1, tp + fn), 3), "false_flags_elsewhere": round(fp / max(1, fp + tn), 3) if kind != "shuffle" else None}
result["held_out_videos"] = len(held)
# ── jump finder: learn "is this sentence a broken seam?" on practice channels, test on held-out channels ──
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
def seam_set(vs, kinds=("skip_steps", "swap_blocks", "intrude")):
    X, y = [], []
    for v in vs:
        for kind in kinds:
            donor = rng.choice([w for w in videos if w.get("topic") != v.get("topic") or not v.get("topic")])["sents"]
            s2, seams = perturb(v["sents"], kind, donor)
            for i, f in enumerate(sf.seam_features(s2, embed), 1):
                X.append(f); y.append(1 if i in seams else 0)
    return X, y
Xp, yp = seam_set([v for v in videos if not v["held"]]); Xh, yh = seam_set(held)
clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(Xp, yp)
ph = clf.predict_proba(Xh)[:, 1]
# threshold: flag at most 5% of the sentences of REAL practice explainers
import numpy as np
real = np.array([f for v in videos if not v["held"] for f in sf.seam_features(v["sents"], embed)])
thr = float(np.quantile(clf.predict_proba(real)[:, 1], 0.95))
realh = np.array([f for v in held for f in sf.seam_features(v["sents"], embed)])
result["jump_finder"] = {
    "auc_held_out_learned": round(roc_auc_score(yh, ph), 3),
    "auc_held_out_words_only": round(roc_auc_score(yh, [-(x[1] + 2 * x[2]) for x in Xh]), 3),
    "auc_held_out_meaning_only": round(roc_auc_score(yh, [-x[6] for x in Xh]), 3),
    "threshold": round(thr, 3),
    "seams_found_held_out": round(float(np.mean(ph[np.array(yh) == 1] >= thr)), 3),
    "flags_on_real_held_out_explainers": round(float(np.mean(clf.predict_proba(realh)[:, 1] >= thr)), 3),
    "weights": [round(float(w), 3) for w in clf.coef_[0]], "bias": round(float(clf.intercept_[0]), 3),
    "features": ["shared words with previous", "shared words with previous two", "opens with a link word", "is a question",
                 "length", "meaning closeness to previous", "closeness to previous two (max)", "closeness to next"]}
for kind in ("skip_steps", "swap_blocks", "intrude"):
    Xk, yk = seam_set(held, (kind,)); pk = clf.predict_proba(Xk)[:, 1]
    result["jump_finder"][f"auc_{kind}"] = round(roc_auc_score(yk, pk), 3)
    result["jump_finder"][f"found_at_threshold_{kind}"] = round(float(np.mean(pk[np.array(yk) == 1] >= thr)), 3)
realrule = [len(sf.rule_jumps(v["sents"])) / max(1, len(v["sents"]) - 1) for v in held]
result["rule_finder_flags_on_real_held_out"] = round(float(np.mean(realrule)), 3)
(OUT / "scramble_test.json").write_text(json.dumps(result, indent=1))
import pickle; pickle.dump({"clf": clf, "thr": thr}, open(OUT / "jump_finder.pkl", "wb"))
(OUT / "scramble_test.json").write_text(json.dumps(result, indent=1))
print(json.dumps(result, indent=1))

# ── our lessons ──
ours = []
for f in sorted(OURS.glob("*.json")):
    d = json.loads(f.read_text()); s = sf.sentences_from_cues(d["cues"]); m = sf.measure(s, d.get("duration"), embed)
    fs = sf.seam_features(s, embed); pr = clf.predict_proba(fs)[:, 1] if fs else []
    flagged = [{"at": round(s[i]["start"], 1), "p": round(float(p), 2), "before": s[i - 1]["text"][:140], "text": s[i]["text"][:160]}
               for i, p in enumerate(pr, 1) if p >= thr]
    rj = sf.rule_jumps(s)
    ours.append({"id": d["id"], **{k: m.get(k) for k in KEYS}, "rule_jumps": [{"at": round(s[i]["start"], 1), "before": s[i-1]["text"][:140], "text": s[i]["text"][:160]} for i in rj],
                 "rule_jump_share": round(len(rj) / max(1, len(s) - 1), 3), "flagged_share": round(len(flagged) / max(1, len(s) - 1), 3),
                 "flagged": flagged, "spine": m["spine"]})
(OUT / "ours_scores.json").write_text(json.dumps(ours, indent=1))
print("ours flagged share:", [(r["id"], r["flagged_share"]) for r in ours])
print("\nmetric                      practice p10/p50/p90     khan-school p50   ours median")
for k in KEYS:
    b = band[k]; o = [r[k] for r in ours if r[k] is not None]
    print(f"{k:28s} {str(b['p10']):>7} {str(b['p50']):>7} {str(b['p90']):>7}   {str(band_school[k]['p50']):>8}   {str(round(st.median(o),3)) if o else '-':>8}")
