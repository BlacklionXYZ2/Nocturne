/**
 * Autonomous Local Agent Management Center - Frontend Controller
 * ===============================================================
 * Handles:
 * 1. Multi-turn Agent execution with thought streaming & tool badge rendering.
 * 2. Autonomous Scheduler & Task Queue controls (task_queue.md).
 * 3. GPU Power & Thermal Management (Auto-Sleep / 330W -> 18W Standby).
 * 4. Model Studio with GGUF binary hardware DNA & live VRAM calculation.
 * 5. Long-term Markdown memory CRUD & transcript log viewer.
 * 6. WebSockets real-time status and telemetry updates.
 */

const appState = {
  activeTab: "agent",
  discoveredModels: [],
  selectedModelObj: null,
  activeModel: null,
  gpuPowerState: "sleeping",
  memoryFiles: [],
  activeMemoryFile: "core_knowledge.md",
  conversations: [],
  activeConversation: null,
  scheduler: {
    enabled: false,
    interval_minutes: 60,
    is_running_cycle: false,
    next_run_time: null
  }
};

// -----------------------------------------------------------------------------
// Initialization & WebSockets Telemetry
// -----------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initLucide();
  initWebSockets();
  refreshStatus();
  refreshModels();
  refreshMemoryFiles();
  refreshConversations();
  refreshScheduler();
  loadTaskQueue();

  // Periodic poll for GPU power & scheduler state
  setInterval(refreshStatus, 4000);
  setInterval(refreshScheduler, 6000);
});

function initLucide() {
  if (window.lucide) {
    lucide.createIcons();
  }
}

function initWebSockets() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data);
    } catch (e) {
      console.warn("WebSocket parse error:", e);
    }
  };

  ws.onclose = () => {
    setTimeout(initWebSockets, 3000);
  };
}

function handleWebSocketMessage(msg) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;

  if (msg.type === "thought") {
    appendTerminalThought(msg.data);
  } else if (msg.type === "tool_call") {
    appendTerminalToolCall(msg.data);
  } else if (msg.type === "tool_result") {
    appendTerminalToolResult(msg.data);
  } else if (msg.type === "status") {
    appendTerminalStatus(msg.data);
  } else if (msg.type === "final_answer") {
    if (msg.data && msg.data.trim()) {
      appendTerminalAnswer(msg.data);
    }
    const btn = document.getElementById("btn-dispatch-agent");
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Execute Task</span>`;
    }
    const statusLabel = document.getElementById("agent-status-label");
    if (statusLabel) {
      statusLabel.innerText = "Agent Idle";
      statusLabel.className = "text-[11px] font-mono text-slate-400";
    }
    const schedBtn = document.getElementById("btn-run-cycle-now");
    if (schedBtn) {
      schedBtn.disabled = false;
      schedBtn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Run Self-Prompt Cycle Now</span>`;
    }
    initLucide();
    loadTaskQueue();
    refreshStatus();
  }
}

// -----------------------------------------------------------------------------
// Tab Navigation
// -----------------------------------------------------------------------------
function switchTab(tabId) {
  appState.activeTab = tabId;

  // Hide all tab contents
  document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
  const target = document.getElementById(`tab-${tabId}`);
  if (target) target.classList.remove("hidden");

  // Update tab button styles
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.className = "tab-btn px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5";
  });
  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) {
    activeBtn.className = "tab-btn px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-slate-800 shadow transition flex items-center gap-1.5";
  }

  initLucide();
}

