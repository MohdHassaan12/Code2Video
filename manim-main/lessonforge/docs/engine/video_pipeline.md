# Video Agent (Vid Agent) & Animation Pipeline

This document outlines the architecture, flow, and components of the **Video Generation & Reference Subsystem** (referred to as the **Vid Agent**) within the Concept Explorer pipeline.

The Video subsystem serves two main purposes:
1. **Automated STEM Animation Generation (Manim):** Creating custom mathematical and scientific animation clips dynamically using an external LLM-powered storyboard/code planner and rendering them via a local Manim engine.
2. **Web Video Retrieval (YouTube API):** Querying and embedding high-quality, real-world educational videos from YouTube to act as curated learning references.

---

## 1. Directory & File Structure

All core logic for the Vid Agent resides in the [`ce/`](file:///d:/concept_explorer-main/ce/) package:

* **[`ce/videos_build.py`](file:///d:/concept_explorer-main/ce/videos_build.py):** The primary orchestrator. Iterates through the lesson nodes and coordinates the planning, generation, and finalization phases.
* **[`ce/video_planner.py`](file:///d:/concept_explorer-main/ce/video_planner.py):** The Planning Agent. Analyzes node contents to determine if a video is needed (e.g. for experiments, misconceptions, recaps) and specifies requirements (type, duration).
* **[`ce/clip_planner.py`](file:///d:/concept_explorer-main/ce/clip_planner.py):** Segmenter. Breaks down a long video specification into manageable ~20-second clip slots.
* **[`ce/video_generation.py`](file:///d:/concept_explorer-main/ce/video_generation.py):** Clip Orchestrator. Coordinates generating individual clips and merging them into the final video file.
* **[`ce/stem_animation.py`](file:///d:/concept_explorer-main/ce/stem_animation.py):** STEM Lab Connector. Communicates with the external rendering server to generate storyboards, convert them to Python Manim code, compile the video, and download results.
* **[`ce/video_merger.py`](file:///d:/concept_explorer-main/ce/video_merger.py):** File Assembler. Calls `ffmpeg` to losslessly concatenate multiple rendered clip segments into one final `.mp4` video.
* **[`ce/video.py`](file:///d:/concept_explorer-main/ce/video.py):** Web Video Search. Performs clean, safe-search API requests to YouTube to supply curated reference videos.

---

## 2. Pipeline Flow Chart

The following diagram illustrates the complete end-to-end execution flow of the Video Generation Pipeline:

```mermaid
graph TD
    A[Start: ce.videos_build] --> B[Loop: For Each Lesson Node]
    B --> C{Video Spec / Video Exists?}
    C -- Yes (and not forced) --> B
    C -- No / Forced --> D[ce.video_planner.analyze_node]
    
    D --> E{Agent Available?}
    E -- Yes --> F[Call LLM: Analyze node content & grade context]
    E -- No --> G[Fallback: Hook/Reveal/Concept/Simulation/Recap need 45s visual]
    
    F --> H[Return JSON Spec]
    G --> H
    
    H --> I{needed == true?}
    I -- No --> B
    I -- Yes --> J[ce.clip_planner.plan]
    
    J --> K[Segment duration into ~20s clips]
    K --> L[ce.video_generation.generate_animation]
    
    L --> M[Loop: For Each Clip Segment]
    M --> N[ce.stem_animation.generate_clip]
    N --> O[POST /api/generate_storyboard]
    O --> P[POST /api/generate_code]
    P --> Q[POST /api/compile_video]
    Q --> R[Poll /api/render_status until 'done']
    R --> S[Download MP4 segment to generated_videos/]
    S --> M
    
    M -- All Clips Rendered --> T[ce.video_merger.merge_videos]
    T --> U[Concat segments using ffmpeg]
    U --> V[Save to node['video'] as ready]
    V --> B
    
    B -- All Nodes Processed --> W[End: Return generated status, paths & cost]
```

---

## 3. Detailed Component Breakdown

### A. The Planning Phase
* **Orchestrator Trigger:** `videos_build.py` runs `video_planner.analyze_node(lesson, node)`.
* **Prompt Construction:** The planner sends the subject, grade, lesson objective, node type (e.g. `hook`, `reveal`), and raw node contents to the model configuration specified under the `"video"` model group.
* **Decision Matrix:** The LLM decides if an animation is needed, targeting:
  1. Misconceptions (visualizing the gap between intuition and reality)
  2. Multi-step processes or state changes
  3. Complicated abstract concepts
  4. STEM laboratory experiments
  5. Recaps / summarize highlights
* **JSON Structure & Normalization:** The LLM is directed to return a JSON object with strict keys: `needed` (boolean), `type` (string), `objective` (string), and `duration` (integer). To handle model-specific variance, a normalization layer in `video_planner.py` automatically maps alternative boolean keys (e.g., `needsAnimation`, `needs_animation`, `animationNeeded`) to `needed` and applies safe defaults before returning the spec to the orchestrator.
* **Fallback Behavior:** If no LLM api key is configured, the offline stub maps a static list of node types (`hook`, `reveal`, `concept`, `simulation`, `recap`) to default 45-second `VISUALIZATION` videos.

### B. Segmenting & Scheduling
* **Clip Planner:** Manim renders are most reliable and faster to compute when segmented into shorter clips (~20 seconds each). 
* `clip_planner.py` calculates `n = max(1, duration // 20)` and schedules `n` clips. Each clip gets a context dictionary with metadata and segment ordering.

### C. Storyboard, Code, & Rendering (STEM Lab Service)
* **Local Render Server:** `stem_animation.py` acts as a client to `http://localhost:5000` (STEM Lab API).
* **API Handshake:**
  1. `/api/generate_storyboard`: Passes the topic and styling choices (e.g., `3blue1brown/minimalist/neon`) to get a visual description structure.
  2. `/api/generate_code`: Translates the visual storyboard into runnable Python code using the `manim` library.
  3. `/api/compile_video`: Submits the generated script to render a low-quality (`quality: "l"`) widescreen `.mp4` video.
  4. `/api/render_status/{job_id}`: Polls every 2 seconds until the compile state resolves to `done` or raises a `RuntimeError` with compilation logs if a build failure occurs.
  5. **Download:** The rendered segment is saved inside the local folder `generated_videos/` with a unique timestamped name.

### D. Concatenation & Compilation
* **FFmpeg Concat:** `video_merger.py` writes absolute paths of all rendered segment files into a temporary text list.
* It fires off `ffmpeg -f concat -safe 0 -i <temp_txt> -c copy <final_mp4> -y` to losslessly stitch the clips together in milliseconds, avoiding expensive re-encoding.
* The final path is added back to the node metadata as `node["video"]["path"]`.

---

## 4. Web Video Reference Alternative (`ce/video.py`)
If generating custom animations is not required or the local rendering engine is offline, curators can choose real-world video embeds:
* Uses the official **YouTube Data API v3** to search for relevant learning material.
* Implements safety filters: `safeSearch: "strict"`, `videoEmbeddable: "true"`, and `videoDuration: "medium"` (4 to 20 mins) to match academic classroom needs.
* Translates standard video URLs into privacy-enhanced embed URLs (`https://www.youtube-nocookie.com/embed/<id>`) to keep student privacy safe inside frames.
* **Graceful Degradation:** If `YOUTUBE_API_KEY` is empty, it returns an empty list, allowing the rest of the editor dashboard to work cleanly without blocking.
