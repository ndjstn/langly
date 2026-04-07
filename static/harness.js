const chatWindow = document.getElementById("chat-window");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const modeSelect = document.getElementById("mode-select");
const iterationsInput = document.getElementById("iterations-input");
const iterationsAuto = document.getElementById("iterations-auto");
const abTestToggle = document.getElementById("ab-test-toggle");
const gradeToggle = document.getElementById("grade-toggle");
const scopePanel = document.getElementById("scope-panel");
const statusPanel = document.getElementById("status-panel");
const researchPanel = document.getElementById("research-panel");
const promptPanel = document.getElementById("prompt-panel");
const postprocessPanel = document.getElementById("postprocess-panel");
const tasksPanel = document.getElementById("tasks-panel");
const kanbanPanel = document.getElementById("kanban-panel");
const katasPanel = document.getElementById("katas-panel");
const selectionPanel = document.getElementById("selection-panel");
const routingPanel = document.getElementById("routing-panel");
const iterationsPanel = document.getElementById("iterations-panel");
const recoveryPanel = document.getElementById("recovery-panel");
const tuningPanel = document.getElementById("tuning-panel");
const reconfigPanel = document.getElementById("reconfig-panel");
const abtestPanel = document.getElementById("abtest-panel");
const gradePanel = document.getElementById("grade-panel");
const timingsPanel = document.getElementById("timings-panel");
const toolsPanel = document.getElementById("tools-panel");
const tracePanel = document.getElementById("trace-panel");
const mermaidPanel = document.getElementById("mermaid-panel");
const visionPanel = document.getElementById("vision-panel");
const toolGlossaryPanel = document.getElementById("tool-glossary");
const availablePanel = document.getElementById("available-tools");
const themeSelect = document.getElementById("theme-select");
const researchToggle = document.getElementById("research-toggle");
const citationsToggle = document.getElementById("citations-toggle");
const promptToggle = document.getElementById("prompt-toggle");
const tuningToggle = document.getElementById("tuning-toggle");
const toolSelectionToggle = document.getElementById("tool-selection-toggle");
const taskCaptureToggle = document.getElementById("task-capture-toggle");
const taskTemplatesToggle = document.getElementById("task-templates-toggle");
const taskCapturePanel = document.getElementById("task-capture-panel");
const taskTemplatesPanel = document.getElementById("task-templates-panel");
const filesListEl = document.getElementById("files-list");
const filesPathEl = document.getElementById("files-path");
const fileViewerEl = document.getElementById("file-viewer");
const attachmentsListEl = document.getElementById("attachments-list");
const fileInputEl = document.getElementById("file-input");

let activeRequestId = null;
let statusEvents = [];
let streamTarget = null;
let streamBuffer = "";
let attachments = [];
let currentPath = ".";

const escapeHtml = (text) => {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
};

const linkify = (text) => {
  return text.replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>');
};

const formatResponse = (text) => {
  if (!text) return "";
  const parts = text.split("```");
  return parts
    .map((part, idx) => {
      if (idx % 2 === 0) {
        let escaped = escapeHtml(part);
        escaped = linkify(escaped);
        if (escaped.includes("Sources:")) {
          const sections = escaped.split("Sources:");
          const body = sections[0].trim();
          const sources = sections[1].trim().split("\n").filter(Boolean);
          const items = sources
            .map((line) => {
              const cleaned = line.replace(/^\s*\[\d+\]\s*/, "");
              return `<li>${linkify(cleaned)}</li>`;
            })
            .join("");
          return `${body}\n\n<strong>Sources:</strong><ul class="sources-list">${items}</ul>`;
        }
        return escaped;
      }
      const lines = part.split("\n");
      const lang = escapeHtml(lines.shift() || "");
      const code = escapeHtml(lines.join("\n"));
      return `<pre class="code-block"><button class="copy-btn" data-code="${code}">Copy</button><code>${lang ? `<span class="code-lang">${lang}</span>\n` : ""}${code}</code></pre>`;
    })
    .join("");
};

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_err) {
    const temp = document.createElement("textarea");
    temp.value = text;
    document.body.appendChild(temp);
    temp.select();
    document.execCommand("copy");
    temp.remove();
  }
};