// -----------------------------------------------------------------------------
// Status & GPU Power Management (Auto-Sleep / 330W Protection)
// -----------------------------------------------------------------------------
async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    appState.activeModel = data.active_model;
    appState.gpuPowerState = data.power_state;

    // Update active model banners
    const modelText = data.active_model || (data.is_running ? "Running" : "GPU Sleeping (Standby)");
    const agentModelLabel = document.getElementById("agent-active-model-name");
    if (agentModelLabel) agentModelLabel.innerText = modelText;

    // Update Top GPU Power Badge
    const powerDot = document.getElementById("gpu-power-dot");
    const powerText = document.getElementById("gpu-power-text");
    const powerBtnText = document.getElementById("btn-gpu-toggle-text");
    const powerDesc = document.getElementById("agent-gpu-power-desc");

    const gpu = data.gpu || {};
    const watts = gpu.power_watts || (data.is_running ? 285 : 18);
    const temp = gpu.temp_c ? `${gpu.temp_c}°C` : "";

    if (data.is_running) {
      if (powerDot) powerDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
      if (powerText) powerText.innerText = `GPU ACTIVE (${watts}W${temp ? ' • ' + temp : ''})`;
      if (powerBtnText) powerBtnText.innerText = "Sleep GPU";
      if (powerDesc) powerDesc.innerText = `GPU Active (${watts}W • ${temp})`;
    } else {
      if (powerDot) powerDot.className = "w-2 h-2 rounded-full bg-slate-500";
      if (powerText) powerText.innerText = `GPU STANDBY (${watts}W${temp ? ' • ' + temp : ''})`;
      if (powerBtnText) powerBtnText.innerText = "Wake GPU";
      if (powerDesc) powerDesc.innerText = `Standby (${watts}W • Cool)`;
    }
  } catch (e) {
    console.warn("Status fetch error:", e);
  }
}

async function toggleGpuPower() {
  try {
    if (appState.gpuPowerState === "active") {
      await fetch("/api/power/sleep", { method: "POST" });
    } else {
      await fetch("/api/power/wake", { method: "POST" });
    }
    await refreshStatus();
  } catch (e) {
    alert(`GPU toggle error: ${e.message}`);
  }
}

// -----------------------------------------------------------------------------
// Autonomous Scheduler & Task Queue Controller
// -----------------------------------------------------------------------------
async function refreshScheduler() {
  try {
    const res = await fetch("/api/scheduler/status");
    const data = await res.json();
    appState.scheduler = data;

    const toggle = document.getElementById("sched-enable-toggle");
    if (toggle) toggle.checked = data.enabled;

    const intervalInput = document.getElementById("sched-interval-mins");
    if (intervalInput && !document.activeElement.isSameNode(intervalInput)) {
      intervalInput.value = data.interval_minutes;
    }

    const sleepToggle = document.getElementById("sched-sleep-after");
    if (sleepToggle) sleepToggle.checked = data.sleep_after_cycle;

    const nextRunText = document.getElementById("sched-next-run-text");
    if (nextRunText) {
      if (data.enabled && data.next_run_time) {
        const remainingSec = Math.max(0, Math.round(data.next_run_time - (Date.now() / 1000)));
        const mins = Math.floor(remainingSec / 60);
        const secs = remainingSec % 60;
        nextRunText.innerText = `In ${mins}m ${secs}s`;
      } else {
        nextRunText.innerText = "Disabled";
      }
    }

    const statusLabel = document.getElementById("sched-status-label");
    if (statusLabel) {
      statusLabel.innerText = data.is_running_cycle ? "Running Cycle..." : "Idle";
      statusLabel.className = data.is_running_cycle ? "text-cyan-400 font-mono animate-pulse" : "text-slate-300 font-mono";
    }
  } catch (e) {
    console.warn("Scheduler status fetch error:", e);
  }
}

async function saveSchedulerSettings() {
  const enabled = document.getElementById("sched-enable-toggle").checked;
  const interval = parseInt(document.getElementById("sched-interval-mins").value) || 60;
  const sleepAfter = document.getElementById("sched-sleep-after").checked;

  try {
    await fetch("/api/scheduler/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: enabled,
        interval_minutes: interval,
        sleep_after_cycle: sleepAfter
      })
    });
    await refreshScheduler();
  } catch (e) {
    alert(`Failed to update scheduler: ${e.message}`);
  }
}

