"""
Interactive Active-Recall Player Generator.
Transforms passive AI-generated educational videos into active-recall learning companions:
- Generates interactive HTML5/CSS3/JS single-page web player
- Enforces the cognitive "Testing Effect" (Roediger & Karpicke) via automated checkpoint pauses
- Displays section-specific Concept Check quizzes with instant feedback
- Provides chapter navigation, speed controls, and mastery analytics
"""

import os
import json
from typing import Dict, List, Any, Optional
from adapt_manim.core.types import Storyboard, StoryboardSection


class InteractivePlayerGenerator:
    """Generates standalone interactive active-recall companion web players for educational videos."""

    @classmethod
    def generate_player_html(
        cls,
        topic: str,
        video_filename: str,
        storyboard: Storyboard,
        quiz_items: List[Dict[str, Any]],
        output_path: str,
        section_durations: Optional[List[float]] = None
    ) -> str:
        """
        Generates a standalone, responsive, self-contained interactive HTML5 player
        with embedded chapter quizzes and active-recall checkpoints.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Build chapter metadata with timestamps
        chapters = []
        cumulative_time = 0.0

        for idx, sec in enumerate(storyboard.sections):
            dur = section_durations[idx] if (section_durations and idx < len(section_durations)) else (len(sec.cues) * 4.5)
            start_t = cumulative_time
            end_t = cumulative_time + dur
            cumulative_time = end_t

            # Associate quiz item if available
            q = quiz_items[idx] if idx < len(quiz_items) else {
                "question": f"What is the key takeaway of {sec.title}?",
                "options": [
                    "A) It establishes the foundational geometric definition.",
                    "B) It demonstrates the mathematical formulation.",
                    "C) It provides the pedagogical synthesis.",
                    "D) All of the above."
                ],
                "answer_index": 3,
                "explanation": f"This section introduces the foundational concepts and visual formulation for {sec.title}."
            }

            chapters.append({
                "id": sec.id,
                "title": sec.title,
                "start_time": round(start_t, 2),
                "end_time": round(end_t, 2),
                "quiz": {
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "answer_index": q.get("answer_index", 0),
                    "explanation": q.get("explanation", "Great job! This concept is central to understanding the overall proof.")
                }
            })

        chapters_json = json.dumps(chapters, indent=2)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{topic} - Interactive Video Lecture</title>
  <style>
    :root {{
      --bg: #0f1117;
      --card-bg: #1a1d24;
      --accent: #58c4dd;
      --accent-green: #83c167;
      --accent-yellow: #ffff00;
      --accent-red: #fc6255;
      --text: #e1e7ed;
      --text-muted: #8b949e;
      --border: #30363d;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      padding: 14px 24px;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .title-badge {{
      display: inline-block;
      background: rgba(88, 196, 221, 0.15);
      color: var(--accent);
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 0.8rem;
      font-weight: 700;
      text-transform: uppercase;
      margin-right: 12px;
    }}
    h1 {{ font-size: 1.25rem; font-weight: 700; display: inline-flex; align-items: center; }}
    .main-layout {{
      display: flex;
      flex: 1;
      height: calc(100vh - 65px);
    }}
    .video-container {{
      flex: 3;
      position: relative;
      background: #000;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
    }}
    video {{
      width: 100%;
      max-height: 100%;
      outline: none;
    }}
    .sidebar {{
      flex: 1.2;
      min-width: 340px;
      max-width: 420px;
      background: var(--card-bg);
      border-left: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }}
    .sidebar-header {{
      padding: 16px;
      border-bottom: 1px solid var(--border);
      font-weight: 600;
      font-size: 0.95rem;
      display: flex;
      justify-content: space-between;
    }}
    .chapter-list {{
      list-style: none;
      padding: 12px;
      overflow-y: auto;
      flex: 1;
    }}
    .chapter-item {{
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 10px;
      cursor: pointer;
      transition: all 0.2s ease;
      background: rgba(255, 255, 255, 0.02);
    }}
    .chapter-item:hover {{
      border-color: var(--accent);
      background: rgba(88, 196, 221, 0.05);
    }}
    .chapter-item.active {{
      border-color: var(--accent);
      background: rgba(88, 196, 221, 0.12);
    }}
    .chapter-item.completed {{
      border-color: var(--accent-green);
    }}
    .chapter-title {{
      font-weight: 600;
      font-size: 0.9rem;
      margin-bottom: 4px;
    }}
    .chapter-time {{
      font-size: 0.78rem;
      color: var(--text-muted);
    }}
    .quiz-overlay {{
      display: none;
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 17, 23, 0.92);
      backdrop-filter: blur(8px);
      z-index: 100;
      padding: 32px;
      overflow-y: auto;
      flex-direction: column;
      justify-content: center;
      align-items: center;
    }}
    .quiz-overlay.visible {{ display: flex; }}
    .quiz-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 28px;
      max-width: 620px;
      width: 100%;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
    }}
    .quiz-header {{
      font-size: 0.8rem;
      color: var(--accent);
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .quiz-question {{
      font-size: 1.15rem;
      font-weight: 600;
      margin-bottom: 20px;
      line-height: 1.4;
    }}
    .quiz-options {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 20px;
    }}
    .option-btn {{
      padding: 12px 16px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255,255,255,0.03);
      color: var(--text);
      cursor: pointer;
      text-align: left;
      font-size: 0.92rem;
      transition: all 0.2s;
    }}
    .option-btn:hover {{
      background: rgba(88, 196, 221, 0.1);
      border-color: var(--accent);
    }}
    .option-btn.correct {{
      background: rgba(131, 193, 103, 0.2);
      border-color: var(--accent-green);
      color: #bbf7d0;
    }}
    .option-btn.wrong {{
      background: rgba(252, 98, 85, 0.2);
      border-color: var(--accent-red);
      color: #fecaca;
    }}
    .feedback-box {{
      display: none;
      padding: 12px;
      border-radius: 6px;
      font-size: 0.9rem;
      margin-bottom: 16px;
      line-height: 1.4;
    }}
    .btn-continue {{
      display: none;
      padding: 10px 20px;
      background: var(--accent);
      color: #000;
      border: none;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
      font-size: 0.9rem;
    }}
    .stats-card {{
      padding: 16px;
      background: rgba(255, 255, 255, 0.02);
      border-top: 1px solid var(--border);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>

  <header>
    <div>
      <span class="title-badge">Interactive Video Lecture</span>
      <h1>{topic}</h1>
    </div>
    <div style="font-size: 0.85rem; color: var(--text-muted);">
      Powered by Code2Video & AdaptManim
    </div>
  </header>

  <div class="main-layout">
    <!-- Video Player & Active Recall Overlay -->
    <div class="video-container">
      <video id="player" controls playsinline>
        <source src="{video_filename}" type="video/mp4">
        Your browser does not support the video tag.
      </video>

      <!-- Active Recall Modal Overlay -->
      <div id="quiz-overlay" class="quiz-overlay">
        <div class="quiz-card">
          <div class="quiz-header">🎯 Active-Recall Checkpoint</div>
          <div id="quiz-question" class="quiz-question">Question goes here</div>
          <div id="quiz-options" class="quiz-options"></div>
          <div id="quiz-feedback" class="feedback-box"></div>
          <button id="btn-continue" class="btn-continue">Continue Lecture ➔</button>
        </div>
      </div>
    </div>

    <!-- Chapter Navigation Sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">
        <span>📖 Lecture Chapters</span>
        <span id="score-tracker">Score: 0/0</span>
      </div>
      <ul id="chapter-list" class="chapter-list"></ul>
      <div class="stats-card">
        <strong>💡 Active Learning Mode:</strong><br>
        Video automatically pauses at chapter boundaries to reinforce core concepts via the Testing Effect.
      </div>
    </div>
  </div>

  <script>
    const chapters = {chapters_json};
    const player = document.getElementById('player');
    const overlay = document.getElementById('quiz-overlay');
    const questionEl = document.getElementById('quiz-question');
    const optionsEl = document.getElementById('quiz-options');
    const feedbackEl = document.getElementById('quiz-feedback');
    const continueBtn = document.getElementById('btn-continue');
    const chapterList = document.getElementById('chapter-list');
    const scoreTracker = document.getElementById('score-tracker');

    let triggeredQuizzes = new Set();
    let currentQuizChapter = null;
    let correctAnswers = 0;
    let totalQuestionsAnswered = 0;

    // Render chapters
    chapters.forEach((ch, idx) => {{
      const li = document.createElement('li');
      li.className = 'chapter-item';
      li.id = 'chapter-' + idx;
      li.innerHTML = `
        <div class="chapter-title">${{idx + 1}}. ${{ch.title}}</div>
        <div class="chapter-time">${{formatTime(ch.start_time)}} - ${{formatTime(ch.end_time)}}</div>
      `;
      li.onclick = () => {{
        player.currentTime = ch.start_time;
        player.play();
      }};
      chapterList.appendChild(li);
    }});

    function formatTime(sec) {{
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${{m}}:${{s < 10 ? '0' : ''}}${{s}}`;
    }}

    // Time update listener
    player.ontimeupdate = () => {{
      const t = player.currentTime;

      // Update active chapter highlight
      chapters.forEach((ch, idx) => {{
        const item = document.getElementById('chapter-' + idx);
        if (t >= ch.start_time && t < ch.end_time) {{
          item.classList.add('active');
        }} else {{
          item.classList.remove('active');
        }}
      }});

      // Trigger quiz near end of chapter (0.5s before chapter end)
      chapters.forEach((ch, idx) => {{
        if (t >= (ch.end_time - 0.6) && t <= ch.end_time && !triggeredQuizzes.has(idx)) {{
          player.pause();
          triggeredQuizzes.add(idx);
          showQuiz(ch, idx);
        }}
      }});
    }};

    function showQuiz(chapter, idx) {{
      currentQuizChapter = chapter;
      questionEl.textContent = chapter.quiz.question;
      optionsEl.innerHTML = '';
      feedbackEl.style.display = 'none';
      continueBtn.style.display = 'none';

      chapter.quiz.options.forEach((opt, optIdx) => {{
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.textContent = opt;
        btn.onclick = () => handleAnswer(btn, optIdx, chapter.quiz);
        optionsEl.appendChild(btn);
      }});

      overlay.classList.add('visible');
    }}

    function handleAnswer(btn, selectedIdx, quiz) {{
      const allBtns = optionsEl.querySelectorAll('.option-btn');
      allBtns.forEach(b => b.disabled = true);
      totalQuestionsAnswered++;

      const isCorrect = (selectedIdx === quiz.answer_index);
      if (isCorrect) {{
        correctAnswers++;
        btn.classList.add('correct');
        feedbackEl.style.background = 'rgba(131, 193, 103, 0.15)';
        feedbackEl.style.color = '#bbf7d0';
        feedbackEl.innerHTML = '<strong>✓ Correct!</strong> ' + quiz.explanation;
      }} else {{
        btn.classList.add('wrong');
        if (allBtns[quiz.answer_index]) {{
          allBtns[quiz.answer_index].classList.add('correct');
        }}
        feedbackEl.style.background = 'rgba(252, 98, 85, 0.15)';
        feedbackEl.style.color = '#fecaca';
        feedbackEl.innerHTML = '<strong>✗ Not quite:</strong> ' + quiz.explanation;
      }}

      scoreTracker.textContent = `Score: ${{correctAnswers}}/${{totalQuestionsAnswered}}`;
      feedbackEl.style.display = 'block';
      continueBtn.style.display = 'inline-block';
    }}

    continueBtn.onclick = () => {{
      overlay.classList.remove('visible');
      player.play();
    }};
  </script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)

        return output_path

