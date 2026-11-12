# 05 — Personalisation by level, age-appropriate understandability, in-video interactivity, colour palette

Research notes for the lessonforge pipeline (narrated Manim lessons, classes 6–12, English/Hindi/Hinglish). Date: 2026-10-08. Claims marked **[uncertain]** were not verified against the primary source or are my synthesis rather than a published finding. Contrast numbers in Q4 were computed locally (script in the session scratchpad: WCAG 2.x ratio; APCA Lc with the 0.0.98G-4g constants; CVD separation via Machado et al. 2009 matrices, CIE76 ΔE).

---

## Q1 — What adaptive-learning / LLM-tutor systems actually vary by level, and the evidence

| Approach | Source | What it says concretely | Evidence | How to adopt |
|---|---|---|---|---|
| LearnLM pedagogy rubric | [arXiv 2412.16429](https://arxiv.org/abs/2412.16429) | Trained/evaluated on rubric items: **Leveling** (match proficiency), **Unstuck**, **Manageable chunks**, **Appropriate response length**, **Asks questions / Guides to answer**, **Guide mistake discovery**, **Stimulates interest**. Adaptation comes from learner personas + stated grade/proficiency + prior-knowledge activation. Vocabulary/sentence complexity is *not* a rubric item. | Expert-rater preference only: +31% vs GPT-4o, +11% vs Claude 3.5 Sonnet, +13% vs Gemini 1.5 Pro. Authors say learning-outcome evidence is missing. | Put persona + grade + prior-knowledge into the script prompt; score drafts with a rubric using the same names. |
| Khanmigo | [NBER w35620](https://www.nber.org/papers/w35620); [EdWorkingPaper](https://edworkingpapers.com/sites/default/files/ai26-1551.pdf); [KQED](https://www.kqed.org/mindshift/66662/students-didnt-get-answers-from-khanmigo-they-didnt-want-its-questions-either) | Socratic chat tutor on top of Khan practice. | Two-year cluster RCT, 18 Tennessee middle schools: ≈+1.3 percentile ranks/term (≈0.06–0.08 SD/year). Not distinguishable from Khan practice without the AI; low tutor engagement. (A 0.15 SD WestEd figure circulates on secondary sites **[uncertain]**.) | The practice/retrieval loop moved scores, not the chat; build video + checks first. |
| Duolingo: CEFR-controlled generation (CaLM) and Birdbrain | [arXiv 2406.03030](https://arxiv.org/abs/2406.03030); [Duolingo blog](https://blog.duolingo.com/large-language-model-duolingo-lessons) | Prompt auto-filled with **language, CEFR level, theme**; designers add exercise type/grammar focus. CaLM = SFT+RL model that hits a requested CEFR level. Birdbrain adapts exercise *difficulty*, not prose. | Few-shot GPT-4 often misses the level; CaLM beats GPT-4 at a fraction of cost; small human study. | Treat level as a hard constraint checked by a classifier (Q2 thresholds), regenerate on miss. |
| BYJU'S personalisation engine | [AnalyticsIndiaMag](https://www.analyticsindiamag.com/look-byjus-personalization-engine-driving-one-one-learning-experience/); [YourStory](https://yourstory.com/2022/03/byjus-leveraging-data-insights-create-personalized-learning-experiences) | ~50,000-concept knowledge graph; personalisation = **sequencing** (next video/test, remediation), not rewriting explanations. | Vendor claims only **[uncertain]**. | Tag segments with concept IDs now (`concept_ids` in the Q3 schema). |
| Human vs computer tutoring | VanLehn 2011 (via [arXiv 1812.09628](https://arxiv.org/pdf/1812.09628)); Kulik & Fletcher 2016 ([record](https://docs.opendeved.net/lib/2N9LMVR5)) | Bloom's 2-sigma conflated tutoring with mastery learning. VanLehn: human d≈0.79, step-based ITS d≈0.76 — feedback *granularity* matters more than human-ness. Kulik & Fletcher: median ITS effect 0.66 SD (50 evaluations; smaller on standardised tests). | Meta-analyses (28 and 50 studies). | In-video checks target the step just taught, with per-option feedback, not end-of-video quizzes. |
| Expertise reversal / scaffold density | Kalyuga 2007 ([PDF](https://www.uky.edu/~gmswan3/EDC608/Kalyuga2007_Article_ExpertiseReversalEffectAndItsI.pdf)); Spanjers et al. 2010 ([EPR](https://link.springer.com/doi/10.1007/s10648-010-9135-6)); Rey et al. 2019 ([doi](https://www.doi.org/10.1007/S10648-018-9456-4)) | Worked examples, heavy signalling and segment pauses help novices and can *hurt* high-knowledge learners. Spanjers: 2-s automatic pauses helped low-prior-knowledge students only. Rey: segmenting effect small-to-medium (88 comparisons). | Experiments + meta-analysis. | Scaffold density is a level parameter: 6–8 = worked example + sub-steps + pauses; 11–12 = problem-first, faded example. |
| Assistance dilemma | Koedinger & Aleven 2007 ([EPR](https://link.springer.com/doi/10.1007/s10648-007-9049-0)) | Withhold, then add help only as needed: yes/no → hint → bottom-out. | Cognitive Tutor field data. | Tiered hints inside each interaction, never a single reveal. |
| Pretesting (prior-knowledge probes) | Pan & Sana 2021 ([record](https://pure.athabascau.ca/en/publications/pretesting-versus-posttesting-comparing-the-pedagogical-benefits-/)); video pretesting 2022 ([PMC8964911](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8964911/)) | A question *before* the segment, even if answered wrong, improves later memory and cuts mind-wandering in video lectures. | 5 experiments, N=1,573: pretesting beat retrieval practice by d≈0.30. | Open each segment with an unscored "predict", then teach, then a scored recall. |
| Grade-specific simplification ("same lesson, three levels") | Agrawal & Carpuat 2023 ([arXiv](https://arxiv.org/abs/2305.14993)); Ribeiro et al. 2023 ([ACL](https://aclanthology.org/2023.emnlp-main.714)); ReadCtrl ([arXiv](https://arxiv.org/abs/2406.09205)) | Controls that work: target grade **plus** instance-level edit operations; RL that minimises |requested − observed readability|; readability lookahead decoding. Metrics: SARI, FKGL. | Instance-level control beats corpus-wide settings; RL/lookahead close the request–measure gap. | Write the class-11 script first, simplify down with explicit edit ops, measure with Q2, regenerate on miss. |
| Do LLMs adapt when told the age? | Rooein et al. ([arXiv 2312.02065](https://arxiv.org/abs/2312.02065)); Imperial & Tayyar Madabushi 2023 ([ACL](https://aclanthology.org/2023.gem-1.18)) | Four SOTA LLMs: readability barely moves with the requested age; ChatGPT-class models needed refined prompts to hit FKGL/CEFR targets. | Automatic readability vs recommended level. | Never trust "explain to a 12-year-old"; measure and loop. |
| Conversational style | Brame 2016 ([CBE-LSE](https://pmc.ncbi.nlm.nih.gov/articles/PMC5132380/)) | "You/we", enthusiastic narration raises engagement. | Review of Mayer's experiments. | Same voice at all levels; vary content, not tone. |

**What actually varies:** (1) vocabulary tier and sentence length (measured, not prompted); (2) scaffold density; (3) chunk size and pause frequency; (4) a prior-knowledge probe per segment; (5) example domain — concrete for 6–8, symbolic allowed for 11–12 (asserted by LearnLM personas and Mayer, not separately quantified **[uncertain]**); (6) pace (Q2). Cosmetic "age tone" without a measurable readability change carries no evidence.

**Adopt first**
1. A per-level **generation contract** (grade, CEFR tier, max sentence length, scaffold density, pace) injected into the script prompt and verified by the Q2 checker, with regeneration on failure.
2. **Pretest-then-teach-then-recall** structure per segment (Pan & Sana; Szpunar).
3. Tiered hints inside every check (assistance dilemma), rather than reveal-the-answer.

**Open questions**
- No K–12 Indian-classroom evidence that levelled narration (vs levelled *problems*) changes outcomes; Khanmigo RCT suggests practice dominates.
- How to detect prior knowledge without a login: use the first predict-question as the probe and branch only the next segment.
- Hinglish code-switching has no readability literature to lean on.

---

## Q2 — Age-appropriate understandability ("will a student of age X understand this?")

| Approach | Source | What it says concretely | Evidence / validity for spoken text | How to adopt |
|---|---|---|---|---|
| Flesch–Kincaid Grade Level | Kincaid et al. 1975: 0.39·words/sentence + 11.8·syllables/word − 15.59 | Common Core bands: grades 6–8 → FKGL 6.51–10.34; 9–10 → 8.32–12.12; 11–CCR → 10.34–14.2 ([achievethecore](https://achievethecore.org/page/2725/textcomplexity)). | Formulas predict *listenability* of read-aloud text about as well as print readability ([ACL W16-0531](https://preview.aclanthology.org/fix_video/W16-0531.pdf)); they ignore rate, pauses, disfluency. | Primary cheap check; narration is heard once by mostly L2 listeners, so aim 1–2 grades **below** the band floor (synthesis **[uncertain]**). |
| New Dale–Chall (1995) | Chall & Dale 1995: 0.1579·(% unfamiliar words) + 0.0496·(words/sentence) (+3.6365 if > 5% unfamiliar) | Score 5.0–5.9 ≈ grades 5–6; 6.0–6.9 ≈ 7–8; 7.0–7.9 ≈ 9–10; 8.0–8.9 ≈ 11–12. | Word-list based, so vocabulary-sensitive; list is US-English. | Swap its list for Oxford 3000 + per-lesson glossary. |
| Lexile; Coh-Metrix | [lexile.com](https://lexile.com); [cohmetrix.com](http://cohmetrix.com) | Lexile bands 6–8 925–1185L, 9–10 1050–1335L, 11–CCR 1185–1385L. Coh-Metrix adds cohesion/narrativity/concreteness. | Proprietary / web-only; not embeddable. | Sanity mapping only; approximate referential cohesion as content-word overlap between adjacent sentences. |
| Age-of-acquisition norms | Kuperman et al. 2012 ([BRM](https://link.springer.com/article/10.3758/s13428-012-0210-4), 30,121 words, data at crr.ugent.be); [2025 extension](https://link.springer.com/article/10.3758/s13428-025-02843-8) | Mean age (years) at which a word is learned. | r≈.93 with lab norms; predicts lexical decision beyond frequency. L1 US adults. | Flag non-glossary words with AoA > (student age − 1). |
| Word frequency | [SUBTLEX-US](https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexus/overview.htm) (Zipf); [wordfreq](https://pypi.org/project/wordfreq) (multilingual incl. Hindi) | Zipf 1–7; ≥ 4 is everyday vocabulary. | Frequency predicts recognition speed; `wordfreq` is the only drop-in Hindi resource found. | Zipf gate per band (table) **[thresholds mine]**. |
| CEFR word lists | [Oxford 3000/5000 by CEFR](https://www.oxfordlearnersdictionaries.com/about/wordlists/oxford3000-5000) (900 A1 / 800 A2 / 700 B1 / 600 B2, downloadable); [English Profile](https://www.englishprofile.org/wordlists) (web lookup) | A1–B2 graded core vocabulary. | Teacher-validated, learner-oriented — fits Indian English-medium students better than L1 AoA. | 6–8 → A1–B1; 9–10 → A1–B2; 11–12 → Oxford 5000 (+ subject terms). |
| NCERT vocabulary | None machine-readable found; textbooks are public (ncert.nic.in). An Indian textbook readability study exists ([record](https://opact.sdu.edu.tr/vufind/SummonRecord/FETCH-LOGICAL-j537-e2062417d7fd54b380f6b7083fa41af2812045104de3ac010606a92d19335b773)) but was unreadable to me **[uncertain]**. | — | — | Build a "known-by-class-N" list from NCERT PDFs; use as the in-domain glossary. |
| Hindi readability | Sinha et al., COLING 2012 ([ACL C12-2111](https://aclanthology.org/C12-2111/)) | English formulas transfer poorly; Hindi models use sentence length, word length, conjunct (juktakshar) counts. | User experiments. | Use words/sentence, chars/word, conjunct ratio + `wordfreq` hi Zipf; no validated bands **[uncertain]**. |
| Working memory, sentence length | Gathercole et al. 2004 ([eprint](https://eprints.whiterose.ac.uk/5942/)); broadcast writing ([UF IFAS](https://edis.ifas.ufl.edu/publication/wc193)) | WM grows ~linearly from 4 to 15 y; broadcast rule ≤ 20 words, one idea per sentence (no re-reading). | Developmental data; practitioner norms. | Hard caps per band; ≤ 2 clauses for 6–8. |
| Speech rate by age | Ray Hull, WSU ([news item](https://www.wichita.edu/about/wsunews/archive/index.php?nid=3349)) | Children process ~124 wpm (preschool), ~130 (5–7 y), ~135 (grade 5–6), 135–140 (middle school); Fred Rogers ≈ 124 wpm. | Clinical synthesis; primary studies not retrieved **[uncertain]**. Tauroza & Allison 1990: lectures to non-native listeners ≈ 140 wpm **[recalled, unverified]**. | TTS rate per band; measure wpm from alignment, not the script. |
| Pauses / segmenting | Spanjers 2010; Rey 2019 (Q1) | 2-s pauses between segments helped novices. | Experiments / meta-analysis. | ≥ 1.5–2 s at segment boundaries; ≥ 0.5 s between sentences. |
| "Explain to a 12-year-old" evaluation | ELI5 ([ACL P19-1346](https://aclanthology.org/P19-1346/)); SARI ([Xu et al. 2016](https://aclanthology.org/Q16-1029/)); Rooein; Imperial | ELI5 is an answer-quality corpus, not an age benchmark; SARI needs reference simplifications; controlled-readability papers report |target − FKGL| and CEFR-classifier accuracy. | Rooein: LLM readability nearly flat across requested ages. | Use FKGL/Dale–Chall/AoA/CEFR gates with |target − measured| as the loss, plus spot human review. |

**Age ↔ class mapping used below:** class 1 at age 6 (NEP 2020), so class 6 ≈ 11–12 y, class 8 ≈ 13–14, class 10 ≈ 15–16, class 12 ≈ 17–18.

### Concrete thresholds per class band (code-checkable; English narration)

All numbers are my synthesis of the sources above, biased ~1–2 grades below Common Core because narration is heard once, mostly by L2 listeners. Tokens in the lesson's declared **glossary** (technical terms shown and defined on screen) are excluded from vocabulary checks.

| Check (per script, per segment) | Class 6–8 (11–14 y) | Class 9–10 (14–16 y) | Class 11–12 (16–18 y) |
|---|---|---|---|
| FKGL target / fail | 5–7 / > 8 | 7–9 / > 10 | 9–11 / > 12 |
| New Dale–Chall (Oxford 3000 + glossary as "familiar") | ≤ 7.0 | ≤ 8.0 | ≤ 9.0 |
| Mean words per sentence / absolute max | ≤ 14 / 20 | ≤ 17 / 24 | ≤ 20 / 28 |
| Clauses per sentence (max) | 2 | 3 | 3 |
| Mean syllables per word | ≤ 1.45 | ≤ 1.55 | ≤ 1.65 |
| Non-glossary words with Kuperman AoA > (age − 1) | ≤ 5% | ≤ 5% | ≤ 5% (age − 1 = 15) |
| Non-glossary words outside CEFR tier | outside A1–B1 ≤ 8% | outside A1–B2 ≤ 10% | outside Oxford 5000 ≤ 12% |
| Non-glossary tokens with `wordfreq` Zipf below | 3.5 → ≤ 5% | 3.0 → ≤ 5% | 2.7 → ≤ 5% |
| New glossary terms introduced | ≤ 1 per 45 s, each defined at first use | ≤ 1 per 30 s | ≤ 1 per 20 s |
| Passive-voice sentences | ≤ 10% | ≤ 15% | ≤ 20% |
| Narration rate (measured from alignment) | 120–135 wpm | 130–145 wpm | 140–155 wpm |
| Pause between sentences / at segment boundary | ≥ 0.6 s / ≥ 2.0 s | ≥ 0.5 s / ≥ 1.5 s | ≥ 0.4 s / ≥ 1.5 s |
| Segment length before a check | ≤ 90 s | ≤ 150 s | ≤ 180 s |
| Referential cohesion (adjacent sentences share ≥ 1 content word) | ≥ 80% | ≥ 70% | ≥ 60% |

Hindi/Hinglish: apply words/sentence and pause/rate rows unchanged; replace FKGL/AoA/CEFR rows with: mean characters per word ≤ 5.5 / 6.0 / 6.5, conjunct-consonant ratio ≤ 0.08 / 0.10 / 0.12, and `wordfreq` hi Zipf gate as above (Sinha 2012 features; bands **unvalidated**).

**Adopt first**
1. Implement the table as a `readability_check(script, band, glossary)` returning pass/fail per row; wire it as the regeneration loop criterion (Duolingo/Ribeiro lesson: measure, don't prompt).
2. Load Kuperman AoA + Oxford 3000/5000 + `wordfreq`; build the NCERT per-class corpus later.
3. Measure wpm and pauses from the forced-alignment output, and set TTS speed per band.

**Open questions**
- Whether Indian English-medium students' effective vocabulary matches CEFR tiers; needs a small norming study with NCERT corpora.
- No Hindi AoA or grade-band norms exist; Hinglish mixing ratio has no literature.
- Formulas ignore maths notation read aloud ("x squared minus four"); decide whether to count spoken-maths tokens.

---

## Q3 — Interactivity embedded in video

| Approach | Source | What it says concretely | Evidence | How to adopt |
|---|---|---|---|---|
| Interpolated testing | Szpunar, Khan & Schacter 2013, PNAS ([PMC3631699](https://pmc.ncbi.nlm.nih.gov/articles/PMC3631699/)); Jing et al. 2016 ([PDF](https://sites.harvard.edu/schacter-memory/files/2022/08/jing2016-1-1.pdf)) | 21-min lecture in 4 segments, short test after each. | Mind-wandering 40% → 20%; 3× more notes; better final retention and cross-segment integration. | One retrieval check per segment (our bands: every 90–180 s). |
| Pretesting inside video | [PMC8964911](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8964911/); Pan & Sana 2021 | Questions *before* a segment cut task-unrelated thought and help memory. | Video-lecture experiments. | Unscored `predict` at segment start. |
| Video design guidelines | Brame 2016 ([CBE-LSE](https://pmc.ncbi.nlm.nih.gov/articles/PMC5132380/)); Guo, Kim & Rubin 2014 ([UBC summary](https://flexible.learning.ubc.ca/?p=2852)) | Short videos (engagement drops after ~6 min; < 3 min watched of > 12-min videos), signalling, segmenting, conversational style, guiding questions. | edX logs (6.9M sessions) + review. | 4–8 min lessons or chapterised longer ones, one check per chapter. |
| Meta-analyses of active/interactive video | Zhang, Li, Pi & Yang 2025, Educational Research Review ([record](https://faculty.snnu.edu.cn/pizhongling/en/lwcg/123220/content/119506.htm)); Ploetzner 2024, Instructional Science ([Springer](https://link.springer.com/article/10.1007/s11251-024-09693-5)) | 54 studies: retention g=0.33, comprehension 0.28, transfer 0.43; embedded questions most common (46%); cognitive load also up (g=0.19). Ploetzner: g=0.52 but navigation and prompts confounded. | 93% adult samples; K-12 thin **[uncertain for us]**. | Embedded retrieval + immediate feedback is the best-supported tier; keep questions short. |
| Segmenting with pauses | Rey 2019; Spanjers 2010 (Q1) | ~2-s auto-pause helps novices. | Meta-analysis. | `pause_prompt` type: 2-s hold with "what comes next?", no answer capture. |
| Edpuzzle / PlayPosit | [Edpuzzle learning-science page](https://blog.edpuzzle.com/teaching-today/learning-science-edpuzzle/) | Pause, overlay question, prevent skipping, dashboard. | Vendor-cited small studies; no RCT found **[uncertain]**. | Mirror the UX, not the vendor. |
| H5P Interactive Video JSON | [semantics.json](https://github.com/h5p/h5p-interactive-video/blob/master/semantics.json) | Per interaction: `duration{from,to}`, `pause`, `displayType`, `x,y,width,height`, `action{library,params}`, `adaptivity{correct,wrong}{seekTo,allowOptOut,message}`, `goto`; plus `bookmarks[]{time,label}`, `endscreens`, `summary`. | Mature OSS format with web/LMS players. | Borrow `adaptivity.wrong.seekTo` and `bookmarks`; keep our schema a strict subset so H5P export is a mapping. |
| xAPI video profile + cmi5 | [xAPI Video Profile v1.0.3](https://w3id.org/xapi/video/v1.0.3); [community repo](https://github.com/liveaspankaj/xapi-video-cop) | Verbs `played/paused/seeked/completed/interacted`; extensions `progress`, `played-segments`, `time`; standard `answered` with `result.success/response`; cmi5 adds LMS launch rules. SCORM only has `cmi.interactions.n.*`. | Industry standard. | Emit xAPI from the player, buffer offline, batch-sync. |
| Timed-metadata carriers | WebVTT metadata tracks ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API)); HLS `EXT-X-DATERANGE` ([RFC 8216 §4.3.2.7](https://datatracker.ietf.org/doc/html/rfc8216#section-4.3.2.7)) and ID3; DASH `EventStream`; surfaced as player events ([JW Player](https://docs.jwplayer.com/players/reference/metadata-events)) | WebVTT `kind="metadata"` cues carry JSON and fire `enter/exit`; HLS/DASH events need streaming infrastructure. | Spec facts. | MP4 on phones → **JSON sidecar**; optionally a WebVTT metadata track for web; HLS/DASH only if we adopt adaptive streaming. |
| YouTube | Chapters via description timestamps (first `0:00`, ≥ 3 chapters, ≥ 10 s — [guide](https://gling.ai/blog/creating-youtube-chapters-a-complete-guide)); cards/end screens | Cards are link teasers; cannot pause or capture answers. | — | Chapters + on-screen "pause and try" prompts only; real checks live in our app. |
| Web / React Native player | [react-native-video](https://docs.thewidlarzgroup.com/react-native-video/) (`onProgress` ~250 ms, `paused`, `ref.seek()`); HTMLMediaElement `timeupdate` (~4 Hz), TextTrack cue events | Pause within ~0.25 s of a cue, overlay, record, seek back. | — | Pause when `onProgress` crosses `t` (web: cue `enter`), overlay, write answer + xAPI, `seek(on_wrong.seek_to)`. |

### Minimal `interactions.json` schema (sidecar, one per rendered video)

```json
{
  "schema": "lessonforge.interactions/0.1",
  "video_id": "cls8_math_linear_eq_01",
  "lang": "en",                      // en | hi | hinglish
  "band": "6-8",
  "duration_s": 312.4,
  "chapters": [ { "t": 0.0, "title": "What is an equation?" }, { "t": 95.2, "title": "Balancing both sides" } ],
  "interactions": [
    {
      "id": "q1",
      "type": "predict",            // predict | recall | mcq | numeric | pause_prompt
      "t": 94.0,                     // seconds; player pauses here
      "pause": true,
      "max_wait_s": 45,              // auto-resume for unattended playback; null = wait
      "scored": false,
      "prompt": { "text": "What should we do to both sides?", "tts": "What should we do to both sides?" },
      "options": [
        { "id": "a", "text": "Subtract 3", "correct": true,  "feedback": "Yes — keep the balance." },
        { "id": "b", "text": "Add 3",      "correct": false, "feedback": "That makes the left side bigger." }
      ],
      "answer": null,                // for numeric: { "value": 4, "tolerance": 0 }
      "hints": [ "Think about the balance scale." ],
      "on_wrong": { "seek_to": 61.0, "allow_skip": true },
      "concept_ids": ["NCERT.8.M.2.linear_eq.balance"],
      "segment_id": "seg2",
      "xapi": { "object_id": "https://lessonforge/q/cls8_math_linear_eq_01/q1" }
    }
  ]
}
```

Rules: `t` must not fall inside a narration sentence (snap to the alignment's sentence-end pause); at most one interaction per segment plus the opening `predict`; every `mcq` needs per-option feedback (immediate-feedback evidence); `on_wrong.seek_to` points at the explanation start; the player emits xAPI `played/paused/answered/completed` with `result.success`, `result.response`, and `time` in extensions.

**Adopt first**
1. Sidecar JSON above, with `predict` at segment start and a scored `recall`/`mcq` at segment end (Szpunar; Pan & Sana).
2. Player behaviour: pause-overlay-record-seek-on-wrong, with offline xAPI buffering.
3. Chapters emitted for both the player and the YouTube description.

**Open questions**
- Evidence is overwhelmingly adult/university; the class 6–8 cognitive-load cost of frequent checks is unmeasured.
- Branching (different next segment per answer) has little evidence beyond "seek back"; start with seek-back only.
- Whether unattended auto-resume (`max_wait_s`) erodes the interpolated-testing effect.

---

## Q4 — Colour palette and background for teaching videos

| Approach | Source | What it says concretely | Evidence | How to adopt |
|---|---|---|---|---|
| Positive-polarity advantage | Piepenbrock et al. 2013, Ergonomics ([record](https://documentacion.fundacionmapfre.org/documentacion/bib/143702.do)); Buchner & Baumgartner 2007 ([record](https://madoc.bib.uni-mannheim.de/26118/)); [NN/g summary](https://www.nngroup.com/articles/dark-mode/) | Dark-on-light improves acuity and proofreading for young and old; advantage grows as text shrinks (smaller pupil, sharper image). Users don't *notice* it. | Several lab experiments. | Default **light theme** for phone/projector; keep text large if dark. |
| Glance legibility, ambient light | Dobres et al. 2016 ([PMC5213401](https://pmc.ncbi.nlm.nih.gov/articles/PMC5213401)); Dobres 2017 (via NN/g) | At 23 lux, positive polarity thresholds 38.6% faster; daylight: no polarity effect; night: positive wins. | Psychophysics. | Dark is fine in bright rooms; worst case is dim room + small text. |
| Projected text | Heliyon 2024 ([PMC10957382](https://pmc.ncbi.nlm.nih.gov/articles/PMC10957382)) | Dark-on-light best for displayed *and* projected text, against the folk rule **[abstract-level only]**. | One study. | Light theme for classroom projection. |
| Low-end phones | Display tests ([PhoneArena](https://www.phonearena.com/news/Older-LCD-technology-the-clear-winner-in-direct-sunlight_id12082)) | Budget LCDs render black as grey (less dark-theme contrast) and are often more sunlight-readable than cheap OLEDs. | Reviews **[uncertain]**. | Dark grey, not pure black; no thin strokes in the dark theme; ship both themes. |
| WCAG 2.2 | [SC 1.4.3 / 1.4.6 / 1.4.11](https://www.w3.org/TR/WCAG22/#contrast-minimum) | 4.5:1 normal text, 3:1 large text (≥ 24px / 19px bold) and non-text, 7:1 enhanced. | Normative; weak in dark mode. | Gate: text roles ≥ 4.5:1, strokes/fills ≥ 3:1. |
| APCA (WCAG 3 draft) | [apca-introduction](https://github.com/Myndex/apca-introduction) | Lc 90 preferred body, 75 min body (> 18px), 60 for > 24px, 45 for > 36px, 30 spot text, 15 invisibility. Better in dark mode. | Perceptual model, not yet normative. | Second gate: equations (≥ 36 px at 1080p) ≥ Lc 45; captions ≥ Lc 75. |
| Colour-blind safety | Okabe & Ito ([jfly](https://jfly.uni-koeln.de/color/)); Wong 2011, Nature Methods ([doi](https://www.nature.com/articles/nmeth.1618)) | Eight hues (E69F00, 56B4E9, 009E73, F0E442, 0072B2, D55E00, CC79A7, black) separable under protan/deutan/tritan; pair hue with lightness/shape. | CVD simulation; widely adopted. | Never encode right/wrong by hue alone: add ✓/✗, strike-through or box. |
| Colour coding in multimedia learning | Ozcelik et al. 2009 ([METU record](https://avesis.metu.edu.tr/yayin/4c4f4fae-afe5-4186-b7a3-ea75cb837310/an-eye-tracking-study-of-how-color-coding-affects-multimedia-learning)) | Same colour for corresponding text/diagram elements improved retention and transfer; faster text↔picture search. | Eye-tracking experiment. | One role colour per quantity across equation, diagram and caption. |
| How many hues | Categorical-colour guidance ([review](https://www.scitepress.org/PublishedPapers/2025/131094)) | ≤ 8–12 colours remain nameable. | — | 4 semantic hues + 1 accent + 3 neutrals, fixed across lessons. |
| 3Blue1Brown / manimgl | [default_config.yml](https://github.com/3b1b/manim/blob/master/manimlib/default_config.yml); Manim CE defaults to black ([docs](https://docs.manim.community/en/stable/reference/manim.utils.color.html)) | Background `#333333`; BLUE_C `#58C4DD`, TEAL_C `#5CD0B3`, GREEN_C `#83C167`, YELLOW_C `#FFFF00`, GOLD_C `#F0AC5F`, RED_C `#FC6255`, PURPLE_C `#9A72AC`, GREY_B `#BBBBBB`. | Computed: white on #333333 12.6:1; BLUE_C 6.2:1; GREEN_C 5.9:1; RED_C 4.2:1 (fails AA). No published rationale for the dark background found **[uncertain]**. | Keep the 3b1b *roles* (blue = given, yellow = highlight, red = negative); replace RED_C; no pure yellow on light. |
| Khan Academy colour system | [Khan blog](https://blog.khanacademy.org/how-we-rebuilt-khan-academys-color-system-from-the-ground-up) | 8 hues, 88 swatches; Success/Warning/Critical/Instructive/Neutral tokens; strong foregrounds pass 4.5:1 on all base backgrounds; dark mode = extra ramp stop. Classic videos: black board, coloured pen (observation). | Design-system practice. | Role tokens resolved per theme, contrast-tested in CI. |
| Brilliant / Veritasium | [Brilliant scrape](https://www.webdesignhot.com/design.md/brilliant-org/) | Brilliant: near-black UI (#0c0e16), coral accent (#fc6e51) **[uncertain]**; Veritasium is live-action. | — | Not load-bearing. |

**Semantic roles for maths teaching.** `given` (data stated in the problem), `unknown` (what we solve for), `result` (derived/final value), `wrong` (misconception, cancelled term), `accent/highlight` (attention this instant), `ink` (ordinary text and strokes), `muted ink` (labels, axes, de-emphasised steps), `background`. Rule: a quantity keeps its role colour in equation, diagram and narration caption (Ozcelik), and a role change is animated (given → result) rather than instantaneous.

### Recommended palettes (contrast computed against the theme background; APCA = absolute Lc, 0.0.98G-4g)

| Role | Dark theme hex | WCAG vs #1C1F26 | APCA Lc | Light theme hex | WCAG vs #FBFAF6 | APCA Lc |
|---|---|---|---|---|---|---|
| background | `#1C1F26` | — | — | `#FBFAF6` | — | — |
| ink | `#F2F3F5` | 14.85:1 | 98 | `#1C1F26` | 15.79:1 | 100 |
| muted ink | `#A8B0BD` | 7.55:1 | 57 | `#5B6472` | 5.73:1 | 77 |
| accent / highlight | `#FFE566` (text or glow) | 13.08:1 | 89 | `#FFE98A` (fill behind ink text; ink on fill 13.57:1, Lc 90) | 1.16:1 (non-text fill) | 8 |
| given | `#80B1E7` | 7.35:1 | 56 | `#0B5CBE` | 6.11:1 | 78 |
| unknown | `#D19461` | 6.38:1 | 50 | `#AD5820` | 4.79:1 | 71 |
| result | `#56FAAA` | 12.29:1 | 85 | `#1F7E6D` | 4.72:1 | 71 |
| wrong | `#E57A9E` | 5.98:1 | 47 | `#6B0A12` | 11.99:1 | 94 |

Notes on the choice. Hue families were fixed by role (blue/orange/teal-green/red-pink), then a constrained search maximised the *minimum* pairwise separation of {ink, given, unknown, result, wrong, accent} under simulated deuteranopia and protanopia, subject to WCAG ≥ 5:1 (dark) / ≥ 4.5:1 (light). Result: minimum CVD ΔE ≈ 24 (dark) and ≈ 20 (light), achieved mainly by giving `result` and `wrong` opposite lightness (bright mint vs mid pink on dark; mid teal vs very dark crimson on light), which is the Okabe-Ito tactic. All text roles pass WCAG AA; on the dark theme `unknown` and `wrong` sit at APCA Lc 47–50, i.e. fine for equation-size text (> 36 px, Lc 45) but not for small captions, so captions use `ink`/`muted` only. The dark background is a blue-grey, not pure black, so LCD "grey blacks" degrade it less and white text halation is reduced. Yellow is used as a *fill* on the light theme because no yellow text passes 4.5:1 on white.

**Adopt first**
1. Ship **both** themes from one role-token file; light is the default for projector/phone delivery (positive-polarity evidence), dark for the 3b1b-style brand on desktop/YouTube.
2. CI contrast gate: every text role ≥ 4.5:1 and the equation roles ≥ APCA Lc 45; fail the render otherwise.
3. Redundant encoding for `wrong` (strike/✗) and `result` (box/✓), never hue alone.

**Open questions**
- No study on dark vs light for *animated maths* specifically; the polarity evidence is static text.
- Low-end Android LCD measurements in Indian classrooms (gamma, black level) are anecdotal; worth a 10-phone field check.
- Whether the brand value of the 3b1b look outweighs the measured legibility cost of dark themes for class 6–8 on small screens.