async function runAutonomousCycleNow() {
  const btn = document.getElementById("btn-run-cycle-now");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Running Cycle...";
  }

  try {
    appendTerminalStatus("⚡ Starting manual Autonomous Self-Prompting cycle...");
    switchTab("agent");

    const res = await fetch("/api/scheduler/run_now", { method: "POST" });
    const data = await res.json();

    if (data.status === "started") {
      appendTerminalStatus("⚡ Autonomous cycle initiated in background. Streaming live reasoning below:");
    } else {
      appendTerminalStatus(`Autonomous cycle status: ${data.message || data.status}`);
    }
  } catch (e) {
    appendTerminalStatus(`❌ Could not trigger cycle: ${e.message}`);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Run Self-Prompt Cycle Now</span>`;
    }
    initLucide();
  }
}

async function loadTaskQueue() {
  try {
    const res = await fetch("/api/memory/task_queue.md");
    if (res.ok) {
      const data = await res.json();
      const editor = document.getElementById("task-queue-editor");
      if (editor) editor.value = data.content;
    }
  } catch (e) {
    console.warn("Could not load task_queue.md:", e);
  }
}

async function saveTaskQueueMarkdown() {
  const editor = document.getElementById("task-queue-editor");
  if (!editor) return;

  try {
    await fetch("/api/memory/task_queue.md", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: editor.value })
    });
    alert("Saved memory/task_queue.md successfully!");
  } catch (e) {
    alert(`Failed to save task queue: ${e.message}`);
  }
}

// -----------------------------------------------------------------------------
// Agent Execution Terminal
// -----------------------------------------------------------------------------
async function dispatchAgentTask() {
  const input = document.getElementById("agent-task-input");
  const prompt = input.value.trim();
  if (!prompt) return;

  const maxTurns = parseInt(document.getElementById("agent-max-turns").value) || 15;
  const btn = document.getElementById("btn-dispatch-agent");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Executing...";
  }

  const statusLabel = document.getElementById("agent-status-label");
  if (statusLabel) {
    statusLabel.innerText = "Agent Thinking...";
    statusLabel.className = "text-[11px] font-mono text-cyan-400 animate-pulse";
  }

  appendTerminalUser(prompt);
  input.value = "";

  try {
    const res = await fetch("/api/agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: prompt, max_turns: maxTurns })
    });

    if (!res.ok) {
      const data = await res.json();
      appendTerminalStatus(`❌ Execution Error: ${data.detail || "Unknown error"}`);
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Execute Task</span>`;
      }
      if (statusLabel) {
        statusLabel.innerText = "Agent Idle";
        statusLabel.className = "text-[11px] font-mono text-slate-400";
      }
      initLucide();
    }
  } catch (e) {
    appendTerminalStatus(`❌ Network / Server Error: ${e.message}`);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Execute Task</span>`;
    }
    if (statusLabel) {
      statusLabel.innerText = "Agent Idle";
      statusLabel.className = "text-[11px] font-mono text-slate-400";
    }
    initLucide();
  }
}

async function resetAgentSession() {
  try {
    const res = await fetch("/api/agent/reset", { method: "POST" });
    if (res.ok) {
      appendTerminalStatus("🔄 Started a fresh conversation. Previous session archived.");
    }
  } catch (e) {
    alert(`Failed to reset session: ${e.message}`);
  }
}

function clearAgentTerminal() {
  const term = document.getElementById("agent-terminal-output");
  if (term) term.innerHTML = `<p class="text-slate-500 text-[11px]">(Terminal cleared. Ready for next task.)</p>`;
}

function appendTerminalUser(prompt) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;
  const div = document.createElement("div");
  div.className = "p-3 rounded-lg bg-cyan-950/30 border border-cyan-800/60 text-cyan-200";
  div.innerHTML = `<span class="text-[10px] uppercase font-bold text-cyan-400 block mb-1">User Task</span><p class="whitespace-pre-wrap">${escapeHtml(prompt)}</p>`;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function appendTerminalThought(thought) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;
  const div = document.createElement("div");
  div.className = "p-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 italic text-[11px]";
  div.innerHTML = `<span class="text-[10px] uppercase font-bold text-indigo-400 not-italic block mb-1">Agent Thought &amp; Scratchpad</span><p class="whitespace-pre-wrap">${escapeHtml(thought)}</p>`;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function appendTerminalToolCall(data) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;
  const div = document.createElement("div");
  div.className = "p-2.5 rounded-lg bg-amber-950/20 border border-amber-800/40 text-amber-200 text-xs";
  div.innerHTML = `<div class="flex items-center gap-1.5 font-bold text-amber-400 text-[11px]"><i data-lucide="wrench" class="w-3 h-3"></i><span>Calling Tool: ${escapeHtml(data.tool)}</span></div><pre class="mt-1 text-[11px] text-slate-300 font-mono overflow-x-auto">${escapeHtml(JSON.stringify(data.args, null, 2))}</pre>`;
  term.appendChild(div);
  initLucide();
  term.scrollTop = term.scrollHeight;
}

function appendTerminalToolResult(data) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;
  const div = document.createElement("div");
  div.className = "p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 text-[11px]";
  div.innerHTML = `<div class="text-[10px] uppercase font-bold text-slate-500 mb-0.5">Observation (${escapeHtml(data.tool)})</div><pre class="font-mono text-[11px] text-slate-300 whitespace-pre-wrap overflow-x-auto max-h-48">${escapeHtml(data.result)}</pre>`;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function appendTerminalAnswer(answer) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;
  const div = document.createElement("div");
  div.className = "p-4 rounded-lg bg-emerald-950/30 border border-emerald-800/60 text-emerald-100";
  div.innerHTML = `<span class="text-[10px] uppercase font-bold text-emerald-400 block mb-1">Final Answer &amp; Outcome</span><p class="whitespace-pre-wrap leading-relaxed">${escapeHtml(answer)}</p>`;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function appendTerminalStatus(msg) {
  const term = document.getElementById("agent-terminal-output");
  if (!term) return;
  const div = document.createElement("div");
  div.className = "text-[11px] font-mono text-cyan-400/80 py-0.5";
  div.innerText = `> ${msg}`;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

// -----------------------------------------------------------------------------
// Model Scanner & Parameter Studio Controller
// -----------------------------------------------------------------------------
async function refreshModels() {
  const container = document.getElementById("model-cards-container");
  if (!container) return;

  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    appState.discoveredModels = data.models || [];

    if (appState.discoveredModels.length === 0) {
      container.innerHTML = `<p class="text-xs text-amber-400">No primary GGUF models found in Desktop\\Models.</p>`;
      return;
    }

    container.innerHTML = appState.discoveredModels.map((m, idx) => {
      const isSelected = appState.selectedModelObj?.name === m.name;
      const isCurrent = appState.activeModel === m.name;
      const maxCtxK = Math.round(m.max_context_length / 1024);

      let draftBadge = "";
      if (m.companion_draft_model) {
        draftBadge = `<span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">⚡ Draft: ${m.companion_draft_model.type.toUpperCase()}</span>`;
      }

      return `
        <div onclick="selectModelByIndex(${idx})" class="glass-panel p-3.5 rounded-xl space-y-2.5 cursor-pointer border transition ${isSelected ? 'border-cyan-400 bg-cyan-950/30 ring-1 ring-cyan-400' : (isCurrent ? 'border-emerald-500 shadow-sm' : 'border-slate-800 hover:border-slate-700')}">
          <div class="flex items-start justify-between gap-1.5">
            <h4 class="text-xs font-semibold text-white truncate flex-1" title="${m.name}">${m.name}</h4>
            <span class="text-[10px] px-2 py-0.5 rounded-full border bg-indigo-950 text-indigo-300 border-indigo-800 font-mono">${m.architecture}</span>
          </div>
          <div class="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
            <span>${m.size_gb} GB</span>
            <span>•</span>
            <span class="text-cyan-400">${m.quantization}</span>
            <span>•</span>
            <span class="text-emerald-400 font-semibold">${maxCtxK >= 1024 ? '1M' : maxCtxK + 'k'} ctx</span>
            ${draftBadge}
          </div>
          <div class="pt-1 flex items-center justify-between text-[11px] text-slate-400">
            <span class="text-slate-500">Native Max: ${m.max_context_length.toLocaleString()} tokens</span>
            ${isCurrent ? '<span class="text-emerald-400 font-semibold flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Active</span>' : ''}
          </div>
        </div>
      `;
    }).join("");

    initLucide();

    if (!appState.selectedModelObj && appState.discoveredModels.length > 0) {
      selectModelByIndex(0);
    }
  } catch (e) {
    container.innerHTML = `<p class="text-xs text-rose-400">Failed to scan models: ${e.message}</p>`;
  }
}

