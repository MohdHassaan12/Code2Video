# 06 addendum — checks and additions to the teaching-script plan

Written 2026-10-09 by the session that built the paste-your-own-script path. The plan is
[`06_teaching_script_plan.html`](06_teaching_script_plan.html) and this file replaces none of
it. Three literature searches had been started before that plan existed; once it appeared
they were narrowed to what **adds to it, corrects it or puts a number on it**. Their three
reports are kept below as written, because the working copies were in a temp folder that a
reboot wipes.

## How far each claim was checked

- Each report gives its own level per source: full text read, or abstract only.
- Re-read by me against the saved source pages, and matching what the reports say: the
  NRICH, CK-12, PhET, OpenStax and Illustrative Mathematics licence lines; Fiorella & Mayer
  2016 (the four experiments' effect sizes); Crouch et al. 2004 (30% and 32%); the Agastya
  trial's abstract; Google's REST reference for the notebook API (notebooks, sources and
  audio overviews, nothing else); the Google Terms of Service clauses; and on OpenRouter's
  own documentation, that the `openrouter:web_search` server tool exists (beta) and that the
  `web` plugin and `:online` are deprecated.
- **Not re-checked by me:** NCERT's rights notice (NCERT's site reset the connection from
  this machine when I tried again; the search read it in the front matter of one textbook
  PDF and saved no copy), OpenRouter's per-request search prices, the date of the NotebookLM
  rename, the skill naming rule, every system in "Not named in the plan", and every effect
  size not listed above.

## What this changes in the plan

1. **Sources have licences, and the plan does not mention them.** NCERT textbooks are free
   to read and, by the notice the search read, all rights reserved. NRICH and CK-12 forbid
   AI or automated use. PhET, OpenStax, Exploratorium, Khan Academy and the Mathematics
   Assessment Project are non-commercial. Only Illustrative Mathematics (first edition) may
   be quoted and adapted freely. The plan saves numbered source passages in
   `teaching_pack.json` and shows them in the app: whether to store passages or only
   citations and our own paraphrase is the owner's decision. Table in report 2.
2. **No separate search key is needed.** The plan says searching needs Tavily, Serper or
   Brave. The OpenRouter key the project already has can search through a server tool, and
   can take a chapter PDF as a file part. Report 3, section 2.
3. **"Draw while saying" rests on less than the plan implies.** In Fiorella & Mayer 2016
   the gain came with the instructor's hand visible (d = 0.35); the same drawing with no hand
   gave d = −0.16, not significant. Manim has no hand. A later study did find dynamic
   drawings better than static ones (d = 0.54, abstract only). Keep the principle; do not
   expect the drawing-in effect by itself.
4. **The opening question has measurable conditions.** A question asked before the content
   helps the questioned content (g = 0.54) and not the rest (0.04), helps far more when the
   learner commits to a guess (0.65 against 0.22), and less for school children (0.22) than
   adults. So: one question, about the lesson's one big idea, guessable from what the class
   already knows, a guess asked for, and the answer given by name later. Report 1.
5. **The try-it task needs four more things.** A "what did you see?" step with the true
   outcome shown (18% of observations in one study did not match what happened); an answer
   that carries the reason (even with a prediction, 70% gave no fully correct explanation);
   an end product the learner writes or says, since handling objects alone is the weakest
   active level; and one line saying what each object stands for. After an animated lesson,
   two lines in words beat a drawing. One light task should not be expected to move test
   scores: in the Uttar Pradesh trial the monthly four-hour lab did (+0.22 to 0.34 SD) and
   the lighter visit did not. Report 2.
6. **One spine.** The narration search recommends Kulgemeyer 2020 as the checkable core: it
   is the only candidate tested whole on a one-way explainer for school students, and its
   fourteen features can each be checked in a script. The three stage frameworks and the
   seven principles stay. Five features it would add: say "you", join steps with "because",
   one name per object, the everyday word before the term, a closing summary. Two of these
   are already rules here (`frameworks.py` voices say "Speaks to 'you'"; the writer's prompt
   says "Use each technical term one way throughout"). The closing summary pulls against
   the current recap stage, which is "retrieval, not summary": that is a choice to make, not
   a finding. Its evidence is one study: more declarative knowledge (d = 0.42), no
   difference found for conceptual knowledge.
