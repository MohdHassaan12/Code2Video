document.addEventListener("DOMContentLoaded", () => {
    // --- Application State ---
    let currentMode = "creator"; // 'creator' or 'student'
    let currentSlides = [];
    let activeSlideIndex = 0;
    let storyboardData = null;
    let generatedCode = "";
    
    // --- DOM Elements ---
    const apiKeyInput = document.getElementById("api-key-input");
    const btnToggleApi = document.getElementById("btn-toggle-api");
    const apiSettingsBody = document.getElementById("api-settings-body");
    const modeTabs = document.querySelectorAll(".mode-tab");
    const studentOnlyInputs = document.getElementById("student-only-inputs");
    const topicInput = document.getElementById("topic-input");
    const ytUrlInput = document.getElementById("youtube-url-input");
    const styleSelect = document.getElementById("style-select");
    const personaSelect = document.getElementById("persona-select");
    const techTermsSelect = document.getElementById("tech-terms-select");
    const languageSelect = document.getElementById("language-select");
    const ttsProviderSelect = document.getElementById("tts-provider-select");
    const speakerSelect = document.getElementById("speaker-select");
    const backgroundSelect = document.getElementById("background-select");
    const qualitySelect = document.getElementById("quality-select");
    const aspectSelect = document.getElementById("aspect-select");
    const interestInput = document.getElementById("interest-input");
    const interestTags = document.querySelectorAll(".interest-tag");
    const btnGenerate = document.getElementById("btn-generate");
    const btnText = btnGenerate.querySelector(".btn-text");
    const btnLoader = btnGenerate.querySelector(".btn-loader");
    
    const mainTabs = document.getElementById("main-tabs");
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");
    
    const slidesEmpty = document.getElementById("slides-empty");
    const slidesDeck = document.getElementById("slides-deck");
    const currentSlideContainer = document.getElementById("current-slide-container");
    const slidePrev = document.getElementById("slide-prev");
    const slideNext = document.getElementById("slide-next");
    const slideDots = document.getElementById("slide-dots");
    const tabSlidesBtn = document.getElementById("tab-slides-btn");
    
    const jsonEmpty = document.getElementById("json-empty");
    const jsonBox = document.getElementById("json-box");
    const jsonCode = document.getElementById("json-code");
    const nonManinPanel = document.getElementById("non-manim-panel");
    const nonManinCount = document.getElementById("non-manim-count");
    const nonManinRows = document.getElementById("non-manim-rows");
    const nonManinBody = document.getElementById("non-manim-body");
    const nonManinToggleLabel = document.getElementById("non-manim-toggle-label");
    document.getElementById("non-manim-header").addEventListener("click", () => {
        const open = nonManinBody.style.display !== "none";
        nonManinBody.style.display = open ? "none" : "block";
        nonManinToggleLabel.textContent = open ? "▼ show" : "▲ hide";
    });

    const preflightPanel  = document.getElementById("preflight-panel");
    const preflightSummary = document.getElementById("preflight-summary");
    const preflightBody   = document.getElementById("preflight-body");
    const preflightToggle = document.getElementById("preflight-toggle-label");
    const preflightRows   = document.getElementById("preflight-rows");
    document.getElementById("preflight-header").addEventListener("click", () => {
        const open = preflightBody.style.display !== "none";
        preflightBody.style.display = open ? "none" : "block";
        preflightToggle.textContent = open ? "▼ show" : "▲ hide";
    });

    const issuesPanel  = document.getElementById("issues-panel");
    const issuesSummary = document.getElementById("issues-summary");
    const issuesBody   = document.getElementById("issues-body");
    const issuesToggle = document.getElementById("issues-toggle-label");
    const issuesRows   = document.getElementById("issues-rows");
    document.getElementById("issues-header").addEventListener("click", (e) => {
        if (e.target.closest("button")) return; // don't toggle when clicking copy buttons
        const open = issuesBody.style.display !== "none";
        issuesBody.style.display = open ? "none" : "block";
        issuesToggle.textContent = open ? "▼ show" : "▲ hide";
    });

    let _issuesData = null; // store for copy buttons

    document.getElementById("btn-copy-issues-json").addEventListener("click", () => {
        if (!_issuesData) return;
        navigator.clipboard.writeText(JSON.stringify(_issuesData, null, 2));
        showToast("Issues list copied as JSON", "success");
    });

    document.getElementById("btn-copy-issues-checklist").addEventListener("click", () => {
        if (!_issuesData || !_issuesData.issues) return;
        const topic = (storyboardData && storyboardData.topic) || "Storyboard";
        const missing  = _issuesData.issues.filter(i => i.tier === "missing");
        const fallback = _issuesData.issues.filter(i => i.tier === "fallback");
        let out = `Asset Issues — ${topic}\n${"─".repeat(50)}\n\n`;
        if (missing.length) {
            out += `🔴 MISSING — need external sourcing (${missing.length})\n`;
            missing.forEach(i => {
                out += `  [ ] Scene ${i.scene} · ${i.element_type}${i.element_id ? ` (${i.element_id})` : ""}\n`;
                out += `      "${i.description}"\n`;
                out += `      → ${i.action}\n`;
            });
            out += "\n";
        }
        if (fallback.length) {
            out += `🟡 DEGRADED — will render as native shape (${fallback.length})\n`;
            fallback.forEach(i => {
                out += `  [ ] Scene ${i.scene} · ${i.element_type}${i.element_id ? ` (${i.element_id})` : ""}\n`;
                out += `      keyword: "${i.description}"\n`;
                out += `      → ${i.action}\n`;
            });
        }
        navigator.clipboard.writeText(out);
        showToast("Issues copied as checklist", "success");
    });
    
    const codeEmpty = document.getElementById("code-empty");
    const codeBox = document.getElementById("code-box");
    const pythonCodeTextarea = document.getElementById("python-code");
    const btnCompileCustom = document.getElementById("btn-compile-custom");
    
    const videoEmpty = document.getElementById("video-empty");
    const videoBox = document.getElementById("video-box");
    const manimVideo = document.getElementById("manim-video");
    
    const consoleLogs = document.getElementById("console-logs");
    const btnClearLogs = document.getElementById("btn-clear-logs");
    const toastContainer = document.getElementById("toast-container");

    // --- Load Saved API Key ---
    const savedKey = localStorage.getItem("gemini_api_key");
    if (savedKey) {
        apiKeyInput.value = savedKey;
    }
    
    // Save API key on change
    apiKeyInput.addEventListener("input", () => {
        localStorage.setItem("gemini_api_key", apiKeyInput.value.trim());
    });

    // Toggle API Key settings section
    btnToggleApi.addEventListener("click", () => {
        apiSettingsBody.classList.toggle("hidden");
    });

    // --- Mode Tab Switching ---
    modeTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            modeTabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            currentMode = tab.dataset.mode;
            
            if (currentMode === "student") {
                studentOnlyInputs.classList.add("show");
                btnText.textContent = "Generate Slide Deck";
                topicInput.value = "Gravitation";
                interestInput.value = "Minecraft";
            } else {
                studentOnlyInputs.classList.remove("show");
                btnText.textContent = "Generate Storyboard";
                topicInput.value = "Pythagorean Theorem";
            }
        });
    });

    // --- Interest Tags selection ---
    interestTags.forEach(tag => {
        tag.addEventListener("click", () => {
            interestInput.value = tag.dataset.val;
            autoDetectBackgroundFromInterest(tag.dataset.val);
        });
    });

    // --- Style Select Auto-Change Background ---
    styleSelect.addEventListener("change", () => {
        const style = styleSelect.value;
        if (style.includes("chalkboard")) {
            backgroundSelect.value = "chalkboard.jpg";
        } else if (style.includes("cyberpunk")) {
            backgroundSelect.value = "space.jpg";
        } else if (style.includes("powerpoint")) {
            backgroundSelect.value = "white_canvas";
        } else {
            backgroundSelect.value = "default";
        }
    });

    // --- Interest Input Auto-Change Background ---
    function autoDetectBackgroundFromInterest(interest) {
        const lower = interest.toLowerCase();
        if (lower.includes("space") || lower.includes("universe") || lower.includes("astronomy") || lower.includes("galaxy") || lower.includes("physics")) {
            backgroundSelect.value = "space.jpg";
        } else if (lower.includes("school") || lower.includes("classroom") || lower.includes("chalk")) {
            backgroundSelect.value = "chalkboard.jpg";
        } else if (lower.includes("notebook") || lower.includes("paper") || lower.includes("write") || lower.includes("drawing") || lower.includes("art")) {
            backgroundSelect.value = "notebook_paper.jpg";
        } else if (lower.includes("minecraft") || lower.includes("game") || lower.includes("building") || lower.includes("engineer") || lower.includes("blueprint") || lower.includes("grid")) {
            backgroundSelect.value = "blueprint.jpg";
        }
    }

    interestInput.addEventListener("input", () => {
        autoDetectBackgroundFromInterest(interestInput.value);
    });

    // --- Main View Tab Switching ---
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.dataset.tab;
            switchTab(targetTab);
        });
    });

    function switchTab(targetTab) {
        tabBtns.forEach(b => {
            if (b.dataset.tab === targetTab) {
                b.classList.add("active");
            } else {
                b.classList.remove("active");
            }
        });
        
        tabPanes.forEach(pane => {
            if (pane.id === targetTab) {
                pane.classList.add("active");
            } else {
                pane.classList.remove("active");
            }
        });
    }

    // --- Logger functions ---
    function log(message, type = "system") {
        const line = document.createElement("div");
        line.className = `console-line ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        line.textContent = `[${timestamp}] ${message}`;
        
        consoleLogs.appendChild(line);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
    }

    btnClearLogs.addEventListener("click", () => {
        consoleLogs.innerHTML = "";
        log("Console cleared.");
    });

    // --- Toast Alert Notification ---
    function showToast(message, type = "success") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span>${type === 'success' ? '✓' : '✗'}</span>
            <span>${message}</span>
        `;
        toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // --- Helper to get Headers ---
    function getHeaders() {
        const headers = {
            "Content-Type": "application/json"
        };
        const key = apiKeyInput.value.trim();
        if (key) {
            headers["X-Gemini-API-Key"] = key;
        }
        return headers;
    }

    // --- Narration language / voice controls ---
    // Sarvam speakers per language + Gemini voice list, mirrored from the debug sandbox
    // (debug_sandbox/sandbox_app.py). The chosen voice is sent to the server as `speaker`;
    // for the Gemini provider UniversalTTSService accepts a Gemini voice name there
    // (viz_helpers falls back to Puck if it isn't one), so the same field serves both.
    const SARVAM_SPEAKERS_BY_LANG = {
        "hi-IN": ["shubh", "ashutosh", "priya", "suhani"],
        "en-IN": ["ratan", "ishita"],
        "bn-IN": ["rehan", "roopa", "suhani"],
        "ta-IN": ["ratan", "rohan", "ishita", "ritu"],
        "te-IN": ["shubh", "ratan", "neha", "priya"],
        "kn-IN": ["shubh", "ratan", "neha", "ishita"],
        "ml-IN": ["shubh", "pooja"],
        "mr-IN": ["ratan", "priya", "ritu"],
        "gu-IN": ["ratan", "priya", "ritu"],
        "pa-IN": ["mani", "roopa", "suhani"],
        "od-IN": ["shubh", "ritu", "pooja"],
    };
    const GEMINI_VOICES = ["Puck", "Charon", "Kore", "Fenrir", "Aoede", "Zephyr", "Lyra", "Orion", "Callisto", "Nova"];
    const EDGE_VOICES_BY_LANG = {
        "hi-IN": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
        "en-IN": ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"],
        "bn-IN": ["bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"],
        "ta-IN": ["ta-IN-PallaviNeural", "ta-IN-ValluvarNeural"],
        "te-IN": ["te-IN-ShrutiNeural", "te-IN-MohanNeural"],
    };
    const LOCAL_VOICES_BY_LANG = {
        "hi-IN": ["hf_alpha", "hm_omega", "hf_beta", "hm_psi"],
        "en-IN": ["af_heart", "am_michael", "bf_emma", "bm_george"],
    };

    function updateSpeakerOptions() {
        if (!speakerSelect) return;
        const provider = ttsProviderSelect ? ttsProviderSelect.value : "sarvam";
        const lang = languageSelect ? languageSelect.value : "hi-IN";
        const prev = speakerSelect.value;
        let voices = ["shubh"];
        if (provider === "gemini") {
            voices = GEMINI_VOICES;
        } else if (provider === "edge") {
            voices = EDGE_VOICES_BY_LANG[lang] || EDGE_VOICES_BY_LANG["hi-IN"] || ["hi-IN-SwaraNeural"];
        } else if (provider === "local" || provider === "kokoro") {
            voices = LOCAL_VOICES_BY_LANG[lang] || (lang && lang.startsWith("en") ? LOCAL_VOICES_BY_LANG["en-IN"] : LOCAL_VOICES_BY_LANG["hi-IN"]) || ["af_heart"];
        } else {
            voices = SARVAM_SPEAKERS_BY_LANG[lang] || ["shubh"];
        }
        speakerSelect.innerHTML = voices
            .map((v) => `<option value="${v}">${v}</option>`)
            .join("");
        // Keep the prior pick if it's still valid, else default to the first option.
        if (voices.includes(prev)) speakerSelect.value = prev;
    }
    if (languageSelect) languageSelect.addEventListener("change", updateSpeakerOptions);
    if (ttsProviderSelect) ttsProviderSelect.addEventListener("change", updateSpeakerOptions);
    updateSpeakerOptions();

    // Collect the narration/language knobs the storyboard + code endpoints accept.
    function narrationParams() {
        return {
            persona: personaSelect ? personaSelect.value : "hybrid",
            // How technical terms are spoken: english (never re-said in the native
            // language), bilingual (native equivalent once), native (translated).
            // Only the storyboard endpoint reads it; the others ignore the extra field.
            tech_terms: techTermsSelect ? techTermsSelect.value : "english",
            language: languageSelect ? languageSelect.value : "hi-IN",
            speaker: speakerSelect ? speakerSelect.value : "shubh",
            tts_provider: ttsProviderSelect ? ttsProviderSelect.value : "sarvam",
        };
    }

    // --- Generate Click Handler ---
    btnGenerate.addEventListener("click", async () => {
        const topic = topicInput.value.trim();
        const style = styleSelect.value;
        const key = apiKeyInput.value.trim();
        
        if (!topic) {
            showToast("Please enter a STEM topic", "error");
            return;
        }

        // Set Loading
        btnGenerate.disabled = true;
        btnLoader.classList.remove("hidden");
        
        try {
            if (currentMode === "creator") {
                log(`Starting Content Creator workflow for topic: "${topic}"...`);
                switchTab("json-view");
                
                // 1. Generate Storyboard JSON
                log("Calling Storyboard Creator Agent to generate animation plan...");
                const ytUrl = ytUrlInput.value.trim();
                const requestBody = { topic, style, background: backgroundSelect.value, ...narrationParams() };
                if (ytUrl) {
                    requestBody.context = { youtube_url: ytUrl };
                }
                const response = await fetch("/api/generate_storyboard", {
                    method: "POST",
                    headers: getHeaders(),
                    body: JSON.stringify(requestBody)
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || err.error || "Failed to generate storyboard");
                }
                
                storyboardData = await response.json();
                log("Storyboard JSON generated successfully!");

                // Show JSON
                jsonEmpty.classList.add("hidden");
                jsonBox.classList.remove("hidden");
                jsonCode.textContent = JSON.stringify(storyboardData, null, 2);
                renderNonManinItems(storyboardData.non_manim_items || []);

                // Pre-flight: probe all svg_icon + chemical_molecule assets in parallel,
                // then build the consolidated issues list
                log("Running pre-flight asset check (probing SVG icons and molecules)...");
                try {
                    const [pfResp, issuesResp] = await Promise.all([
                        fetch("/api/preflight_assets", {
                            method: "POST", headers: getHeaders(),
                            body: JSON.stringify({ storyboard: storyboardData })
                        }),
                        fetch("/api/asset_issues", {
                            method: "POST", headers: getHeaders(),
                            body: JSON.stringify({ storyboard: storyboardData })
                        })
                    ]);
                    if (pfResp.ok) {
                        const pfData = await pfResp.json();
                        renderPreflightItems(pfData);
                        if (pfData.fallback_count > 0) {
                            log(`Pre-flight: ${pfData.resolved}/${pfData.total} assets resolved. ${pfData.fallback_count} will fall back to native shapes.`, "warn");
                        } else if (pfData.total > 0) {
                            log(`Pre-flight: all ${pfData.total} assets resolved successfully.`);
                        }
                    }
                    if (issuesResp.ok) {
                        const issuesData = await issuesResp.json();
                        renderAssetIssues(issuesData);
                        if (issuesData.counts.total > 0) {
                            log(`Asset issues: ${issuesData.counts.missing} missing, ${issuesData.counts.fallback} degraded — see the issues panel.`, "warn");
                        }
                    }
                } catch (pfErr) {
                    log(`Pre-flight check skipped: ${pfErr.message}`, "warn");
                }

                // 2. Translate Storyboard to Python Manim Code
                log("Translating Storyboard JSON into Python Manim script...");
                switchTab("code-view");
                
                const codeResponse = await fetch("/api/generate_code", {
                    method: "POST",
                    headers: getHeaders(),
                    body: JSON.stringify({ storyboard: storyboardData, style, background: backgroundSelect.value, ...narrationParams() })
                });
                
                if (!codeResponse.ok) {
                    const err = await codeResponse.json();
                    throw new Error(err.detail || err.error || "Failed to translate storyboard to code");
                }
                
                const codeData = await codeResponse.json();
                generatedCode = codeData.code;
                const sceneClass = codeData.scene_class || "STEMAnimation";
                if (codeData.valid === false) {
                    log(`Warning: generated code still has a syntax issue after auto-repair: ${codeData.validation_error}`, "error");
                } else {
                    log("Manim Python script created and validated successfully!");
                }

                // Show Python script
                codeEmpty.classList.add("hidden");
                codeBox.classList.remove("hidden");
                pythonCodeTextarea.value = generatedCode;

                // 3. Compile Python Script to Video
                log("Triggering video compilation. Please wait...");
                switchTab("video-view");

                await compileVideo(generatedCode, sceneClass, codeData.scene_scripts);
                
            } else {
                // Student Portal mode
                const interest = interestInput.value.trim();
                if (!interest) {
                    showToast("Please enter a student interest", "error");
                    btnGenerate.disabled = false;
                    btnLoader.classList.add("hidden");
                    return;
                }
                
                log(`Starting Student Portal workflow on topic: "${topic}" for interest: "${interest}"...`);
                switchTab("slides-view");
                tabSlidesBtn.textContent = "Personalized Slides";
                
                log("Calling Slide Creator Agent to generate personalized student course slides...");
                const response = await fetch("/api/generate_student_slides", {
                    method: "POST",
                    headers: getHeaders(),
                    body: JSON.stringify({ topic, interest, style, background: backgroundSelect.value })
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || err.error || "Failed to generate course slides");
                }
                
                const data = await response.json();
                currentSlides = data.slides || [];
                activeSlideIndex = 0;
                log(`Successfully generated ${currentSlides.length} educational slides!`);
                
                if (currentSlides.length > 0) {
                    slidesEmpty.classList.add("hidden");
                    slidesDeck.classList.remove("hidden");
                    renderSlide(activeSlideIndex);
                    showToast("Personalized course created!", "success");
                } else {
                    throw new Error("No slides returned by the model");
                }
            }
        } catch (error) {
            log(`Error: ${error.message}`, "error");
            showToast(error.message, "error");
        } finally {
            btnGenerate.disabled = false;
            btnLoader.classList.add("hidden");
        }
    });

    // --- Video Compilation execution ---
    async function compileVideo(code, sceneClass, sceneScripts) {
        const quality = qualitySelect.value;
        videoEmpty.classList.add("hidden");
        videoBox.classList.add("hidden");
        
        log(`Compiling Manim scene class '${sceneClass}' [Quality: ${quality.toUpperCase()}]...`);
        showToast("Compiling video with Manim...", "success");
        
        try {
            const aspect = aspectSelect ? aspectSelect.value : "widescreen";
            // Enqueue the render job, then poll for completion (renders no longer block the request).
            const response = await fetch("/api/compile_video", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // scene_scripts unlock the server's parallel per-scene render +
                // scene-scoped repair; without them every render takes the slow
                // sequential single-script path.
                body: JSON.stringify({ code, scene_class: sceneClass, quality, aspect_ratio: aspect, persona: (personaSelect ? personaSelect.value : "hybrid"), scene_scripts: (Array.isArray(sceneScripts) && sceneScripts.length > 1) ? sceneScripts : null })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || err.error || "Network error during compilation");
            }

            const { job_id } = await response.json();
            log(`Render job queued (id: ${job_id}). Waiting for completion...`);
            const result = await pollRenderJob(job_id);

            // Print compiler output logs to the console pane
            if (result.logs) {
                log("\n--- MANIM COMPILER LOGS ---", "system");
                const lines = result.logs.split("\n");
                lines.forEach(line => {
                    if (line.trim()) {
                        if (line.includes("Error") || line.includes("Traceback") || line.includes("Exception")) {
                            log(line, "error");
                        } else {
                            log(line, "system");
                        }
                    }
                });
                log("---------------------------\n", "system");
            }
            
            if (result.success && result.video_url) {
                log("Manim video compilation completed successfully!");
                showToast("Video rendered successfully!", "success");
                
                videoEmpty.classList.add("hidden");
                videoBox.classList.remove("hidden");
                
                // Update HTML video element
                manimVideo.src = result.video_url;
                manimVideo.load();
                manimVideo.play().catch(e => log(`Autoplay blocked: ${e.message}`, "system"));
            } else {
                throw new Error("Manim compilation failed. Review the compiler logs below.");
            }
        } catch (error) {
            log(error.message, "error");
            showToast(error.message, "error");
            videoEmpty.classList.remove("hidden");
            videoBox.classList.add("hidden");
            // Switch back to code view so the user can fix errors
            switchTab("code-view");
        }
    }

    // Poll a queued render job until it finishes or errors out.
    async function pollRenderJob(jobId, intervalMs = 2000) {
        let elapsed = 0;
        while (true) {
            await new Promise(r => setTimeout(r, intervalMs));
            elapsed += intervalMs;
            const resp = await fetch(`/api/render_status/${jobId}`);
            if (!resp.ok) {
                throw new Error("Lost track of the render job (status not found).");
            }
            const job = await resp.json();
            if (job.state === "done" || job.state === "error") {
                return job;
            }
            // Light heartbeat so long renders don't look frozen.
            if (elapsed % 10000 === 0) {
                log(`Still rendering... (${Math.round(elapsed / 1000)}s elapsed)`, "system");
            }
        }
    }

    // --- Compile Custom Script Button ---
    btnCompileCustom.addEventListener("click", async () => {
        const code = pythonCodeTextarea.value.trim();
        if (!code) {
            showToast("No Python code available to compile", "error");
            return;
        }
        
        // Disable button
        btnCompileCustom.disabled = true;
        log("Compiling custom Python Manim code edits...");
        switchTab("video-view");
        
        try {
            await compileVideo(code, "STEMAnimation");
        } finally {
            btnCompileCustom.disabled = false;
        }
    });

    // --- Copy Button logic ---
    document.querySelectorAll(".btn-copy").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.dataset.target;
            const element = document.getElementById(targetId);
            const textToCopy = element.tagName === "TEXTAREA" ? element.value : element.textContent;
            
            navigator.clipboard.writeText(textToCopy)
                .then(() => showToast("Copied to clipboard!", "success"))
                .catch(() => showToast("Failed to copy text", "error"));
        });
    });

    // --- Slide Deck Rendering & Interactive Simulation ---
    function renderSlide(index) {
        if (!currentSlides[index]) return;
        const slide = currentSlides[index];
        activeSlideIndex = index;
        
        // Reset container
        currentSlideContainer.innerHTML = "";
        
        const card = document.createElement("div");
        card.className = "slide-card";
        
        // Slide badge
        const badge = document.createElement("div");
        badge.className = "slide-badge";
        badge.textContent = `Slide ${slide.slide_index} of ${currentSlides.length}`;
        card.appendChild(badge);
        
        // Title
        const title = document.createElement("h2");
        title.textContent = slide.title;
        card.appendChild(title);
        
        // Personalized Hook block
        const hookBlock = document.createElement("div");
        hookBlock.className = "section-block hook-box";
        hookBlock.innerHTML = `
            <div class="section-title">⚡ Interactive Hook (Student's Interest)</div>
            <div class="section-content">${slide.hook}</div>
        `;
        card.appendChild(hookBlock);
        
        // Full explanation
        const explBlock = document.createElement("div");
        explBlock.className = "section-block";
        explBlock.innerHTML = `
            <div class="section-title">📘 Concept Explanation</div>
            <div class="section-content">${slide.explanation}</div>
        `;
        card.appendChild(explBlock);
        
        // Dynamic Simulation widget
        const simBlock = document.createElement("div");
        simBlock.className = "section-block";
        
        const simTitle = document.createElement("div");
        simTitle.className = "section-title";
        simTitle.textContent = "🎮 Interactive Hook Simulation";
        simBlock.appendChild(simTitle);
        
        const simDesc = document.createElement("div");
        simDesc.className = "section-content";
        simDesc.style.marginBottom = "8px";
        simDesc.textContent = slide.hook_simulation;
        simBlock.appendChild(simDesc);
        
        // Interactive widget container. Primary path: an AI-generated, self-contained
        // simulation rendered inside a sandboxed iframe. Fallback: the built-in keyword
        // sims rendered into canvasMock/controlsRow if generation fails.
        const simWidget = document.createElement("div");
        simWidget.className = "simulation-widget";

        const simFrame = document.createElement("iframe");
        simFrame.className = "simulation-iframe";
        // No allow-same-origin => the widget runs in an opaque origin and cannot reach the host page.
        simFrame.setAttribute("sandbox", "allow-scripts");
        simFrame.setAttribute("title", "Interactive simulation");
        simWidget.appendChild(simFrame);

        const canvasMock = document.createElement("div");
        canvasMock.className = "simulation-canvas-mock";
        canvasMock.id = `sim-canvas-${index}`;
        canvasMock.style.display = "none";
        simWidget.appendChild(canvasMock);

        const controlsRow = document.createElement("div");
        controlsRow.className = "simulation-controls-row";
        controlsRow.id = `sim-controls-${index}`;
        controlsRow.style.display = "none";
        simWidget.appendChild(controlsRow);

        const btnRegenSim = document.createElement("button");
        btnRegenSim.className = "btn btn-secondary btn-regen-sim";
        btnRegenSim.textContent = "↻ Regenerate Simulation";
        btnRegenSim.addEventListener("click", () => {
            slide._simHtml = null;
            loadInteractiveSim(slide, simFrame, canvasMock, controlsRow);
        });
        simWidget.appendChild(btnRegenSim);

        simBlock.appendChild(simWidget);
        card.appendChild(simBlock);
        
        // Image Prompt Box
        const promptBlock = document.createElement("div");
        promptBlock.className = "section-block prompt-box";
        promptBlock.innerHTML = `
            <div class="section-title" style="color: var(--accent-amber)">🎨 Midjourney/DALL-E Prompt</div>
            <div class="section-content">${slide.image_prompt}</div>
        `;
        card.appendChild(promptBlock);
        
        // Slide action buttons: Compile Animation & View Python code
        const actionsBlock = document.createElement("div");
        actionsBlock.className = "slide-actions";
        
        const btnViewCode = document.createElement("button");
        btnViewCode.className = "btn btn-secondary";
        btnViewCode.textContent = "View Manim Code";
        btnViewCode.addEventListener("click", () => {
            codeEmpty.classList.add("hidden");
            codeBox.classList.remove("hidden");
            pythonCodeTextarea.value = slide.manim_code;
            showToast("Manim code loaded in editor tab!", "success");
            switchTab("code-view");
        });
        
        const btnPlayAnimation = document.createElement("button");
        btnPlayAnimation.className = "btn btn-primary";
        btnPlayAnimation.innerHTML = `<span>Compile Animation Video</span><span class="btn-loader hidden"></span>`;
        btnPlayAnimation.addEventListener("click", async () => {
            btnPlayAnimation.disabled = true;
            btnPlayAnimation.querySelector(".btn-loader").classList.remove("hidden");
            switchTab("video-view");
            try {
                await compileVideo(slide.manim_code, slide.scene_class || "SlideAnimation");
            } finally {
                btnPlayAnimation.disabled = false;
                btnPlayAnimation.querySelector(".btn-loader").classList.add("hidden");
            }
        });
        
        actionsBlock.appendChild(btnViewCode);
        actionsBlock.appendChild(btnPlayAnimation);
        card.appendChild(actionsBlock);
        
        // Inject card to DOM
        currentSlideContainer.appendChild(card);

        // Load the interactive simulation (AI-generated widget, built-in fallback).
        loadInteractiveSim(slide, simFrame, canvasMock, controlsRow);

        // Update Dots
        updateCarouselDots();
    }

    // Render a placeholder document inside the sim iframe.
    function simPlaceholder(message) {
        return `<!DOCTYPE html><html><head><meta charset="utf-8">
            <style>html,body{margin:0;height:100%}body{display:flex;align-items:center;justify-content:center;
            background:#020205;color:#9ca3af;font-family:system-ui,sans-serif;font-size:13px;text-align:center;padding:12px}</style>
            </head><body><div>${message}</div></body></html>`;
    }

    // Fetch (or reuse cached) AI-generated simulation HTML and render it in the iframe.
    // On failure, fall back to the built-in keyword simulation rendered into the div.
    async function loadInteractiveSim(slide, frame, canvasMock, controlsRow) {
        frame.style.display = "block";
        canvasMock.style.display = "none";
        controlsRow.style.display = "none";

        if (slide._simHtml) {
            frame.srcdoc = slide._simHtml;
            return;
        }

        frame.srcdoc = simPlaceholder("Generating interactive simulation…");
        try {
            const resp = await fetch("/api/generate_sim", {
                method: "POST",
                headers: getHeaders(),
                body: JSON.stringify({
                    topic: topicInput.value.trim(),
                    interest: interestInput.value.trim(),
                    hook_simulation: slide.hook_simulation || ""
                })
            });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || err.error || "Simulation generation failed");
            }
            const data = await resp.json();
            slide._simHtml = data.html;
            frame.srcdoc = data.html;
            log("Interactive simulation generated.");
        } catch (error) {
            log(`Sim generation failed — using built-in fallback: ${error.message}`, "system");
            // Fall back to the deterministic built-in sims.
            frame.style.display = "none";
            canvasMock.style.display = "flex";
            controlsRow.style.display = "flex";
            setupInteractiveSimulation(
                canvasMock, controlsRow,
                topicInput.value.trim().toLowerCase(),
                interestInput.value.trim().toLowerCase()
            );
        }
    }

    // Carousel buttons
    slidePrev.addEventListener("click", () => {
        if (activeSlideIndex > 0) {
            renderSlide(activeSlideIndex - 1);
        }
    });

    slideNext.addEventListener("click", () => {
        if (activeSlideIndex < currentSlides.length - 1) {
            renderSlide(activeSlideIndex + 1);
        }
    });

    function updateCarouselDots() {
        slideDots.innerHTML = "";
        currentSlides.forEach((_, idx) => {
            const dot = document.createElement("div");
            dot.className = `carousel-dot ${idx === activeSlideIndex ? 'active' : ''}`;
            dot.addEventListener("click", () => renderSlide(idx));
            slideDots.appendChild(dot);
        });
    }

    // --- Interactive Simulation Engines inside Slides ---
    function setupInteractiveSimulation(canvasContainer, controlsContainer, topic, interest) {
        // Detect topic categories
        if (topic.includes("pythagorean") || topic.includes("triangle")) {
            renderPythagoreanSim(canvasContainer, controlsContainer);
        } else if (topic.includes("gravit") || topic.includes("gravity") || topic.includes("force")) {
            renderGravitySim(canvasContainer, controlsContainer, interest);
        } else if (topic.includes("splicing") || topic.includes("dna") || topic.includes("rna") || topic.includes("gene")) {
            renderGeneSplicingSim(canvasContainer, controlsContainer);
        } else {
            // Default: Harmonic wave frequency plotter
            renderWaveSim(canvasContainer, controlsContainer);
        }
    }

    // 1. Right Triangle Pythagorean Simulator
    function renderPythagoreanSim(canvas, controls) {
        canvas.innerHTML = `
            <svg id="py-svg" width="100%" height="100%" viewBox="0 0 400 130" style="background:#020205;">
                <polygon id="triangle" points="180,110 180,30 260,110" fill="none" stroke="#8b5cf6" stroke-width="2" />
                <line points="172,110 172,102 180,102" fill="none" stroke="#9ca3af" stroke-width="1" />
                <text id="side-a" x="155" y="75" fill="#00ffcc" font-size="10" font-family="sans-serif">a = 40</text>
                <text id="side-b" x="215" y="122" fill="#8b5cf6" font-size="10" font-family="sans-serif">b = 40</text>
                <text id="side-c" x="225" y="65" fill="#f59e0b" font-size="10" font-family="sans-serif">c = 56.6</text>
                <text id="calc-text" x="10" y="25" fill="#ffffff" font-size="9" font-family="monospace">a² + b² = c²</text>
                <text id="calc-vals" x="10" y="45" fill="#a7f3d0" font-size="9" font-family="monospace">40² + 40² = 3200</text>
            </svg>
        `;
        
        controls.innerHTML = `
            <div style="flex:1; display:flex; flex-direction:column; gap:4px;">
                <label>Side A (Vertical): <span id="val-a">40</span></label>
                <input type="range" id="slider-a" min="20" max="80" value="40">
            </div>
            <div style="flex:1; display:flex; flex-direction:column; gap:4px;">
                <label>Side B (Horizontal): <span id="val-b">40</span></label>
                <input type="range" id="slider-b" min="20" max="80" value="40">
            </div>
        `;
        
        const sliderA = controls.querySelector("#slider-a");
        const sliderB = controls.querySelector("#slider-b");
        const valA = controls.querySelector("#val-a");
        const valB = controls.querySelector("#val-b");
        const triangle = canvas.querySelector("#triangle");
        const textA = canvas.querySelector("#side-a");
        const textB = canvas.querySelector("#side-b");
        const textC = canvas.querySelector("#side-c");
        const calcText = canvas.querySelector("#calc-vals");
        
        function updateTriangle() {
            const a = parseInt(sliderA.value);
            const b = parseInt(sliderB.value);
            valA.textContent = a;
            valB.textContent = b;
            
            const startX = 180;
            const startY = 110;
            const topY = startY - a;
            const rightX = startX + b;
            
            triangle.setAttribute("points", `${startX},${startY} ${startX},${topY} ${rightX},${startY}`);
            
            // Reposition texts
            textA.setAttribute("y", (startY + topY) / 2);
            textA.setAttribute("x", startX - 30);
            textA.textContent = `a = ${a}`;
            
            textB.setAttribute("x", (startX + rightX) / 2 - 10);
            textB.textContent = `b = ${b}`;
            
            const hyp = Math.sqrt(a*a + b*b).toFixed(1);
            textC.setAttribute("x", (startX + rightX) / 2 + 10);
            textC.setAttribute("y", (startY + topY) / 2 - 10);
            textC.textContent = `c = ${hyp}`;
            
            calcText.textContent = `${a}² + ${b}² = ${(a*a + b*b)} = ${hyp}²`;
        }
        
        sliderA.addEventListener("input", updateTriangle);
        sliderB.addEventListener("input", updateTriangle);
        updateTriangle();
    }

    // 2. Gravitational Physics dropping simulator (e.g. Minecraft style)
    function renderGravitySim(canvas, controls, interest) {
        let isMinecraft = interest.includes("mine");
        let ballColor = isMinecraft ? "#ef4444" : "#00ffcc";
        
        canvas.innerHTML = `
            <div style="position:relative; width:100%; height:100%; overflow:hidden; background:#010103;">
                <div id="ground" style="position:absolute; bottom:0; left:0; width:100%; height:20px; background:${isMinecraft ? '#4b5320' : '#111827'}; border-top:1px solid ${isMinecraft ? '#8b5cf6' : '#374151'}"></div>
                <div id="drop-object" style="position:absolute; width:24px; height:24px; background:${ballColor}; border-radius:${isMinecraft ? '4px' : '50%'}; left:45%; top:10px; box-shadow:0 0 10px ${ballColor}; display:flex; align-items:center; justify-content:center; font-size:12px;">
                    ${isMinecraft ? '📦' : ''}
                </div>
                <div id="telemetry" style="position:absolute; top:8px; left:8px; font-family:monospace; font-size:8.5px; color:#a7f3d0;">
                    Y: <span id="tel-y">100.0</span>m<br>
                    Vy: <span id="tel-vy">0.0</span>m/s<br>
                    t: <span id="tel-t">0.0</span>s
                </div>
            </div>
        `;
        
        controls.innerHTML = `
            <div style="flex:2; display:flex; flex-direction:column; gap:4px;">
                <label>Gravity acceleration (g): <span id="gravity-val">9.8</span> m/s²</label>
                <input type="range" id="slider-g" min="2" max="25" value="10" step="0.5">
            </div>
            <button class="btn btn-secondary" id="btn-drop" style="flex:1; padding:4px 8px; font-size:0.8rem;">Drop Object</button>
        `;
        
        const sliderG = controls.querySelector("#slider-g");
        const gravityVal = controls.querySelector("#gravity-val");
        const btnDrop = controls.querySelector("#btn-drop");
        const obj = canvas.querySelector("#drop-object");
        const telY = canvas.querySelector("#tel-y");
        const telVy = canvas.querySelector("#tel-vy");
        const telT = canvas.querySelector("#tel-t");
        
        let position = 10; // offset in px from top
        let velocity = 0;
        let time = 0;
        let animId = null;
        
        sliderG.addEventListener("input", () => {
            gravityVal.textContent = sliderG.value;
        });
        
        function runPhysics() {
            const g = parseFloat(sliderG.value);
            const groundLimit = 130 - 24 - 20; // Container height is 130, minus ground, minus box
            const dt = 0.05; // 20 updates per sec approx
            
            if (position < groundLimit) {
                time += dt;
                velocity += g * dt;
                position += velocity * dt * 8; // scaling factor
                
                if (position >= groundLimit) {
                    position = groundLimit;
                    velocity = 0;
                    cancelAnimationFrame(animId);
                    animId = null;
                    btnDrop.disabled = false;
                } else {
                    animId = requestAnimationFrame(runPhysics);
                }
                
                obj.style.top = position + "px";
                telY.textContent = ((groundLimit - position) / 10).toFixed(1);
                telVy.textContent = velocity.toFixed(1);
                telT.textContent = time.toFixed(2);
            }
        }
        
        btnDrop.addEventListener("click", () => {
            btnDrop.disabled = true;
            position = 10;
            velocity = 0;
            time = 0;
            obj.style.top = "10px";
            if (animId) cancelAnimationFrame(animId);
            animId = requestAnimationFrame(runPhysics);
        });
    }

    // 3. DNA splicing simulator
    function renderGeneSplicingSim(canvas, controls) {
        canvas.innerHTML = `
            <div style="width:100%; height:100%; background:#000; padding:12px; display:flex; flex-direction:column; justify-content:center; gap:8px;">
                <div style="font-size:0.75rem; color:#8b5cf6; font-family:monospace; display:flex; gap:2px; justify-content:center;" id="pre-mrna">
                    <span style="color:#00ffcc">[Exon1: AUG]</span>
                    <span id="intron-span" style="background:rgba(239, 68, 68, 0.2); border:1px dashed #ef4444; padding:0 2px;">[Intron: UUAGCC]</span>
                    <span style="color:#00ffcc">[Exon2: GACUAA]</span>
                </div>
                <div style="display:flex; justify-content:center; align-items:center; font-size:1.5rem; color:#f59e0b;" id="splice-arrow">
                    ✂
                </div>
                <div style="font-size:0.75rem; color:#00ffcc; font-family:monospace; text-align:center;" id="mature-mrna">
                    Waiting for splice operation...
                </div>
            </div>
        `;
        
        controls.innerHTML = `
            <button class="btn btn-primary" id="btn-splice" style="width:100%; padding:6px 12px; font-size:0.8rem;">Cut Introns (Splicing)</button>
        `;
        
        const btnSplice = controls.querySelector("#btn-splice");
        const intron = canvas.querySelector("#intron-span");
        const arrow = canvas.querySelector("#splice-arrow");
        const mature = canvas.querySelector("#mature-mrna");
        
        btnSplice.addEventListener("click", () => {
            intron.style.display = "none";
            arrow.textContent = "✓ Spliced!";
            mature.innerHTML = `
                <strong style="color:#f59e0b">Mature mRNA:</strong> AUG - GACUAA 
                <br><span style="font-size:0.65rem; color:var(--text-secondary)">(Translated Protein: Met - Asp)</span>
            `;
            btnSplice.disabled = true;
        });
    }

    // 4. Default: Wave Plotter (Interactive Frequency/Amplitude)
    function renderWaveSim(canvas, controls) {
        canvas.innerHTML = `
            <svg id="wave-svg" width="100%" height="100%" viewBox="0 0 400 130" style="background:#020205;">
                <line x1="10" y1="65" x2="390" y2="65" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
                <path id="wave-path" d="" fill="none" stroke="#00ffcc" stroke-width="2" />
                <path id="derivative-path" d="" fill="none" stroke="#f59e0b" stroke-dasharray="3,3" stroke-width="1.5" />
                <legend x="20" y="20">
                    <text x="20" y="20" fill="#00ffcc" font-size="8" font-family="monospace">y = A * sin(f * x)</text>
                    <text x="140" y="20" fill="#f59e0b" font-size="8" font-family="monospace">dy/dx = A * f * cos(f * x) [Derivative]</text>
                </legend>
            </svg>
        `;
        
        controls.innerHTML = `
            <div style="flex:1; display:flex; flex-direction:column; gap:4px;">
                <label>Amplitude (A): <span id="val-amp">30</span></label>
                <input type="range" id="slider-amp" min="10" max="50" value="30">
            </div>
            <div style="flex:1; display:flex; flex-direction:column; gap:4px;">
                <label>Frequency (f): <span id="val-freq">4</span></label>
                <input type="range" id="slider-freq" min="1" max="10" value="4">
            </div>
        `;
        
        const sliderAmp = controls.querySelector("#slider-amp");
        const sliderFreq = controls.querySelector("#slider-freq");
        const valAmp = controls.querySelector("#val-amp");
        const valFreq = controls.querySelector("#val-freq");
        const wavePath = canvas.querySelector("#wave-path");
        const derivPath = canvas.querySelector("#derivative-path");
        
        function plotWave() {
            const amp = parseInt(sliderAmp.value);
            const freq = parseInt(sliderFreq.value) / 20; // scale down for graph
            valAmp.textContent = sliderAmp.value;
            valFreq.textContent = sliderFreq.value;
            
            let dWave = "";
            let dDeriv = "";
            const centerY = 65;
            
            for (let x = 10; x <= 390; x++) {
                const angle = (x - 10) * freq;
                const y = centerY - amp * Math.sin(angle);
                
                // dy/dx is cosine
                const dy = centerY - (amp * freq * 15) * Math.cos(angle);
                
                if (x === 10) {
                    dWave = `M ${x} ${y}`;
                    dDeriv = `M ${x} ${dy}`;
                } else {
                    dWave += ` L ${x} ${y}`;
                    dDeriv += ` L ${x} ${dy}`;
                }
            }
            
            wavePath.setAttribute("d", dWave);
            derivPath.setAttribute("d", dDeriv);
        }
        
        sliderAmp.addEventListener("input", plotWave);
        sliderFreq.addEventListener("input", plotWave);
        plotWave();
    }

    function renderAssetIssues(data) {
        _issuesData = data;
        const { counts, issues } = data;
        if (!counts.total) { issuesPanel.classList.add("hidden"); return; }

        issuesPanel.classList.remove("hidden");
        issuesSummary.textContent =
            `${counts.total} asset issue${counts.total > 1 ? "s" : ""} — ` +
            `🔴 ${counts.missing} missing  ·  🟡 ${counts.fallback} degraded`;

        const TIER_BADGE = {
            missing:  `<span style="background:#450a0a;border:1px solid #7f1d1d;color:#f87171;border-radius:4px;padding:2px 7px;font-size:11px;">🔴 Missing</span>`,
            fallback: `<span style="background:#451a03;border:1px solid #92400e;color:#fbbf24;border-radius:4px;padding:2px 7px;font-size:11px;">🟡 Degraded</span>`,
        };

        issuesRows.innerHTML = issues.map(item => `
            <tr style="border-bottom:1px solid #2a2a2a;vertical-align:top;">
                <td style="padding:6px 8px;white-space:nowrap;color:#f87171;">Scene ${escapeHtml(String(item.scene))}</td>
                <td style="padding:6px 8px;">${TIER_BADGE[item.tier] || item.tier}</td>
                <td style="padding:6px 8px;white-space:nowrap;">
                    <code style="font-size:11px;color:#a3a3a3;">${escapeHtml(item.element_type)}</code>
                    ${item.element_id ? `<br><span style="color:#525252;font-size:10px;">${escapeHtml(item.element_id)}</span>` : ""}
                </td>
                <td style="padding:6px 8px;color:#e5e5e5;max-width:260px;word-break:break-word;">${escapeHtml(item.description)}</td>
                <td style="padding:6px 8px;color:#86efac;font-style:italic;">${escapeHtml(item.action)}</td>
            </tr>
        `).join("");

        // Auto-open
        issuesBody.style.display = "block";
        issuesToggle.textContent = "▲ hide";
    }

    function renderPreflightItems(pfData) {
        const { total, resolved, fallback_count, items } = pfData;
        if (!total) { preflightPanel.classList.add("hidden"); return; }

        preflightPanel.classList.remove("hidden");
        const allGood = fallback_count === 0;
        preflightSummary.textContent = allGood
            ? `Pre-flight: ${total}/${total} assets resolved`
            : `Pre-flight: ${resolved}/${total} resolved — ${fallback_count} fallback${fallback_count > 1 ? "s" : ""} (will render as native shapes)`;
        preflightSummary.style.color = allGood ? "#4ade80" : "#fbbf24";
        preflightPanel.style.borderColor = allGood ? "#22c55e" : "#f59e0b";
        document.getElementById("preflight-header").style.background = allGood ? "#14532d22" : "#78350f22";

        preflightRows.innerHTML = items.map((item, idx) => {
            const resolved = item.status === "resolved";
            const badge = resolved
                ? `<span style="background:#14532d;border:1px solid #166534;color:#4ade80;border-radius:4px;padding:2px 7px;font-size:11px;">✅ ${escapeHtml(item.provider)}${item.icon_id ? ` · ${escapeHtml(item.icon_id)}` : ""}</span>`
                : `<span style="background:#451a03;border:1px solid #92400e;color:#fbbf24;border-radius:4px;padding:2px 7px;font-size:11px;">⚠️ fallback → native shape</span>`;

            const fixRow = resolved ? "" : `
                <div style="display:flex;gap:6px;margin-top:6px;align-items:center;">
                    <input id="pf-input-${idx}" type="text" value="${escapeHtml(item.keyword)}"
                        style="flex:1;background:#292524;border:1px solid #44403c;border-radius:4px;color:#e5e5e5;
                               font-size:11px;padding:3px 7px;outline:none;"
                        placeholder="Try a simpler keyword…" />
                    <button id="pf-btn-${idx}"
                        style="background:#1d4ed8;color:#fff;border:none;border-radius:4px;
                               padding:3px 10px;font-size:11px;cursor:pointer;white-space:nowrap;">
                        Re-test
                    </button>
                </div>`;

            return `<tr id="pf-row-${idx}" style="border-bottom:1px solid #2a2a2a;vertical-align:top;">
                <td style="padding:6px 8px;white-space:nowrap;color:#60a5fa;">Scene ${escapeHtml(String(item.scene))}</td>
                <td style="padding:6px 8px;white-space:nowrap;">
                    <span style="background:#292524;border:1px solid #44403c;border-radius:4px;padding:2px 6px;font-size:11px;">
                        ${escapeHtml(item.type)}
                    </span>
                    ${item.element_id ? `<br><span style="color:#737373;font-size:10px;">${escapeHtml(item.element_id)}</span>` : ""}
                </td>
                <td style="padding:6px 8px;">
                    <code style="color:#d4d4d4;font-size:11px;">${escapeHtml(item.keyword)}</code>
                    ${fixRow}
                </td>
                <td style="padding:6px 8px;">${badge}</td>
            </tr>`;
        }).join("");

        // Auto-open if any fallbacks
        if (fallback_count > 0) {
            preflightBody.style.display = "block";
            preflightToggle.textContent = "▲ hide";
        }

        // Wire up Re-test buttons
        items.forEach((item, idx) => {
            if (item.status === "resolved") return;
            const btn = document.getElementById(`pf-btn-${idx}`);
            const inp = document.getElementById(`pf-input-${idx}`);
            if (!btn || !inp) return;

            btn.addEventListener("click", async () => {
                const newKeyword = inp.value.trim();
                if (!newKeyword) return;
                btn.textContent = "…";
                btn.disabled = true;
                try {
                    const r = await fetch("/api/probe_asset", {
                        method: "POST",
                        headers: { ...getHeaders(), "Content-Type": "application/json" },
                        body: JSON.stringify({ type: item.type, keyword: newKeyword })
                    });
                    const result = await r.json();
                    const row = document.getElementById(`pf-row-${idx}`);
                    if (result.status === "resolved") {
                        // Patch storyboardData in memory so codegen uses the fixed keyword
                        const scenes = (storyboardData.visual_storyboard || []);
                        for (const scene of scenes) {
                            if (String(scene.scene_index) !== String(item.scene)) continue;
                            for (const elem of (scene.elements || [])) {
                                if (elem.id === item.element_id) { elem.content = newKeyword; break; }
                            }
                        }
                        item.keyword = newKeyword;
                        item.status = "resolved";
                        item.provider = result.provider;
                        item.icon_id = result.icon_id || "";
                        jsonCode.textContent = JSON.stringify(storyboardData, null, 2);
                        if (row) row.querySelector("td:last-child").innerHTML =
                            `<span style="background:#14532d;border:1px solid #166534;color:#4ade80;border-radius:4px;padding:2px 7px;font-size:11px;">✅ ${escapeHtml(result.provider)}${result.icon_id ? ` · ${escapeHtml(result.icon_id)}` : ""}</span>`;
                        if (row) row.querySelector("td:nth-child(3)").innerHTML =
                            `<code style="color:#4ade80;font-size:11px;">${escapeHtml(newKeyword)}</code>`;
                        log(`Fixed: "${escapeHtml(newKeyword)}" resolved via ${result.provider}`);
                        // Recount fallbacks and update summary
                        const remaining = items.filter(i => i.status === "fallback").length;
                        preflightSummary.textContent = remaining === 0
                            ? `Pre-flight: all ${total} assets resolved`
                            : `Pre-flight: ${total - remaining}/${total} resolved — ${remaining} fallback${remaining > 1 ? "s" : ""}`;
                        if (remaining === 0) {
                            preflightSummary.style.color = "#4ade80";
                            preflightPanel.style.borderColor = "#22c55e";
                        }
                    } else {
                        btn.textContent = "Re-test";
                        btn.disabled = false;
                        log(`Still falling back: "${escapeHtml(newKeyword)}" — try a different keyword.`, "warn");
                    }
                } catch (e) {
                    btn.textContent = "Re-test";
                    btn.disabled = false;
                }
            });
        });
    }

    function renderNonManinItems(items) {
        if (!items || items.length === 0) {
            nonManinPanel.classList.add("hidden");
            return;
        }
        nonManinPanel.classList.remove("hidden");
        nonManinCount.textContent = `${items.length} item${items.length > 1 ? "s" : ""} require external sourcing (cannot be generated by Manim)`;
        nonManinRows.innerHTML = items.map(item => `
            <tr style="border-bottom:1px solid #2a2a2a;vertical-align:top;">
                <td style="padding:6px 8px;white-space:nowrap;color:#fbbf24;">Scene ${item.scene}</td>
                <td style="padding:6px 8px;white-space:nowrap;">
                    <span style="background:#292524;border:1px solid #44403c;border-radius:4px;padding:2px 6px;font-size:11px;color:#d4d4d4;">
                        ${escapeHtml(item.label || item.type)}
                    </span>
                    ${item.element_id ? `<br><span style="color:#737373;font-size:10px;">${escapeHtml(item.element_id)}</span>` : ""}
                </td>
                <td style="padding:6px 8px;color:#e5e5e5;">${escapeHtml(item.description)}</td>
                <td style="padding:6px 8px;color:#86efac;font-style:italic;">${escapeHtml(item.suggestion)}</td>
            </tr>
        `).join("");
        // Auto-open the panel
        nonManinBody.style.display = "block";
        nonManinToggleLabel.textContent = "▲ hide";
    }

    function escapeHtml(str) {
        return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    }
});
