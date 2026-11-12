/* Model routing panel — shared by the classic UI (/) and Studio (/studio).
 *
 *   <div id="model-panel"></div>
 *   <script src="/static/model-panel.js"></script>
 *   mountModelPanel(document.getElementById('model-panel'));
 *
 * Talks to /api/models. Selection is process-global on the server and takes effect
 * on the next LLM call; .env stays the durable configuration. Styles are injected
 * scoped to .mp-root so the panel looks the same on both pages without touching
 * either stylesheet.
 */
(function () {
  const CSS = `
.mp-root{font-size:12.5px;color:#c9d1d9}
.mp-root .mp-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.mp-root .mp-title{font-weight:700;letter-spacing:.02em;color:#e6edf3}
.mp-root .mp-spacer{flex:1}
.mp-root button{font:inherit;cursor:pointer;border-radius:6px;border:1px solid #30363d;
  background:#21262d;color:#c9d1d9;padding:4px 9px}
.mp-root button:hover{border-color:#58c4dd;color:#e6edf3}
.mp-root button.mp-primary{background:#1f6feb;border-color:#1f6feb;color:#fff}
.mp-root button.mp-primary:disabled{opacity:.5;cursor:default}
.mp-root .mp-order{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.mp-root .mp-prov{display:flex;align-items:center;gap:6px;border:1px solid #30363d;
  border-radius:20px;padding:3px 6px 3px 11px;background:#161b22}
.mp-root .mp-prov.mp-off{opacity:.45}
.mp-root .mp-prov b{font-weight:600}
.mp-root .mp-prov .mp-mini{border:none;background:none;padding:0 3px;line-height:1;color:#8b949e}
.mp-root .mp-prov .mp-mini:hover{color:#58c4dd}
.mp-root .mp-nokey{color:#f0883e;font-size:10.5px}
.mp-root .mp-task{border:1px solid #21262d;border-radius:8px;padding:9px 11px;margin-bottom:8px;
  background:rgba(255,255,255,.02)}
.mp-root .mp-task>h4{margin:0 0 3px;font-size:12px;color:#e6edf3;letter-spacing:.03em;text-transform:uppercase}
.mp-root .mp-task>p{margin:0 0 8px;color:#8b949e;font-size:11px;line-height:1.45}
.mp-root .mp-row{display:flex;align-items:center;gap:7px;margin:5px 0}
.mp-root .mp-row label{flex:0 0 78px;color:#8b949e;font-size:11.5px}
.mp-root .mp-row input{flex:1;min-width:0;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;
  border-radius:6px;padding:5px 7px;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px}
.mp-root .mp-row input:focus{outline:none;border-color:#58c4dd}
.mp-root .mp-row select{background:#0d1117;border:1px solid #30363d;color:#8b949e;border-radius:6px;
  padding:5px;font-size:11px;max-width:120px}
.mp-root .mp-tag{font-size:9.5px;letter-spacing:.04em;text-transform:uppercase;padding:2px 5px;
  border-radius:4px;background:#21262d;color:#8b949e}
.mp-root .mp-tag.mp-runtime{background:#1f6feb;color:#fff}
.mp-root .mp-tag.mp-env{background:#238636;color:#fff}
.mp-root .mp-note{color:#8b949e;font-size:11px;line-height:1.5;margin-top:8px}
.mp-root .mp-msg{margin-top:8px;padding:6px 9px;border-radius:6px;font-size:11.5px;display:none}
.mp-root .mp-msg.mp-ok{display:block;background:rgba(35,134,54,.15);color:#7ee787;border:1px solid #238636}
.mp-root .mp-msg.mp-err{display:block;background:rgba(248,81,73,.12);color:#ff7b72;border:1px solid #da3633}
`;

  const TASK_BLURB = {
    storyboard: 'Scene plan + narration (also the Visual Director). Structured-JSON compliance is what matters.',
    code: 'Manim codegen, the Layout QA critic and the repair agent.',
    general: 'Transliteration, on-screen label translation, misc.',
    vision: 'Vision QA critique of rendered frames — multimodal models only.',
  };

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  window.mountModelPanel = function (root) {
    if (!root) return;
    if (!document.getElementById('mp-style')) {
      const s = el('style'); s.id = 'mp-style'; s.textContent = CSS;
      document.head.appendChild(s);
    }
    root.classList.add('mp-root');

    let state = null;       // last snapshot from the server
    let order = [];         // provider order being edited
    const inputs = {};      // "task/provider" -> <input>

    const bar = el('div', 'mp-bar');
    const title = el('span', 'mp-title', 'Model routing');
    const btnSave = el('button', 'mp-primary', 'Apply');
    const btnReset = el('button', null, 'Reset to .env');
    const btnReload = el('button', null, '↻');
    btnReload.title = 'Reload from server';
    bar.append(title, el('span', 'mp-spacer'), btnReload, btnReset, btnSave);

    const orderBox = el('div', 'mp-order');
    const tasksBox = el('div');
    const msg = el('div', 'mp-msg');
    const note = el('div', 'mp-note');
    root.append(bar, orderBox, tasksBox, msg, note);

    function say(text, ok) {
      msg.className = 'mp-msg ' + (ok ? 'mp-ok' : 'mp-err');
      msg.textContent = text;
    }

    function renderOrder() {
      orderBox.textContent = '';
      const all = Object.keys(state.providers);
      const active = order.filter((p) => all.includes(p));
      const inactive = all.filter((p) => !active.includes(p));
      active.concat(inactive).forEach((p) => {
        const on = active.includes(p);
        const chip = el('div', 'mp-prov' + (on ? '' : ' mp-off'));
        const idx = active.indexOf(p);
        chip.append(el('b', null, on ? `${idx + 1}. ${p}` : p));
        if (!state.providers[p].available) chip.append(el('span', 'mp-nokey', 'no key'));
        const mk = (label, title, fn) => {
          const b = el('button', 'mp-mini', label); b.title = title;
          b.onclick = () => { fn(); renderOrder(); };
          return b;
        };
        if (on && idx > 0) chip.append(mk('↑', 'Higher priority', () => {
          order = active.slice(); const t = order[idx - 1]; order[idx - 1] = order[idx]; order[idx] = t;
        }));
        if (on && idx < active.length - 1) chip.append(mk('↓', 'Lower priority', () => {
          order = active.slice(); const t = order[idx + 1]; order[idx + 1] = order[idx]; order[idx] = t;
        }));
        chip.append(on
          ? mk('✕', 'Do not use this provider', () => { order = active.filter((x) => x !== p); })
          : mk('+', 'Use this provider (last)', () => { order = active.concat([p]); }));
        orderBox.append(chip);
      });
    }

    function renderTasks() {
      tasksBox.textContent = '';
      state.tasks.forEach((task) => {
        const chains = state.chains[task] || {};
        if (!Object.keys(chains).length) return;
        const box = el('div', 'mp-task');
        box.append(el('h4', null, task), el('p', null, TASK_BLURB[task] || ''));
        Object.keys(chains).forEach((provider) => {
          const chain = chains[provider];
          const row = el('div', 'mp-row');
          const lab = el('label', null, provider);
          const input = el('input');
          input.value = chain.models.join(', ');
          input.placeholder = chain.default.join(', ');
          input.title = `${chain.env_var} — comma-separated, first is primary, the rest are failover`;
          inputs[task + '/' + provider] = input;

          const pick = el('select');
          pick.append(new Option('+ add…', ''));
          (state.catalogue[provider] || []).forEach((m) => {
            pick.append(new Option(`${m.id} — ${m.note}`, m.id));
          });
          pick.onchange = () => {
            if (!pick.value) return;
            const have = input.value.split(',').map((s) => s.trim()).filter(Boolean);
            if (!have.includes(pick.value)) input.value = have.concat([pick.value]).join(', ');
            pick.value = '';
          };

          const tag = el('span', 'mp-tag' + (chain.source === 'runtime' ? ' mp-runtime'
            : chain.source === 'env' ? ' mp-env' : ''), chain.source);
          row.append(lab, input, pick, tag);
          box.append(row);
        });
        tasksBox.append(box);
      });

      const blocked = (state.blocked_markers || []).join(', ');
      note.textContent =
        `Order is priority — the next provider is tried only when the one before it fails. `
        + `Changes apply to the next LLM call and are lost on restart; edit stem_animation_lab/.env to make them stick. `
        + `Blocked (reasoning models — they spend the whole token budget thinking and return nothing): ${blocked}. `
        + `Storyboard token cap: ${state.max_tokens.storyboard}; everything else: ${state.max_tokens.global}.`;
    }

    function render() {
      order = state.provider_order.slice();
      renderOrder();
      renderTasks();
    }

    async function load() {
      try {
        const r = await fetch('/api/models');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        state = await r.json();
        render();
      } catch (e) {
        say(`Could not load model routing: ${e.message}`, false);
      }
    }

    async function post(url, body) {
      btnSave.disabled = true;
      try {
        const r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body || {}),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        state = data;
        render();
        say('Saved — active from the next LLM call.', true);
      } catch (e) {
        say(e.message, false);
      } finally {
        btnSave.disabled = false;
      }
    }

    btnSave.onclick = () => {
      const chains = {};
      Object.keys(inputs).forEach((k) => {
        const [task, provider] = k.split('/');
        (chains[task] = chains[task] || {})[provider] =
          inputs[k].value.split(',').map((s) => s.trim()).filter(Boolean);
      });
      post('/api/models', { provider_order: order, chains });
    };
    btnReset.onclick = () => post('/api/models/reset', {});
    btnReload.onclick = load;

    load();
  };
})();