7. **Smaller corrections.** The skill folder should be `teaching-script`, not
   `teaching_script`, if it is ever to load as a standard skill. NotebookLM's consumer
   product has no API; the enterprise one returns no text at all, so the plan's "build its
   shape, use the product by hand" stands. LearnLM is no longer a separate model: its
   behaviour is reached by system instructions on a Gemini model, which OpenRouter serves.
   PhET is a simulation, not a task by hand.

## Papers the searches could not open

Springer and Elsevier opened in full from this machine's network. Taylor & Francis, Sage
and APA blocked automated access; the DOIs are listed at the end of reports 1 and 2. A
person opening them in a browser on the same network, or exported copies, would let the
abstract-only rows be upgraded.

---

## Report 1 — what makes narration teach (deltas to the plan)

Additions and corrections to `06_teaching_script_plan.html` only. **F** = full text read. **A** = abstract only. Not reached: humour, analogy meta-analyses, elaborative interrogation, evidence for Gagné.

### 1. Sources not in the plan that change the template

| Source (DOI) | Level | Finding | Rule for the script |
|---|---|---|---|
| Wittwer & Renkl 2010 (10.1007/s10648-010-9136-5) | F | 21 studies. Explanations added to worked examples: d = 0.16; conceptual knowledge 0.36; against learners prompted to explain for themselves −0.01. | Put each "why" to the learner as a question with a pause, then answer it. |
| St. Hilaire, Chan & Ahn 2023 (10.3758/s13423-023-02353-8) | F | Questions before learning: questioned content g = 0.54 (k = 97), other content 0.04 (k = 91). With a guess 0.65, without 0.22. School children 0.22, adults 0.62. | The opening question is about the one big idea, asks for a guess, and is answered explicitly later. |
| Motz et al. 2025, ManyClasses 2 (10.1037/edu0000978) | A | 30 classes, n = 1,571, grade 6 to college. Prequestions before a video raised delayed scores, more for students who answered correctly; some skipped the video. | The opening question must be guessable from what the class already knows. |
| Schneider et al. 2018 (10.1016/j.edurev.2017.11.001) | F | 103 studies, N = 12,201. Highlighting: retention g = 0.53, transfer 0.33. Flashing −0.56 (k = 3). Maths/logic retention 0.08, not significant (k = 9). | One highlight per sentence, by colour, never flashing. In maths it will not carry a step alone. |
| Rey 2012 (10.1016/j.edurev.2012.05.003) | F | Interesting extras cost d = 0.66 when time is fixed and 0.10 or less when it is not. | A video is fixed-pace: every sentence serves the big idea. |
| Brom et al. 2018 (10.1016/j.edurev.2018.09.004) | F | 33 samples, N = 2,924. Warm colours and faces on the content graphics: retention d = 0.39, transfer 0.33, intrinsic motivation 0.26. | Liveliness goes on the objects that carry the idea, not beside them. |
| Mar et al. 2021 (10.3758/s13423-020-01853-1) | F | 150 effects. Stories recalled and understood better than exposition: g = 0.55; age 16 and under 0.67. With content matched the interval is −0.13 to 1.27. | Give the idea itself a story shape: puzzle, attempt, resolution. |
| Alfieri et al. 2013 (10.1080/00461520.2013.775712) | A | 57 experiments. Two cases compared side by side: d = 0.50; larger when the principle follows the comparison. | "Elaborate" is a side-by-side pair (36 and 18), principle stated after. |

### 2. Where verified sources qualify the plan