const addMessage = (role, text) => {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.dataset.raw = text;
  const actions = document.createElement("div");
  actions.className = "msg-actions";
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "ghost-btn ghost-btn-small";
  copyBtn.textContent = "Copy";
  copyBtn.dataset.copy = "message";
  actions.appendChild(copyBtn);
  const content = document.createElement("div");
  content.className = "msg-content";
  content.innerHTML = formatResponse(text);
  el.append(actions, content);
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return el;
};

const statusIcon = (status) => {
  if (status === "done" || status === "completed") return "✓";
  if (status === "running" || status === "start") return "•";
  if (status === "failed" || status === "error") return "!";
  return "•";
};

const renderTimeline = (events) => {
  const stageOrder = [
    "scope",
    "kata_before",
    "tools",
    "tools_rerun",
    "kata_during",
    "research",
    "model_routing",
    "iterations_plan",
    "iteration_start",
    "iteration_done",
    "ab_test",
    "postprocess",
    "grade",
    "tuning",
    "task_templates",
    "task_capture",
    "kata_after",
    "complete",
  ];
  if (!events.length) return "";
  const lastStage = events[events.length - 1].stage;
  const lastIndex = stageOrder.indexOf(lastStage);
  const steps = stageOrder
    .map((stage, idx) => {
      const cls = idx < lastIndex ? "done" : idx === lastIndex ? "active" : "";
      return `<span class="status-step ${cls}">${stage.replace("_", " ")}</span>`;
    })
    .join("");
  return `<div class="status-timeline">${steps}</div>`;
};

const formatDetail = (detail) => {
  if (!detail || Object.keys(detail).length === 0) return "";
  const raw = JSON.stringify(detail);
  const trimmed = raw.length > 120 ? `${raw.slice(0, 120)}…` : raw;
  return escapeHtml(trimmed);
};