function selectModelByIndex(index) {
  const model = appState.discoveredModels[index];
  if (!model) return;

  appState.selectedModelObj = model;
  const maxCtx = model.max_context_length || 131072;
  const maxCtxK = Math.round(maxCtx / 1024);
  document.getElementById("selected-model-banner").innerText = `${model.name} (${model.size_gb} GB)`;

  // Update Model Architecture DNA Card
  const dnaArch = document.getElementById("dna-arch");
  if (dnaArch) dnaArch.innerText = `${model.architecture} • ${model.moe_info || 'Dense'}`;

  const dnaGqa = document.getElementById("dna-gqa");
  if (dnaGqa) dnaGqa.innerText = `${model.block_count || '--'} layers • GQA ${model.gqa_ratio || '--'}`;

  const dnaNativeCtx = document.getElementById("dna-native-ctx");
  if (dnaNativeCtx) dnaNativeCtx.innerText = `${maxCtx.toLocaleString()} tokens (${maxCtxK >= 1024 ? '1M' : maxCtxK + 'k'})`;

  // Dynamically set slider max to the model's exact native limit
  const slider = document.getElementById("param-ctx-size");
  slider.max = maxCtx;

  const numInput = document.getElementById("param-ctx-number");
  numInput.max = maxCtx;

  // Set default context length & KV quantization
  const ctxVal = model.ideal_gpu_ctx || Math.min(maxCtx, 32768);
  slider.value = ctxVal;
  numInput.value = ctxVal;

  const ctkSelect = document.getElementById("param-ctk");
  const ctvSelect = document.getElementById("param-ctv");
  if (ctkSelect && model.ideal_kv_quant) ctkSelect.value = model.ideal_kv_quant;
  if (ctvSelect && model.ideal_kv_quant) ctvSelect.value = model.ideal_kv_quant;

  // Handle companion speculative draft model (dflash / MTP)
  const draftBox = document.getElementById("draft-model-box");
  const draftName = document.getElementById("draft-model-name");
  const draftToggle = document.getElementById("param-enable-draft");

  if (model.companion_draft_model) {
    draftBox.classList.remove("hidden");
    draftName.innerText = `${model.companion_draft_model.filename} (${model.companion_draft_model.size_gb} GB)`;
    draftToggle.checked = true;
  } else {
    draftBox.classList.add("hidden");
    draftToggle.checked = false;
  }

  updateParamDisplay();
  refreshModels();
}