**a.** Plan: "Fiorella & Mayer 2016 (watching a diagram being drawn beats seeing it drawn already)". The abstract (A) reports the gain with the instructor's hand visible (d = 0.35). Drawing with no hand: d = −0.16, not significant. Computer animation imitating drawing: d = 0.33, not significant. Fiorella et al. 2019 (A, 10.1037/edu0000325) did find d = 0.54 for dynamic over static drawings. Manim has no hand, so principle 3 has weaker support than the plan implies.

**b.** Plan: "The rule comes after they have guessed." Kulgemeyer 2020 (F), feature 1, says rule first when the goal is a principle, example first when it is a procedure. His experiment did not test it (both videos were example-first). Alfieri supports principle-after. It is a choice, not a finding.

**c.** Plan: "Chi & Wylie 2014 … Each step up teaches more." Thurn et al. 2023 (F, comment, 10.1038/s41539-023-00197-4) list studies where that ordering fails. Welhaf et al. 2022 (F, N = 195, 10.1186/s41235-022-00372-y): in-lecture tests cut mind-wandering only slightly and did not raise learning. Use ICAP to describe tasks, not to score them.

**d.** Plan: "interesting extras cost learning". Sundararajan & Adesope 2020 (F): true overall, but for maths and statistics materials g = +0.42 (k not recorded).

### 3. Numbers for papers the plan cites without them

- Sundararajan & Adesope 2020 (F): 58 papers, 68 effects, N = 7,521; g = −0.33.
- Szpunar et al. 2013 (F): n = 32 and 48; 21-minute lecture, four segments. Mind-wandering 19% against 41% of probes (d = 1.01); last-segment score 89% against 70% (d = 1.01). Re-reading questions with answers did nothing.
- Kulgemeyer 2020 (F): grade 9, n = 90 and 86, whole classes assigned; conceptual scale α = .52. The better video added an analogy, more representations, everyday words for terms, "the more … the more" in place of formulas, linked examples, relevance prompts, "you" in place of the passive, a closing summary.
- Mayer, Fiorella & Stull 2020 (F): narrative review, no pooled effect sizes.
- Carpenter & Toftness 2017, Wittwer & Renkl 2008, Chi & Wylie 2014, Kulgemeyer 2018 (A): abstracts give no effect sizes.

### 4. Could not open

Springer and Elsevier opened in full here through the institute subscription. Taylor & Francis, Sage and APA blocked automated access; a browser on the same network may open them.

