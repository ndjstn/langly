const sendBtn = document.getElementById('send');
const metaEl = document.getElementById('meta');
const statusEl = document.getElementById('status');
const toolsEl = document.getElementById('tools');
const katasEl = document.getElementById('katas');
const researchEl = document.getElementById('research-panel');
const mermaidEl = document.getElementById('mermaid-panel');
const filesListEl = document.getElementById('files-list');
const filesPathEl = document.getElementById('files-path');
const fileViewerEl = document.getElementById('file-viewer');
const attachmentsListEl = document.getElementById('attachments-list');
const fileInputEl = document.getElementById('file-input');
const fullBtn = document.getElementById('full-view');
const operatorBtn = document.getElementById('operator-view');
const themeSelect = document.getElementById('theme-select');
const chatWindow = document.getElementById('chat-window');

const checked = (id) => document.getElementById(id).checked;

let activeRequestId = null;
let statusEvents = [];
let streamBuffer = '';
let streamTarget = null;
let attachments = [];
let currentPath = '.';

const statusIcon = (status) => {
  if (status === 'done' || status === 'completed') return '✓';
  if (status === 'running' || status === 'start') return '•';
  if (status === 'failed' || status === 'error') return '!';
  return '•';
};

const renderTimeline = (events) => {
  const stageOrder = [
    'scope', 'kata_before', 'tools', 'kata_during', 'research', 'model_routing',
    'iterations_plan', 'iteration_start', 'iteration_done', 'ab_test',
    'postprocess', 'grade', 'tuning', 'kata_after', 'complete'
  ];
  if (!events.length) return '';
  const lastStage = events[events.length - 1].stage;
  const lastIndex = stageOrder.indexOf(lastStage);
  const steps = stageOrder.map((stage, idx) => {
    const cls = idx < lastIndex ? 'done' : idx === lastIndex ? 'active' : '';
    return `<span class="status-step ${cls}">${stage.replace('_', ' ')}</span>`;
  }).join('');
  return `<div class="status-timeline">${steps}</div>`;
};

const renderStatus = () => {
  if (!statusEvents.length) {
    statusEl.textContent = '';
    return;
  }
  const last = statusEvents[statusEvents.length - 1];
  const progress = typeof last?.progress === 'number' ? Math.round(last.progress * 100) : null;
  const items = statusEvents.slice(-12).map(event => `
    <div class="status-row status-${event.status}">
      <span class="status-dot">${statusIcon(event.status)}</span>
      <span class="status-stage">${event.stage}</span>
      <span class="status-state">${event.status}</span>
      <span class="status-time">${event.timestamp?.split('T')[1]?.split('.')[0] || ''}</span>
    </div>
  `).join('');
  const progressHtml = progress === null ? '' : `<div class="progress"><div style="width:${progress}%"></div></div>`;
  statusEl.innerHTML = `${progressHtml}${renderTimeline(statusEvents)}<div class="status-list">${items}</div>`;
};

const renderTools = (tools) => {
  if (!tools) { toolsEl.textContent = ''; return; }
  toolsEl.innerHTML = tools.map(tool => {
    const output = tool.output ? escapeHtml(JSON.stringify(tool.output, null, 2)) : '';
    const stdout = escapeHtml(tool.stdout || '');
    const stderr = escapeHtml(tool.stderr || '');
    const duration = tool.duration_ms ? `${tool.duration_ms.toFixed(1)}ms` : '';
    return `
      <div class="tool-card">
        <div class="tool-meta">
          <span class="tool-name">${tool.name}</span>
          <span>${tool.status}</span>
          <span>${duration}</span>
          <span>attempts ${tool.attempts}</span>
          <span>retries ${tool.retries}</span>
        </div>
        ${stderr ? `<div class="tool-output">stderr:\n${escapeHtml(stderr)}</div>` : ''}
        ${stdout ? `<div class="tool-output">stdout:\n${escapeHtml(stdout)}</div>` : ''}
        ${output ? `<div class="tool-output">output:\n${escapeHtml(output)}</div>` : ''}
      </div>
    `;
  }).join('');
};

const renderKatas = (katas) => {
  if (!katas || !katas.phases) {
    katasEl.textContent = '';
    return;
  }
  katasEl.innerHTML = katas.phases.map(phase => {
    const steps = (phase.steps || []).map(step => `<div class="kata-step">${escapeHtml(step)}</div>`).join('');
    return `<div class="kata-phase"><h3>${phase.name}</h3><div class="kata-steps">${steps}</div></div>`;
  }).join('');
};