function autoTuneIdealEnvironment() {
  const model = appState.selectedModelObj;
  if (!model) return;

  const idealCtx = model.ideal_gpu_ctx || 32768;
  document.getElementById("param-ctx-size").value = idealCtx;
  document.getElementById("param-ctx-number").value = idealCtx;

  const idealQuant = model.ideal_kv_quant || "q8_0";
  document.getElementById("param-ctk").value = idealQuant;
  document.getElementById("param-ctv").value = idealQuant;

  document.getElementById("param-ngl").value = 99;
  document.getElementById("param-fa").checked = true;
  document.getElementById("param-temp").value = 0.15;

  updateParamDisplay();
  alert(`Auto-tuned parameters for ${model.name} to ideal fit for AMD RX 9070 XT (16 GB VRAM)!`);
}

function syncCtxFromSlider() {
  const val = document.getElementById("param-ctx-size").value;
  document.getElementById("param-ctx-number").value = val;
  updateParamDisplay();
}

function syncCtxFromNumber() {
  const val = document.getElementById("param-ctx-number").value;
  document.getElementById("param-ctx-size").value = val;
  updateParamDisplay();
}

function setCtxPreset(tokens) {
  document.getElementById("param-ctx-size").value = tokens;
  document.getElementById("param-ctx-number").value = tokens;
  updateParamDisplay();
}