- Wittwer & Renkl 2008: 10.1080/00461520701756420
- Kulgemeyer 2018: 10.1080/03057267.2018.1598054
- Alfieri et al. 2013: 10.1080/00461520.2013.775712
- Chi & Wylie 2014: 10.1080/00461520.2014.965823
- Fiorella & Mayer 2016: 10.1037/edu0000065
- Fiorella et al. 2019: 10.1037/edu0000325
- Carpenter & Toftness 2017: 10.1016/j.jarmac.2016.07.014
- Motz et al. 2025: 10.1037/edu0000978
- Dunlosky et al. 2013: 10.1177/1529100612453266
- Hörnlein & Kulgemeyer 2026: 10.1080/09500693.2026.2646710 (the plan's d = 0.69 is unchecked by me)

### 5. The spine

Kulgemeyer 2020. It is the only candidate tested whole on this format and audience (six-minute one-way science explainer, grade 9, d = 0.42 on declarative knowledge), and its fourteen features are each checkable. Merrill's four phases give a usable order, but the 2002 paper (F, 10.1007/BF02505024) makes "no attempt in this paper to identify the empirical support for these principles". ICAP's ordering is contested. I agree with keeping the three stage frameworks for order with the principles on top; five of the seven map onto Kulgemeyer's features. Three changes:

1. Add the features the seven do not name and that bear most on dullness: say "you", join steps with "because", one name per object, everyday words before the term, a closing summary. I did not check whether the existing rules list has them.
2. Soften principle 3 as in 2a.
3. Treat the task after the video as what builds transferable understanding; the video alone moved only declarative knowledge.

---

## Report 2 — the try-it task and the licences of the sources

Opened on 2026-10-09. "Full" = full text read; "abs" = abstract only. Licence notes are my reading of the quoted text, not legal advice.

### 1. Licences of the plan's sources

Only one source checked may be quoted and adapted freely (Illustrative Mathematics, first edition). Two forbid AI or automated use outright (NRICH, CK-12).

| Source | Licence line (quoted) and page | What it allows us |
|---|---|---|
| NCERT textbooks | "ALL RIGHTS RESERVED … No part of this publication may be reproduced, stored in a retrieval … permission of the publisher." Prelims, `ncert.nic.in/textbook/pdf/hesc1ps.pdf` | Cite chapter, paraphrase. Saving numbered passages in `teaching_pack.json` and showing them in the app needs the owner's decision. |
| PhET | "published under the Creative Commons Attribution–NonCommercial license (CC BY-NC 4.0)"; "The PhET logo must remain visible". `phet.colorado.edu/en/licensing` | Screenshots or video with attribution, non-commercial only. |
| NRICH | "not licensed for text and data mining … including for the purposes of training artificial intelligence systems without the prior written permission". `nrich.maths.org/terms-and-conditions` | Link only. Do not ingest. |
| Exploratorium | "copy, reproduce, adapt or distribute Work … solely for informational, educational and other noncommercial purposes" with "© The Exploratorium, www.exploratorium.edu". `exploratorium.edu/about/use-policy` | Adapt non-commercially with notice and live link. |
| Mathematics Assessment Project | "may be reproduced as-is for non-commercial use. Precise terms vary between materials." `map.mathshell.org` | Paraphrase the common issues, link. No adapted copies. |
| 3b1b/videos | "contents of this repository are available under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0". README | Study the moves. Code in prompts would carry NC-SA. |
| Illustrative Mathematics | First edition: "CC BY 4.0 … share and adapt the materials for any purpose, including commercially". v.360: CC BY-NC 4.0. `illustrativemathematics.org/terms-of-use` | First edition: quote and adapt with attribution. |
| OpenStax | "transitioned our textbook library from a mix of CC BY and CC BY-NC-SA licensing to CC BY-NC-SA". `openstax.org/license` | Quote with attribution, non-commercial, share-alike. |
| CK-12 | "You may not use … to build or train artificial intelligence … (iii) to create new content … using automated means". `ck12info.org/curriculum-materials-license` | Exclude. |
| Khan Academy | "solely for your personal, non-commercial purposes"; CC items are BY-NC-SA 4.0. `khanacademy.org/about/tos` | Link only unless an item is marked CC. |
| DIKSHA | "only to the extent expressly permitted by the license applicable to such Content". `diksha.gov.in/term-of-use.html` | Check each item. |
| Arvind Gupta, Eklavya, At Right Angles | No licence statement on the home pages opened (At Right Angles: "© 2026 Azim Premji University"). | Treat as all rights reserved: describe in our words, link. |
| Driver et al.; Van de Walle | Commercial books, not checked. | Cite and paraphrase. |

### 2. Verified findings that change the try-it task

| Finding | Source | Design consequence |
|---|---|---|
| Correct explanations: no demo 22%, watch 24%, predict 30%, predict and discuss 32%. Predicting added 2 minutes. | Crouch et al. 2004, N=158–297 per mode, full | The stored answer must carry the reason, and the question must ask why. |
| 18% of observations did not match what happened. Predicting first made a correct observation about 20% more likely. Learning depended on observing correctly. | Miller et al. 2013, N=292, full | Add a "what did you see?" step and show the true outcome before the question. |
| Predicting and self-testing rated "Favorable" at every age; learner drawing "Unfavorable" up to grade 5. Predicting raised revision of a misconception, d = 0.56, ages 6 to 9. | Brod 2020 review, Table 1, full; Theobald & Brod 2021, N=94, abs | Classes 6 to 8: predict and answer. Drawing only with a part-drawn frame. |
| In pauses between animations, writing a summary beat no activity (d = 0.48; 0.54 after a week). Drawing did not (d = 0.23, n.s.). | Lawson & Mayer 2024, N=203 and 130, college, full | After an animated lesson, ask for two lines in words. |
| Enacting with objects: median d = 0.51, but "most effective for … learners with higher prior knowledge"; learners "need explicit guidance" mapping objects to the idea. | Fiorella & Mayer 2016, full | Task comes after the explanation. One line says what each object stands for. |
| "for acquiring conceptual knowledge, virtual laboratories can replace physical ones", except for "young children, who do not have previous relevant physical experience". Virtual wins for what cannot be seen. Combined is best. | de Jong, Linn & Zacharia 2013, full | Card states the kind: by hand for an unfamiliar phenomenon, animation for the unseen, hands then animation where possible. |
| Grade 5: video against hands-on, no significant difference in knowledge. | DISER 2024 (10.1186/s43031-024-00103-x), 2 classes, N=101, full | Handling alone adds little. |
| Inquiry effect 0.50; teacher-led about 0.40 larger than student-led. Guidance d = 0.50. | Furtak et al. 2012; Lazonder & Harmsen 2016, abs | Give the steps. |
| India, 132 government schools, about 14,000 students, classes 6 to 8, guided hands-on. Monthly four-hour mobile lab: test scores +0.22 to 0.34 SD. Two-hour kit visit: "limited average effects". | Bharti et al. 2026, CESifo WP 12691, RCT, working paper, full | Low-cost hands-on works here when guided and repeated. Do not expect one light task to move scores. |

Hoshangabad: only a 2023 commentary found, with no controlled outcome data. Two hands-on meta-analyses report g = 1.55 (Caglak 2017) and g = 0.98 (Koyunlu Ünlü 2024, mostly university samples); neither is safe as a headline number.

### 3. Where the plan needs qualifying

- "a demo teaches only if you predict first": even with prediction, 70% gave no fully correct explanation (Crouch).
- "doing and producing beat watching … Each step up teaches more": handling beans is ICAP's Active level; the gain is at Constructive. Teachers had "minimal success in designing Constructive … activities" (Chi et al. 2018, full). Check that every task ends in something the learner writes or says.
- PhET sits under "The task to try by hand": it is a simulation.
- "NCERT textbooks (free PDFs)": free to read, all rights reserved.
- "Drawing to learn" (Ainsworth, Prain & Tytler): see Brod and Lawson & Mayer above.
- Hofstein & Lunetta 2004: a narrative review, abstract only; it supports no specific rule.

### 4. Source-grounded script generation

Not searched before the scope change. Nothing verified.

### 5. Not opened

Full texts: Hofstein & Lunetta (10.1002/sce.10106), Chi & Wylie (10.1080/00461520.2014.965823), Furtak (10.3102/0034654312457206), Lazonder & Harmsen (10.3102/0034654315627366), Olympiou & Zacharia (10.1002/sce.20463), White & Gunstone 1992. Licence pages: NCERT copyright policy and lab manuals, IOPSpark, RSC Education, AAAS Project 2061, the PhET activity agreement, the DIKSHA licensing policy, MAP per-lesson terms.

---

## Report 3 — Google's systems, grounding through the keys we have, other systems

Every fact was read on the named page in this session; gaps are marked **unverified**.

**What changes in the plan:** no separate search key is needed; the NotebookLM sentence can now cite Google; the skill folder name breaks the SKILL.md standard.

### 1. Google's own pages

**NotebookLM API.** Plan: *"Its API is in alpha and covers notebooks, sources and audio; I found no endpoint for a script or a video (this is from third-party client docs, not Google's own)."* Confirmed from Google, with additions:

- Renamed **Gemini Notebook** on 2026-07-16 (blog.google). The consumer product has no API.
- The API belongs to **Gemini Notebook Enterprise** (Google Cloud), `v1alpha`, labelled Preview. Notebooks: create, get, listRecentlyViewed, batchDelete, share. Sources: batchCreate, uploadFile, get, batchDelete. Audio overviews: create, delete. Google's REST reference lists nothing else: **no method returns text**, so no question-answering, report or video.
- It needs a Cloud project, Cloud Identity and at least 15 licences; no price on the page.
- The standalone Podcast API is deprecated: "Google isn't allowlisting new customers."

Pages: `docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/` `api-notebooks`, `api-notebooks-sources`, `api-audio-overview`, `podcast-api`, `set-up-licensing`, all dated 2026-10-07.

**LearnLM.** "LearnLM is no longer a separate listing in AI Studio"; it is "integrated into Gemini starting with the 2.5 model series" (ai.google.dev/gemini-api/docs/learnlm, 2026-04-28). No LearnLM id exists on the Gemini models page (2026-10-06) or in OpenRouter's list. Behaviour comes from system instructions: Google "fine-tuned it to follow pedagogical system instructions" (`services.google.com/fh/files/misc/learnlm_prompt_guide.pdf`). The guide's recipe is PARTS (Persona, Act, Recipient, Theme, Structure). Guided Learning is a Gemini app mode; I found no API. So through OpenRouter, "using LearnLM" means a `google/gemini-*` model with the skill as its system instruction.

### 2. Grounding: OpenRouter key or Google key

| Need | OpenRouter key | Price |
|---|---|---|
| Web search | **Yes**: `openrouter:web_search` server tool (beta), `url_citation` results. The `web` plugin and `:online` are deprecated | Exa $0.007 per request; Parallel $0.001–0.005; Perplexity $0.005; native Google $0.014; native OpenAI or Anthropic $0.01 |
| Chapter PDF in context | **Yes**: `file` content part, URL or base64 | Input tokens; `cloudflare-ai` parser free; `mistral-ocr` $2 per 1,000 pages |
| Fetch a URL | `openrouter:web_fetch` exists | **unverified** |
| Gemini File Search (page-numbered citations) | Not documented; needs a Google AI Studio key | Indexing $0.15 per 1M tokens; storage free |
| Gemini `url_context`, Deep Research | Google key | Tokens only; $1–3 per task (Google's estimate) |

Per 1M tokens in/out on OpenRouter: `google/gemini-3.8-flash` $0.75/$3.75; `openai/gpt-5.6-terra` $2/$12; `anthropic/claude-sonnet-5.5` $2/$10. One card (60k in, 5k out) is about $0.06 on Flash, $0.18 on the others (my arithmetic).

### 3. Corrections and qualifications

| Plan | Verified |
|---|---|
| "Searching needs a search key (Tavily, Serper or Brave)" | **Not needed**; see section 2. The native-Google list does not name 3.8 Flash; `engine: auto` falls back to Exa |
| `harness/skills/teaching_script/` | agentskills.io/specification: `name` takes lowercase letters, digits and hyphens only and "must match the parent directory name". Use `teaching-script`. Google's admin page (2026-10-07) says Gemini app skills "use the open, Markdown-based `SKILL.md` format", so the folder can be tried by hand in Gemini |
| "recall after 3 to 5 days was 78% against 67% for a plain reader", 60 students | **Confirmed** (research.google, 2025-09-16). Ages 15–18, one chapter, up to 40 minutes, control was a PDF reader. Learn Your Way is an interactive reader, so this is not evidence about video |
| LearnLM "judged on five principles" | Confirmed; its evidence is tutoring conversations (arXiv 2412.16429, 2505.24477), not scripts |
| "Manim video from a planner, a coder and a critic" | True of Code2Video; TheoremExplainAgent has no critic. Its human study found LLM judges agree with people at 0.16 on logical flow and 0.14 on accuracy, which supports "a person still has to watch" |
| "automatic judges cannot rank the best videos" | EduPanel's abstract claims reliability "comparable to a median human expert"; the plan's wording is stronger. Teaching Monster paper not opened |

### 4. Not named in the plan

- **CourseBlueprint** (arXiv 2606.20608): retrieval, prerequisite graph, then narration under a contract (hook, recall, core, analogy only if flagged, link forward). LLM-judged only.
- **TeachMaster** (ACL 2026, arXiv 2601.04204): each page's narration is written after, and from, its visual code.
- **LASEV** (KDD 2026, arXiv 2602.11790): without its semantic critique gate the expert "publishable" rate fell from 92% to 52%.
- **Oak Aila** (arXiv 2502.10410): an auto-evaluator tuned against human raters one criterion at a time.
- **`anthropics/k12-teacher-skills`** (Apache-2.0): lesson-plan skills with an `evals/` rubric folder.
- **`GarethManning/education-agent-skills`** (CC BY-SA 4.0): 165 skills citing named research.
- **Bespoke** (arXiv 2609.26540): 25 experts rated 92 generated lectures, mean 3.42/5.
- **Anthropic Citations**: quotes with guaranteed source pointers; not combinable with structured outputs.

### 5. Driving consumer NotebookLM with cookies

Google Terms of Service (effective 2026-07-30) list as abuse: "using automated means to access content from any of our services in violation of the machine-readable instructions on our web pages"; "spamming, hacking, or bypassing our systems or protective measures"; "using AI-generated content from our services to develop machine learning models or related AI technology". And: "Google may suspend or terminate your access to the services or delete your Google Account."

The tools agree: `notebooklm-mcp-cli` says it "may not be aligned with Google's Terms of Service"; `notebooklm-py` "uses undocumented Google APIs that can change without notice". The cookie file acts as the signed-in account, and the third clause would bar fine-tuning on notebook output. My reading, not legal advice: keep the baseline manual, as the plan says.

---

## First reading of the reviewer's teaching checks (plan step 4), 2026-10-09

The thirteen questions in `harness/skills/teaching-script/checks.md` are now put to the
reviewer for any lesson written from a teaching card (`critic.review`), **reported and not
enforced**: a check that is not met is a minor finding and a line in
`verification["teaching"]`; it starts no rewrite. They were run once over the first four
pilot lessons made from cards (two on square numbers by prime factorisation, one on adding
fractions, one on Newton's first law; three Hinglish, one English). One reviewer call each.

| Check | Met in | What it found |
|---|---|---|
| 1 opening question with a guess | 4 of 4 | |
| 2 answered by name later | 4 of 4 | |
| 3 the why said with "because" while a picture shows it | 3 of 4 | once said without its picture |
| 4 the why first put as a question | 4 of 4 | |
| 5 something on screen for every beat's sentences | 1 of 4 | **not reliable from text**: it passed the one lesson where a person watching saw the picture show a bus while the voice spoke of a box |
| 6 the same picture carried through and changed | **0 of 4** | every lesson swaps to a new object mid-way |
| 7 two cases side by side before the rule | 3 of 4 | |
| 8 a card mistake stated as a learner would make it, shown to fail | 1 of 4 | |
| 9 wrong choices come from the card's mistakes | 2 of 4 | |
| 10 a question that asks to predict or decide | 4 of 4 | |
| 11 the try-it task set in the narration, without its answer | **0 of 4** | the narration gives the answer, or leaves out the question |
| 12 no chapter opens with a definition or a stage name | 4 of 4 | did not notice an opening a person called "jargon": it does not ask about that |
| 13 nothing contradicts the card | 4 of 4 | |

What follows from it:

- **Do not let these gate yet.** The fixes it proposes for 3, 5 and 6 are changes to the
  picture, which a rewrite of the words cannot make, and 9 needs the answer choices changed,
  which the rewrite step does not touch. Enforcing them would start rewrite rounds that
  cannot succeed.
- **11 and 8 are consistent and fixable in words**: better fixed where the script is written
  (the writer's instructions for setting the task and for meeting the mistake) than by the
  reviewer afterwards.
- **6 is the open problem the plan already names as its last step** (the picture follows the
  card): the count now puts a number on it.
- Four lessons, one reviewer, one reading each: enough to see what recurs, not to rank lessons.