const renderScope = (scope) => {
  if (!scope) {
    scopePanel.textContent = "";
    return;
  }
  const tags = (scope.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("");
  scopePanel.innerHTML = `
    <div class="taglist">${tags}</div>
    <pre>${escapeHtml(JSON.stringify(scope, null, 2))}</pre>
  `;
};

const renderTools = (tools) => {
  if (!tools) {
    toolsPanel.textContent = "";
    return;
  }
  toolsPanel.innerHTML = tools
    .map((tool) => {
      const output = tool.output ? escapeHtml(JSON.stringify(tool.output, null, 2)) : "";
      const stdout = escapeHtml(tool.stdout || "");
      const stderr = escapeHtml(tool.stderr || "");
      const duration = tool.duration_ms ? `${tool.duration_ms.toFixed(1)}ms` : "";
      return `
        <div class="tool-card">
          <div class="tool-meta">
            <span class="tool-name">${tool.name}</span>
            <span>${tool.status}</span>
            <span>${duration}</span>
            <span>attempts ${tool.attempts}</span>
            <span>retries ${tool.retries}</span>
            ${tool.cached ? "<span>cached</span>" : ""}
          </div>
          ${stderr ? `<div class="tool-output">stderr:\n${stderr}</div>` : ""}
          ${stdout ? `<div class="tool-output">stdout:\n${stdout}</div>` : ""}
          ${output ? `<div class="tool-output">output:\n${output}</div>` : ""}
        </div>
      `;
    })
    .join("");
};

const renderVision = (tools) => {
  if (!visionPanel) return;
  if (!tools) {
    visionPanel.textContent = "";
    return;
  }
  const visionTools = tools.filter((tool) => tool.name === "vision" || tool.name === "vision_pipeline");
  if (!visionTools.length) {
    visionPanel.textContent = "";
    return;
  }
  visionPanel.innerHTML = visionTools
    .map((tool) => {
      const output = tool.output || {};
      const model = output.model || output.segment_model || "";
      const results = output.results || [];
      const cards = results
        .map((result) => {
          const img =
            result.annotated_image && result.annotated_mime
              ? `<img class="vision-img" src="data:${result.annotated_mime};base64,${result.annotated_image}" alt="vision output" />`
              : "";
          const objects = result.objects || [];
          const labels = objects.map((obj) => obj.label).filter(Boolean);
          const labelSummary = labels.length ? labels.slice(0, 8).join(", ") : "";
          const response = result.response ? `<div class="vision-text">${escapeHtml(result.response)}</div>` : "";
          const error = result.error ? `<div class="vision-error">${escapeHtml(result.error)}</div>` : "";
          return `
            <div class="vision-card">
              <div class="vision-meta">
                <span>${escapeHtml(result.path || "")}</span>
                <span>${escapeHtml(String(result.object_count ?? ""))} objects</span>
                <span>${escapeHtml(String(result.mask_count ?? ""))} masks</span>
              </div>
              ${img}
              ${labelSummary ? `<div class="vision-labels">${escapeHtml(labelSummary)}</div>` : ""}
              ${response}
              ${error}
            </div>
          `;
        })
        .join("");
      return `
        <div class="vision-tool">
          <div class="vision-header">
            <span class="tool-name">${escapeHtml(tool.name)}</span>
            <span>${escapeHtml(tool.status)}</span>
            ${model ? `<span>${escapeHtml(model)}</span>` : ""}
          </div>
          <div class="vision-grid">${cards}</div>
        </div>
      `;
    })
    .join("");
};

const renderStatus = () => {
  if (!statusEvents.length) {
    statusPanel.textContent = "";
    return;
  }
  const last = statusEvents[statusEvents.length - 1];
  const progress =
    typeof last?.progress === "number" ? Math.round(last.progress * 100) : null;
  const items = statusEvents
    .slice(-12)
    .map(
      (event) => `
        <div class="status-row status-${event.status}">
          <span class="status-dot">${statusIcon(event.status)}</span>
          <span class="status-stage">${event.stage}</span>
          <span class="status-state">${event.status}</span>
          <span class="status-time">${event.timestamp?.split("T")[1]?.split(".")[0] || ""}</span>
          <span class="status-detail">${formatDetail(event.detail)}</span>
        </div>
      `,
    )
    .join("");
  const timeline = renderTimeline(statusEvents);
  const progressHtml =
    progress === null
      ? ""
      : `<div class="progress"><div style="width:${progress}%"></div></div>`;
  statusPanel.innerHTML = `
    ${progressHtml}
    ${timeline}
    <div class="status-list">${items}</div>
  `;
};

const renderTaskwarrior = (taskwarrior) => {
  if (!taskwarrior) {
    tasksPanel.textContent = "";
    kanbanPanel.textContent = "";
    return;
  }
  tasksPanel.innerHTML = `
    <pre>${escapeHtml(JSON.stringify(taskwarrior, null, 2))}</pre>
  `;
  renderKanban(taskwarrior);
};

const renderResearch = (research) => {
  if (!research) {
    researchPanel.textContent = "";
    return;
  }
  const sources = (research.sources || [])
    .map((src, idx) => {
      const title = escapeHtml(src.title || `Source ${idx + 1}`);
      const url = escapeHtml(src.url || "");
      return `<li><a href="${url}" target="_blank" rel="noreferrer">${title}</a></li>`;
    })
    .join("");
  const meta = escapeHtml(JSON.stringify({ query: research.query, used: research.used, error: research.error }, null, 2));
  researchPanel.innerHTML = `
    <div class="sources-wrap">
      <ul class="sources-list">${sources}</ul>
    </div>
    <pre>${meta}</pre>
  `;
};

const renderPrompt = (prompt) => {
  if (!prompt) {
    promptPanel.textContent = "";
    return;
  }
  promptPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(prompt, null, 2))}</pre>`;
};

const renderPostprocess = (postprocess) => {
  if (!postprocess) {
    postprocessPanel.textContent = "";
    return;
  }
  postprocessPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(postprocess, null, 2))}</pre>`;
};