function updateParamDisplay() {
  const model = appState.selectedModelObj;
  const ctx = parseInt(document.getElementById("param-ctx-number").value) || 8192;
  const ngl = document.getElementById("param-ngl").value;

  document.getElementById("val-ngl").innerText = `${ngl} layers (ROCm0)`;
  document.getElementById("val-temp").innerText = document.getElementById("param-temp").value;
  document.getElementById("val-top-p").innerText = document.getElementById("param-top-p").value;

  // Live VRAM Footprint Calculation
  if (model) {
    const ctk = document.getElementById("param-ctk")?.value || "q8_0";
    let mult = 1.0;
    if (ctk === "f16") mult = 2.0;
    else if (ctk === "q5_1" || ctk === "q5_0") mult = 0.65;
    else if (ctk === "q4_1" || ctk === "q4_0" || ctk === "iq4_nl") mult = 0.53;

    const bytesPerToken = (model.bytes_per_token_q8 || 64) * mult;
    const kvGb = (bytesPerToken * ctx) / (1024 ** 3);
    const totalVram = model.size_gb + kvGb + 0.6; // 600MB ROCm runtime buffer

    const vramPct = Math.min(100, Math.round((totalVram / 16.3) * 100));
    const meterText = document.getElementById("vram-meter-text");
    const meterBar = document.getElementById("vram-meter-bar");
    const meterStatus = document.getElementById("vram-meter-status");

    if (meterText) meterText.innerText = `${totalVram.toFixed(1)} GB / 16.3 GB (${vramPct}%)`;
    if (meterBar) {
      meterBar.style.width = `${vramPct}%`;
      if (totalVram <= 14.5) {
        meterBar.className = "h-full bg-emerald-400 transition-all duration-300";
        if (meterStatus) meterStatus.innerText = "✓ Optimal fit: 100% offloaded in dedicated VRAM";
      } else if (totalVram <= 16.3) {
        meterBar.className = "h-full bg-amber-400 transition-all duration-300";
        if (meterStatus) meterStatus.innerText = "⚡ High VRAM: Close to GPU capacity limit";
      } else {
        meterBar.className = "h-full bg-rose-500 transition-all duration-300";
        if (meterStatus) meterStatus.innerText = "⚠ Warning: Exceeds 16.3 GB VRAM (will spill to system RAM)";
      }
    }
  }
}