const renderResearch = (research) => {
  if (!research || !research.sources) {
    researchEl.textContent = '';
    return;
  }
  const items = research.sources.map((src, idx) => {
    const title = escapeHtml(src.title || `Source ${idx + 1}`);
    const url = escapeHtml(src.url || '');
    return `<li><a href="${url}" target="_blank" rel="noreferrer">${title}</a></li>`;
  }).join('');
  researchEl.innerHTML = `<ul class="sources-list">${items}</ul>`;
};

const renderMermaid = (diagram) => {
  if (!diagram) {
    mermaidEl.textContent = '';
    return;
  }
  mermaidEl.innerHTML = '';
  if (window.mermaid) {
    const container = document.createElement('div');
    container.className = 'mermaid';
    container.textContent = diagram;
    mermaidEl.appendChild(container);
    try { window.mermaid.init(undefined, container); } catch (_) {}
  } else {
    mermaidEl.textContent = diagram;
  }
};

const escapeHtml = (text) => {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

const linkify = (text) => {
  return text.replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>');
};

const formatResponse = (text) => {
  if (!text) return '';
  const parts = text.split('```');
  const html = parts.map((part, idx) => {
    if (idx % 2 === 0) {
      let escaped = escapeHtml(part);
      escaped = linkify(escaped);
      if (escaped.includes('Sources:')) {
        const sections = escaped.split('Sources:');
        const body = sections[0].trim();
        const sources = sections[1].trim().split('\n').filter(Boolean);
        const items = sources.map(line => {
          const cleaned = line.replace(/^\s*\[\d+\]\s*/, '');
          return `<li>${linkify(cleaned)}</li>`;
        }).join('');
        return `${body}\n\n<strong>Sources:</strong><ul class="sources-list">${items}</ul>`;
      }
      return escaped;
    }
    const lines = part.split('\n');
    const lang = escapeHtml(lines.shift() || '');
    const code = escapeHtml(lines.join('\n'));
    return `<pre class="code-block"><button class="copy-btn" data-code="${code}">Copy</button><code>${lang ? `<span class="code-lang">${lang}</span>\n` : ''}${code}</code></pre>`;
  }).join('');
  return html;
};

const addBubble = (role, text) => {
  const el = document.createElement('div');
  el.className = `chat-bubble ${role}`;
  el.innerHTML = formatResponse(text);
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return el;
};

const renderAttachments = () => {
  if (!attachmentsListEl) {
    return;
  }
  if (!attachments.length) {
    attachmentsListEl.textContent = '';
    return;
  }
  attachmentsListEl.innerHTML = attachments.map(item => `
    <div class="attachment-item">
      <img src="${item.preview}" alt="attachment" />
      <div class="attachment-path">${escapeHtml(item.path)}</div>
    </div>
  `).join('');
};

const uploadAttachment = async (file) => {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch('/upload', { method: 'POST', body: form });
  if (!resp.ok) {
    throw new Error('upload failed');
  }
  const data = await resp.json();
  return data.path;
};

const loadFileTree = async (path) => {
  if (!filesListEl || !filesPathEl) return;
  const resp = await fetch(`/files/tree?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    filesListEl.textContent = 'Failed to load files.';
    return;
  }
  const data = await resp.json();
  currentPath = data.path || '.';
  filesPathEl.textContent = `Path: ${currentPath}`;
  filesListEl.innerHTML = (data.entries || []).map(entry => {
    const icon = entry.type === 'dir' ? '📁' : '📄';
    return `<div class="file-item" data-path="${entry.path}" data-type="${entry.type}"><span>${icon} ${escapeHtml(entry.name)}</span><span>${entry.size || ''}</span></div>`;
  }).join('');
};

const loadFileContent = async (path) => {
  if (!fileViewerEl) return;
  const resp = await fetch(`/files/read?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    fileViewerEl.textContent = 'Failed to read file.';
    return;
  }
  const data = await resp.json();
  if (data.binary) {
    fileViewerEl.textContent = 'Binary file. Download to view.';
    return;
  }
  fileViewerEl.textContent = data.content || '';
};

const connectStatusStream = () => {
  if (window.__harnessWS) return;
  const ws = new WebSocket(window.HARNESS_WS);
  window.__harnessWS = ws;
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (!activeRequestId || data.request_id !== activeRequestId) return;
      if (data.type === 'harness_status') {
        statusEvents.push(data);
        renderStatus();
      }
      if (data.type === 'harness_token') {
        streamBuffer += data.token;
        if (streamTarget) {
          streamTarget.innerHTML = formatResponse(streamBuffer);
        }
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

const runHarness = async () => {
  const message = document.getElementById('message').value.trim();
  if (!message) return;
  metaEl.textContent = '';
  toolsEl.textContent = '';
  katasEl.textContent = '';
  researchEl.textContent = '';
  mermaidEl.textContent = '';
  statusEvents = [];
  streamBuffer = '';
  activeRequestId = crypto.randomUUID();
  connectStatusStream();

  let combinedMessage = message;
  if (attachments.length) {
    combinedMessage += `\n\nAttachments:\n${attachments.map(item => item.path).join('\n')}`;
  }
  addBubble('user', combinedMessage);
  streamTarget = addBubble('assistant', '');

  const payload = {
    message: combinedMessage,
    request_id: activeRequestId,
    research: checked('research'),
    citations: checked('citations'),
    prompt_enhance: checked('prompt_enhance'),
    tuning: checked('tuning'),
    tool_selection: checked('tool_selection'),
    task_capture: checked('task_capture'),
    task_templates: checked('task_templates')
  };
  const autoTools = Array.from(document.querySelectorAll('.auto-tool'))
    .filter((el) => el.checked)
    .map((el) => el.value);
  if (autoTools.length) {
    payload.auto_tools = autoTools;
  }

  const resp = await fetch('/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await resp.json();
  if (!resp.ok || data.error) {
    const errMsg = data.error || JSON.stringify(data, null, 2);
    if (streamTarget) streamTarget.textContent = errMsg;
    if (streamTarget) streamTarget.textContent = errMsg;
    return;
  }
  if (streamTarget) {
    streamTarget.innerHTML = formatResponse(data.response || streamBuffer || '');
  }
  metaEl.textContent = JSON.stringify({
    scope: data.scope,
    research: data.research,
    tuning: data.tuning,
    tool_selection: data.tool_selection,
    task_capture: data.task_capture
  }, null, 2);
  renderTools(data.tools_used);
  renderKatas(data.katas);
  renderResearch(data.research);
  renderMermaid(data.mermaid);
};

sendBtn.addEventListener('click', runHarness);

if (fileInputEl) {
  fileInputEl.addEventListener('change', async () => {
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
      fileInputEl.value = '';
    }
  });
}

if (filesListEl) {
  filesListEl.addEventListener('click', (event) => {
    const target = event.target.closest('.file-item');
    if (!target) return;
    const path = target.getAttribute('data-path');
    const type = target.getAttribute('data-type');
    if (type === 'dir') {
      loadFileTree(path);
    } else {
      loadFileContent(path);
    }
  });
  loadFileTree(currentPath);
}

chatWindow.addEventListener('click', (event) => {
  const btn = event.target.closest('.copy-btn');
  if (!btn) return;
  const code = btn.getAttribute('data-code') || '';
  navigator.clipboard.writeText(code.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'));
  btn.textContent = 'Copied';
  setTimeout(() => { btn.textContent = 'Copy'; }, 1200);
});

fullBtn.addEventListener('click', () => {
  document.body.classList.remove('mode-operator');
  fullBtn.classList.add('active');
  operatorBtn.classList.remove('active');
});

operatorBtn.addEventListener('click', () => {
  document.body.classList.add('mode-operator');
  operatorBtn.classList.add('active');
  fullBtn.classList.remove('active');
});

if (themeSelect) {
  const storedTheme = localStorage.getItem('flask-theme') || themeSelect.value;
  document.body.className = document.body.className.replace(/theme-[^\s]+/g, '').trim();
  document.body.classList.add(`theme-${storedTheme}`);
  const lightThemes = new Set(['catppuccin', 'github']);
  const applyThemeMode = (theme) => {
    document.body.classList.toggle('theme-light', lightThemes.has(theme));
    document.body.classList.toggle('theme-dark', !lightThemes.has(theme));
  };
  applyThemeMode(storedTheme);
  themeSelect.value = storedTheme;
  themeSelect.addEventListener('change', () => {
    const value = themeSelect.value;
    document.body.className = document.body.className.replace(/theme-[^\s]+/g, '').trim();
    document.body.classList.add(`theme-${value}`);
    applyThemeMode(value);
    localStorage.setItem('flask-theme', value);
  });
}