const renderKanban = (taskwarrior) => {
  if (!taskwarrior || !taskwarrior.tasks) {
    kanbanPanel.textContent = "";
    return;
  }
  const columns = {};
  for (const task of taskwarrior.tasks) {
    const status = task.status || "unknown";
    if (!columns[status]) columns[status] = [];
    columns[status].push(task);
  }
  const order = ["pending", "waiting", "recurring", "completed", "deleted", "unknown"];
  const columnHtml = order
    .filter((status) => columns[status] && columns[status].length)
    .map((status) => {
      const cards = columns[status]
        .map((task) => {
          const tags = (task.tags || []).join(", ");
          return `<div class="kanban-card"><div class="kanban-title">${escapeHtml(task.description || "")}</div><div class="kanban-meta">${escapeHtml(tags)}</div></div>`;
        })
        .join("");
      return `<div class="kanban-column"><h3>${status}</h3>${cards}</div>`;
    })
    .join("");
  kanbanPanel.innerHTML = `<div class="kanban-board">${columnHtml}</div>`;
};

const renderTaskCapture = (capture) => {
  if (!capture) {
    taskCapturePanel.textContent = "";
    return;
  }
  taskCapturePanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(capture, null, 2))}</pre>`;
};

const renderTaskTemplates = (templates) => {
  if (!templates) {
    taskTemplatesPanel.textContent = "";
    return;
  }
  taskTemplatesPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(templates, null, 2))}</pre>`;
};

const renderKatas = (katas) => {
  if (!katas || !katas.phases) {
    katasPanel.textContent = "";
    return;
  }
  katasPanel.innerHTML = katas.phases
    .map((phase) => {
      const steps = (phase.steps || [])
        .map((step) => `<div class="kata-step">${escapeHtml(step)}</div>`)
        .join("");
      return `<div class="kata-phase"><h3>${phase.name}</h3><div class="kata-steps">${steps}</div></div>`;
    })
    .join("");
};

const renderRouting = (routing) => {
  if (!routing) {
    routingPanel.textContent = "";
    return;
  }
  routingPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(routing, null, 2))}</pre>`;
};

const renderIterations = (iterations, meta) => {
  if (!iterations || !iterations.length) {
    iterationsPanel.textContent = "";
    return;
  }
  const payload = { iterations, meta };
  iterationsPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
};

const renderRecovery = (recovery) => {
  if (!recovery) {
    recoveryPanel.textContent = "";
    return;
  }
  recoveryPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(recovery, null, 2))}</pre>`;
};

const renderSelection = (selection) => {
  if (!selection) {
    selectionPanel.textContent = "";
    return;
  }
  selectionPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(selection, null, 2))}</pre>`;
};

const renderTuning = (tuning) => {
  if (!tuning) {
    tuningPanel.textContent = "";
    return;
  }
  tuningPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(tuning, null, 2))}</pre>`;
};

const renderReconfig = (reconfig) => {
  if (!reconfig) {
    reconfigPanel.textContent = "";
    return;
  }
  reconfigPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(reconfig, null, 2))}</pre>`;
};

const renderABTest = (abtest) => {
  if (!abtest) {
    abtestPanel.textContent = "";
    return;
  }
  abtestPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(abtest, null, 2))}</pre>`;
};

const renderGrade = (grade) => {
  if (!grade) {
    gradePanel.textContent = "";
    return;
  }
  gradePanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(grade, null, 2))}</pre>`;
};

const renderTimings = (timings) => {
  if (!timings) {
    timingsPanel.textContent = "";
    return;
  }
  timingsPanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(timings, null, 2))}</pre>`;
};