async function launchSelectedModel() {
  const model = appState.selectedModelObj;
  if (!model) {
    alert("Please select a model from the list first.");
    return;
  }

  const btn = document.getElementById("btn-launch-model");
  btn.disabled = true;
  btn.innerText = "Loading model onto GPU (ROCm0)...";

  const ctxSize = parseInt(document.getElementById("param-ctx-number").value);
  const ngl = parseInt(document.getElementById("param-ngl").value);
  const flashAttn = document.getElementById("param-fa").checked;
  const ctk = document.getElementById("param-ctk").value;
  const ctv = document.getElementById("param-ctv").value;
  const enableDraft = document.getElementById("param-enable-draft").checked;

  let draftPath = null;
  if (enableDraft && model.companion_draft_model) {
    draftPath = model.companion_draft_model.full_path;
  }

  const payload = {
    model: model.full_path || model.relative_path || model.name,
    params: {
      ctx_size: ctxSize,
      n_gpu_layers: ngl,
      device: "ROCm0",
      flash_attn: flashAttn,
      cache_type_k: ctk,
      cache_type_v: ctv,
      draft_model: draftPath,
      draft_gpu_layers: draftPath ? 99 : 0
    }
  };

  try {
    const res = await fetch("/api/server/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok) {
      alert(`Model ${data.model} successfully loaded onto GPU!`);
      await refreshStatus();
      switchTab("agent");
    } else {
      alert(`Launch error: ${data.detail || "Failed to start server"}`);
    }
  } catch (e) {
    alert(`Connection error: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="play" class="w-4 h-4"></i><span>Load Selected Model onto GPU</span>`;
    initLucide();
  }
}

// -----------------------------------------------------------------------------
// Markdown Memory CRUD Controller
// -----------------------------------------------------------------------------
async function refreshMemoryFiles() {
  const container = document.getElementById("memory-file-list");
  if (!container) return;

  try {
    const res = await fetch("/api/memory");
    const data = await res.json();
    appState.memoryFiles = data.files || [];

    container.innerHTML = appState.memoryFiles.map(f => {
      const isSelected = f === appState.activeMemoryFile;
      return `
        <div onclick="selectMemoryFile('${f}')" class="p-2.5 rounded-lg text-xs font-mono cursor-pointer border transition flex items-center justify-between ${isSelected ? 'border-teal-500 bg-teal-950/40 text-teal-200' : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:text-white'}">
          <span class="truncate">${f}</span>
          <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
        </div>
      `;
    }).join("");

    initLucide();

    if (appState.memoryFiles.length > 0) {
      if (!appState.memoryFiles.includes(appState.activeMemoryFile)) {
        appState.activeMemoryFile = appState.memoryFiles[0];
      }
      selectMemoryFile(appState.activeMemoryFile);
    }
  } catch (e) {
    container.innerHTML = `<p class="text-xs text-rose-400">Failed to load memory: ${e.message}</p>`;
  }
}

async function selectMemoryFile(filename) {
  appState.activeMemoryFile = filename;
  document.getElementById("active-memory-filename").innerText = filename;

  try {
    const res = await fetch(`/api/memory/${filename}`);
    const data = await res.json();
    document.getElementById("memory-editor-textarea").value = data.content || "";
    refreshMemoryFilesHighlight();
  } catch (e) {
    console.error("Error reading file:", e);
  }
}

function refreshMemoryFilesHighlight() {
  const container = document.getElementById("memory-file-list");
  if (!container) return;
  const items = container.querySelectorAll("div");
  items.forEach(el => {
    const text = el.querySelector("span")?.innerText;
    if (text === appState.activeMemoryFile) {
      el.className = "p-2.5 rounded-lg text-xs font-mono cursor-pointer border transition flex items-center justify-between border-teal-500 bg-teal-950/40 text-teal-200";
    } else {
      el.className = "p-2.5 rounded-lg text-xs font-mono cursor-pointer border transition flex items-center justify-between border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:text-white";
    }
  });
}

async function saveCurrentMemoryFile() {
  const filename = appState.activeMemoryFile;
  const content = document.getElementById("memory-editor-textarea").value;

  try {
    await fetch(`/api/memory/${filename}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: content })
    });
    alert(`Saved ${filename} successfully!`);
  } catch (e) {
    alert(`Failed to save: ${e.message}`);
  }
}

async function createNewMemoryFile() {
  const name = prompt("Enter new memory filename (e.g. custom_lore.md):");
  if (!name) return;
  const cleanName = name.endsWith(".md") ? name : `${name}.md`;

  try {
    await fetch(`/api/memory/${cleanName}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: `# ${cleanName}\n\n` })
    });
    appState.activeMemoryFile = cleanName;
    await refreshMemoryFiles();
  } catch (e) {
    alert(`Failed to create file: ${e.message}`);
  }
}

// -----------------------------------------------------------------------------
// Conversation Archives Controller
// -----------------------------------------------------------------------------
async function refreshConversations() {
  const container = document.getElementById("conversations-list");
  if (!container) return;

  try {
    const res = await fetch("/api/conversations");
    const data = await res.json();
    appState.conversations = data.conversations || [];

    if (appState.conversations.length === 0) {
      container.innerHTML = `<p class="text-xs text-slate-500 p-2">No archived conversation logs found.</p>`;
      return;
    }

    container.innerHTML = appState.conversations.map(c => `
      <div onclick="selectConversation('${c}')" class="p-2.5 rounded-lg text-xs font-mono cursor-pointer border border-slate-800 bg-slate-900 text-slate-300 hover:border-purple-500 hover:text-white transition flex items-center justify-between">
        <span class="truncate">${c}</span>
        <i data-lucide="file-text" class="w-3.5 h-3.5 text-purple-400"></i>
      </div>
    `).join("");

    initLucide();
  } catch (e) {
    container.innerHTML = `<p class="text-xs text-rose-400">Failed to load logs: ${e.message}</p>`;
  }
}

async function selectConversation(filename) {
  appState.activeConversation = filename;
  document.getElementById("viewing-conversation-title").innerText = filename;

  try {
    const res = await fetch(`/api/conversations/${filename}`);
    const data = await res.json();
    document.getElementById("conversation-viewer-content").innerText = data.content || "(Empty log file)";
  } catch (e) {
    document.getElementById("conversation-viewer-content").innerText = `Error: ${e.message}`;
  }
}

