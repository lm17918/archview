// ── Annotations ────────────────────────────────────────────────────────
const annoLayer = document.getElementById('anno-layer');
const annoViewport = document.getElementById('anno-viewport');
let activeTool = null;
let annotations = [];
let drawState = null;
let boxPreview = null;

function syncViewport() {
  const pan = cy.pan();
  const zoom = cy.zoom();
  annoViewport.style.transform = `translate(${pan.x}px,${pan.y}px) scale(${zoom})`;
}
cy.on('viewport', syncViewport);

async function loadAnnotations() {
  try {
    const resp = await fetch('/annotations.json?t=' + Date.now());
    if (resp.ok) annotations = await resp.json();
  } catch(e) {}
  renderAnnotations();
}

async function saveAnnotations() {
  try {
    await fetch('/annotations', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(annotations),
    });
  } catch(e) {}
}

function renderAnnotations() {
  annoViewport.innerHTML = '';
  const isEraser = activeTool === 'eraser';
  annoViewport.classList.toggle('eraser-active', isEraser);

  annotations.forEach(ann => {
    const el = document.createElement('div');
    el.dataset.id = ann.id;
    el.className = 'annotation anno-' + ann.type;

    if (ann.type === 'box') {
      el.style.left = ann.x + 'px';
      el.style.top = ann.y + 'px';
      el.style.width = ann.w + 'px';
      el.style.height = ann.h + 'px';
      el.style.borderColor = ann.color || '#8b7cf8';
      if (ann.label) {
        const lbl = document.createElement('span');
        lbl.className = 'anno-box-label';
        lbl.textContent = ann.label;
        lbl.style.color = ann.color || '#8b7cf8';
        el.appendChild(lbl);
      }
    } else if (ann.type === 'text') {
      el.style.left = ann.x + 'px';
      el.style.top = ann.y + 'px';
      el.textContent = ann.text;
      el.style.color = ann.color || '#ffffff';
      el.style.fontSize = (ann.fontSize || 16) + 'px';
    }

    if (isEraser) {
      el.addEventListener('click', () => {
        annotations = annotations.filter(a => a.id !== ann.id);
        renderAnnotations();
        saveAnnotations();
      });
    }

    annoViewport.appendChild(el);
  });
}

function screenToModel(clientX, clientY) {
  const rect = annoLayer.getBoundingClientRect();
  const pan = cy.pan();
  const zoom = cy.zoom();
  return {
    x: (clientX - rect.left - pan.x) / zoom,
    y: (clientY - rect.top - pan.y) / zoom,
  };
}

function setTool(tool) {
  activeTool = tool || null;
  document.querySelectorAll('.tool-btn').forEach(btn => {
    btn.classList.toggle('active', (btn.dataset.tool || null) === activeTool);
  });
  annoLayer.classList.remove('tool-active', 'tool-text');
  if (activeTool === 'box') annoLayer.classList.add('tool-active');
  else if (activeTool === 'text') annoLayer.classList.add('tool-active', 'tool-text');
  renderAnnotations();
}

document.querySelectorAll('.tool-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tool = btn.dataset.tool || null;
    setTool(activeTool === tool ? null : tool);
  });
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && activeTool) {
    if (drawState && boxPreview) { boxPreview.remove(); boxPreview = null; }
    drawState = null;
    setTool(null);
  }
});