const connectStatusStream = () => {
  if (window.__harnessWS) return;
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/api/v2/ws/deltas`);
  window.__harnessWS = ws;
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (!activeRequestId || data.request_id !== activeRequestId) return;
      if (data.type === "harness_status") {
        statusEvents.push(data);
        renderStatus();
      }
      if (data.type === "harness_token") {
        if (!streamTarget) {
          streamTarget = addMessage("assistant", "");
        }
        streamBuffer += data.token;
        streamTarget.innerHTML = formatResponse(streamBuffer);
        chatWindow.scrollTop = chatWindow.scrollHeight;
      }
    } catch (_err) {
      // ignore
    }
  };
  ws.onclose = () => {
    window.__harnessWS = null;
    setTimeout(connectStatusStream, 1000);
  };
};
const renderTrace = (trace) => {
  if (!trace) {
    tracePanel.textContent = "";
    return;
  }
  tracePanel.innerHTML = `
    <pre>${escapeHtml(JSON.stringify(trace, null, 2))}</pre>
  `;
};

const renderAvailable = (tools) => {
  if (!tools) {
    availablePanel.textContent = "";
    return;
  }
  availablePanel.innerHTML = `<pre>${escapeHtml(JSON.stringify(tools, null, 2))}</pre>`;
};

const renderToolGlossary = (tools) => {
  if (!toolGlossaryPanel) return;
  const autoToolGlossary = {
    greptile: "Codebase MCP tool discovery + targeted queries.",
    lint: "Runs Ruff checks for Python linting.",
    jj: "Shows Jujutsu status/diff for repo context.",
    taskwarrior: "Summarizes Taskwarrior backlog and capture.",
    taskwarrior_mcp: "Taskwarrior MCP actions (if configured).",
    preflight: "Checks file paths, types, and metadata.",
    mermaid: "Generates a quick reasoning graph from keywords.",
    vision: "Calls a vision LLM on attached images.",
    vision_pipeline: "YOLO-based detection/segmentation pipeline.",
    browser: "Generic MCP browser automation.",
    playwright: "Playwright MCP for browsing/testing.",
    chrome_devtools: "Chrome DevTools MCP for rich browser control.",
  };
  const entries = new Map();
  (tools || []).forEach((tool) => {
    entries.set(tool.name, tool.description || "");
  });
  Object.entries(autoToolGlossary).forEach(([name, desc]) => {
    if (!entries.has(name)) entries.set(name, desc);
  });
  toolGlossaryPanel.innerHTML = Array.from(entries.entries())
    .map(
      ([name, desc]) => `
        <div class="glossary-card">
          <div class="glossary-name">${escapeHtml(name)}</div>
          <div class="glossary-desc">${escapeHtml(desc || "")}</div>
        </div>
      `,
    )
    .join("");
};

const renderAttachments = () => {
  if (!attachmentsListEl) {
    return;
  }
  if (!attachments.length) {
    attachmentsListEl.textContent = "";
    return;
  }
  attachmentsListEl.innerHTML = attachments
    .map(
      (item) => `
    <div class="attachment-item">
      <img src="${item.preview}" alt="attachment" />
      <div class="attachment-path">${escapeHtml(item.path)}</div>
    </div>
  `,
    )
    .join("");
};

const uploadAttachment = async (file) => {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/v2/files/upload", { method: "POST", body: form });
  if (!resp.ok) {
    throw new Error("upload failed");
  }
  const data = await resp.json();
  return data.path || data.relative_path;
};

const loadFileTree = async (path) => {
  if (!filesListEl || !filesPathEl) return;
  const resp = await fetch(`/api/v2/files/tree?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    filesListEl.textContent = "Failed to load files.";
    return;
  }
  const data = await resp.json();
  currentPath = data.path || ".";
  filesPathEl.textContent = `Path: ${currentPath}`;
  filesListEl.innerHTML = (data.entries || [])
    .map((entry) => {
      const icon = entry.type === "dir" ? "📁" : "📄";
      return `<div class="file-item" data-path="${entry.path}" data-type="${entry.type}"><span>${icon} ${escapeHtml(entry.name)}</span><span>${entry.size || ""}</span></div>`;
    })
    .join("");
};