// -----------------------------------------------------------------------------
// Social Integrations (Moltbook & 1F916)
// -----------------------------------------------------------------------------
async function saveIntegrationSettings() {
  const moltEnabled = document.getElementById("integ-moltbook-enabled").checked;
  const moltKey = document.getElementById("integ-moltbook-key").value;
  const onefEnabled = document.getElementById("integ-onef916-enabled").checked;
  const onefKey = document.getElementById("integ-onef916-key").value;

  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();

    if (!cfg.integrations) cfg.integrations = {};
    cfg.integrations.moltbook = { enabled: moltEnabled, api_key: moltKey, base_url: "https://moltbook.com/api/v1" };
    cfg.integrations.onef916 = { enabled: onefEnabled, api_key: onefKey, base_url: "https://1f916.org/api/v1" };

    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg)
    });

    alert("Social integrations configuration saved successfully!");
  } catch (e) {
    alert(`Failed to save integrations: ${e.message}`);
  }
}

// -----------------------------------------------------------------------------
// Mobile Companion & Cloudflare QR Pairing
// -----------------------------------------------------------------------------
let qrCodeInstance = null;

function openMobileModal() {
  document.getElementById("mobile-modal").classList.remove("hidden");
  checkTunnelStatus();
}

function closeMobileModal() {
  document.getElementById("mobile-modal").classList.add("hidden");
}

async function checkTunnelStatus() {
  try {
    const res = await fetch("/api/tunnel/status");
    const data = await res.json();
    if (data.is_active && data.authenticated_url) {
      showActiveTunnel(data.authenticated_url);
    } else {
      showIdleTunnel();
    }
  } catch (e) {
    showIdleTunnel();
  }
}

function showIdleTunnel() {
  document.getElementById("tunnel-idle-state").classList.remove("hidden");
  document.getElementById("tunnel-active-state").classList.add("hidden");
  document.getElementById("tunnel-loading-state").classList.add("hidden");
}

function showLoadingTunnel() {
  document.getElementById("tunnel-idle-state").classList.add("hidden");
  document.getElementById("tunnel-active-state").classList.add("hidden");
  document.getElementById("tunnel-loading-state").classList.remove("hidden");
}

function showActiveTunnel(url) {
  document.getElementById("tunnel-idle-state").classList.add("hidden");
  document.getElementById("tunnel-loading-state").classList.add("hidden");
  document.getElementById("tunnel-active-state").classList.remove("hidden");
  document.getElementById("tunnel-url-display").value = url;

  renderQrCode(url);
}

function renderQrCode(url) {
  const container = document.getElementById("qrcode-container");
  container.innerHTML = "";
  if (typeof QRCode !== "undefined") {
    qrCodeInstance = new QRCode(container, {
      text: url,
      width: 180,
      height: 180,
      colorDark: "#0f172a",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.M
    });
  } else {
    container.innerHTML = `<p class="text-xs text-slate-500">QR Code library loading...</p>`;
  }
}

async function startCloudflareTunnel() {
  showLoadingTunnel();
  try {
    const res = await fetch("/api/tunnel/start", { method: "POST" });
    const data = await res.json();
    if (data.authenticated_url) {
      showActiveTunnel(data.authenticated_url);
    } else {
      alert("Tunnel failed to start. Ensure npx or cloudflared is accessible.");
      showIdleTunnel();
    }
  } catch (e) {
    alert(`Tunnel startup error: ${e.message}`);
    showIdleTunnel();
  }
}

async function stopCloudflareTunnel() {
  try {
    await fetch("/api/tunnel/stop", { method: "POST" });
    showIdleTunnel();
  } catch (e) {
    alert(`Failed to stop tunnel: ${e.message}`);
  }
}

function copyTunnelUrl() {
  const input = document.getElementById("tunnel-url-display");
  input.select();
  navigator.clipboard.writeText(input.value);
  alert("Mobile pair URL copied to clipboard!");
}

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------
function escapeHtml(str) {
  if (typeof str !== "string") str = JSON.stringify(str);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