const loadFileContent = async (path) => {
  if (!fileViewerEl) return;
  const resp = await fetch(`/api/v2/files/read?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    fileViewerEl.textContent = "Failed to read file.";
    return;
  }
  const data = await resp.json();
  if (data.binary) {
    fileViewerEl.textContent = "Binary file. Download to view.";
    return;
  }
  fileViewerEl.textContent = data.content || "";
};

const renderMermaid = (diagram) => {
  if (!diagram) {
    mermaidPanel.textContent = "";
    return;
  }
  mermaidPanel.innerHTML = "";
  if (window.mermaid) {
    const container = document.createElement("div");
    container.className = "mermaid";
    container.textContent = diagram;
    mermaidPanel.appendChild(container);
    try {
      window.mermaid.init(undefined, container);
    } catch (_e) {
      mermaidPanel.innerHTML = `<pre>${diagram}</pre>`;
    }
  } else {
    mermaidPanel.innerHTML = `<pre>${diagram}</pre>`;
  }
};

const callHarness = async (message, mode) => {
  const payload = { message, request_id: activeRequestId };
  if (mode && mode !== "auto") {
    payload.mode = mode;
  }
  if (iterationsInput) {
    const raw = Number(iterationsInput.value || 1);
    if (!iterationsAuto?.checked && Number.isFinite(raw)) {
      payload.iterations = Math.min(Math.max(raw, 1), 5);
    }
  }
  if (abTestToggle?.checked) {
    payload.ab_test = true;
  }
  if (gradeToggle?.checked) {
    payload.grade = true;
  }
  if (researchToggle?.checked) {
    payload.research = true;
  }
  if (citationsToggle?.checked) {
    payload.citations = true;
  }
  if (promptToggle) {
    payload.prompt_enhance = promptToggle.checked;
  }
  if (tuningToggle?.checked) {
    payload.tuning = true;
  }
  if (toolSelectionToggle) {
    payload.tool_selection = toolSelectionToggle.checked;
  }
  if (taskCaptureToggle?.checked) {
    payload.task_capture = true;
  }
  if (taskTemplatesToggle?.checked) {
    payload.task_templates = true;
  }
  const autoTools = Array.from(document.querySelectorAll(".auto-tool"))
    .filter((el) => el.checked)
    .map((el) => el.value);
  if (autoTools.length) {
    payload.auto_tools = autoTools;
  }
  let resp;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      resp = await fetch("/api/v2/harness/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      break;
    } catch (err) {
      if (attempt === 2) {
        throw err;
      }
      await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)));
    }
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    let body = "";
    try {
      const data = await resp.json();
      body = JSON.stringify(data, null, 2);
      if (data && typeof data === "object" && "detail" in data) {
        detail =
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail, null, 2);
      } else {
        detail = body;
      }
    } catch (_err) {
      body = await resp.text();
      detail = body || resp.statusText;
    }
    console.error("Harness API error", { status: resp.status, detail, body });
    throw new Error(detail);
  }
  return resp.json();
};

sendBtn.addEventListener("click", async () => {
  const message = messageInput.value.trim();
  if (!message) return;
  connectStatusStream();
  activeRequestId = crypto.randomUUID();
  statusEvents = [];
  streamTarget = null;
  streamBuffer = "";
  renderStatus();
  scopePanel.textContent = "";
  researchPanel.textContent = "";
  promptPanel.textContent = "";
  postprocessPanel.textContent = "";
  taskCapturePanel.textContent = "";
  taskTemplatesPanel.textContent = "";
  tasksPanel.textContent = "";
  kanbanPanel.textContent = "";
  katasPanel.textContent = "";
  selectionPanel.textContent = "";
  routingPanel.textContent = "";
  iterationsPanel.textContent = "";
  recoveryPanel.textContent = "";
  tuningPanel.textContent = "";
  reconfigPanel.textContent = "";
  abtestPanel.textContent = "";
  gradePanel.textContent = "";
  timingsPanel.textContent = "";
  toolsPanel.textContent = "";
  tracePanel.textContent = "";
  if (visionPanel) {
    visionPanel.textContent = "";
  }
  mermaidPanel.textContent = "";
  availablePanel.textContent = "";
  if (toolGlossaryPanel) {
    toolGlossaryPanel.textContent = "";
  }
  let combinedMessage = message;
  if (attachments.length) {
    combinedMessage += `\n\nAttachments:\n${attachments.map((item) => item.path).join("\n")}`;
  }
  addMessage("user", combinedMessage);
  messageInput.value = "";
  addMessage("system", "Running harness...");
  try {
    const data = await callHarness(combinedMessage, modeSelect.value);
    console.debug("Harness response", data);
    if (streamTarget) {
      streamTarget.innerHTML = formatResponse(data.response || streamBuffer || "(no response)");
    } else {
      addMessage("assistant", data.response || "(no response)");
    }
    renderScope(data.scope);
    renderResearch(data.research);
    renderPrompt(data.prompt_enhancement);
    renderPostprocess(data.postprocess);
    renderTaskCapture(data.task_capture);
    renderTaskTemplates(data.task_templates);
    renderKatas(data.katas);
    renderTaskwarrior(data.taskwarrior);
    renderSelection(data.tool_selection);
    renderRouting(data.model_routing);
    renderIterations(data.iterations, {
      iterations_used: data.iterations_used,
      iterations_auto: data.iterations_auto,
    });
    renderRecovery(data.recovery);
    renderTuning(data.tuning);
    renderReconfig(data.tool_reconfig);
    renderABTest(data.ab_test);
    renderGrade(data.grade);
    renderTimings(data.timings);
    renderTools(data.tools_used);
    renderVision(data.tools_used);
    renderTrace(data.trace);
    renderMermaid(data.mermaid);
    renderAvailable(data.available_tools);
    renderToolGlossary(data.available_tools);
  } catch (err) {
    console.error("Harness UI error", err);
    addMessage("assistant", `Error: ${err.message}`);
  }
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendBtn.click();
  }
});

if (iterationsAuto) {
  const syncIterations = () => {
    if (!iterationsInput) return;
    iterationsInput.disabled = iterationsAuto.checked;
  };
  iterationsAuto.addEventListener("change", syncIterations);
  syncIterations();
}

if (themeSelect) {
  const storedTheme = localStorage.getItem("harness-theme") || "catppuccin";
  document.body.classList.add(`theme-${storedTheme}`);
  const lightThemes = new Set(["catppuccin", "github"]);
  const applyThemeMode = (theme) => {
    document.body.classList.toggle("theme-light", lightThemes.has(theme));
    document.body.classList.toggle("theme-dark", !lightThemes.has(theme));
  };
  applyThemeMode(storedTheme);
  themeSelect.value = storedTheme;
  themeSelect.addEventListener("change", () => {
    const value = themeSelect.value;
    document.body.className = document.body.className
      .split(" ")
      .filter((cls) => !cls.startsWith("theme-"))
      .join(" ");
    document.body.classList.add(`theme-${value}`);
    applyThemeMode(value);
    localStorage.setItem("harness-theme", value);
  });
}

if (fileInputEl) {
  fileInputEl.addEventListener("change", async () => {
    const file = fileInputEl.files?.[0];
    if (!file) return;
    try {
      const path = await uploadAttachment(file);
      const preview = URL.createObjectURL(file);
      attachments.push({ path, preview });
      renderAttachments();
    } catch (err) {
      console.error(err);
    } finally {
      fileInputEl.value = "";
    }
  });
}

if (filesListEl) {
  filesListEl.addEventListener("click", (event) => {
    const target = event.target.closest(".file-item");
    if (!target) return;
    const path = target.getAttribute("data-path");
    const type = target.getAttribute("data-type");
    if (type === "dir") {
      loadFileTree(path);
    } else {
      loadFileContent(path);
    }
  });
  loadFileTree(currentPath);
}

chatWindow.addEventListener("click", (event) => {
  const btn = event.target.closest(".copy-btn");
  if (!btn) return;
  if (btn.dataset.copy === "message") {
    const msg = btn.closest(".msg");
    if (!msg) return;
    const raw = msg.dataset.raw || "";
    copyToClipboard(raw);
    btn.textContent = "Copied";
    setTimeout(() => {
      btn.textContent = "Copy";
    }, 1200);
    return;
  }
  const code = btn.getAttribute("data-code") || "";
  copyToClipboard(code.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&"));
  btn.textContent = "Copied";
  setTimeout(() => {
    btn.textContent = "Copy";
  }, 1200);
});

const copyChatBtn = document.getElementById("copy-chat");
if (copyChatBtn) {
  copyChatBtn.addEventListener("click", () => {
    const messages = Array.from(chatWindow.querySelectorAll(".msg"));
    const lines = messages
      .map((msg) => {
        const role = msg.classList.contains("user")
          ? "User"
          : msg.classList.contains("assistant")
          ? "Assistant"
          : "System";
        return `${role}:\n${msg.dataset.raw || ""}`;
      })
      .join("\n\n");
    copyToClipboard(lines);
  });
}

const copyLastBtn = document.getElementById("copy-last");
if (copyLastBtn) {
  copyLastBtn.addEventListener("click", () => {
    const messages = Array.from(chatWindow.querySelectorAll(".msg.assistant"));
    const last = messages[messages.length - 1];
    if (!last) return;
    copyToClipboard(last.dataset.raw || "");
  });
}
