// Box drawing
annoLayer.addEventListener('mousedown', e => {
  if (activeTool !== 'box') return;
  const pos = screenToModel(e.clientX, e.clientY);
  drawState = { startX: pos.x, startY: pos.y };
  boxPreview = document.createElement('div');
  boxPreview.className = 'annotation anno-box anno-preview';
  boxPreview.style.borderColor = '#8b7cf8';
  boxPreview.style.left = pos.x + 'px';
  boxPreview.style.top = pos.y + 'px';
  boxPreview.style.width = '0px';
  boxPreview.style.height = '0px';
  annoViewport.appendChild(boxPreview);
  e.preventDefault();
});

annoLayer.addEventListener('mousemove', e => {
  if (activeTool !== 'box' || !drawState || !boxPreview) return;
  const pos = screenToModel(e.clientX, e.clientY);
  const x = Math.min(drawState.startX, pos.x);
  const y = Math.min(drawState.startY, pos.y);
  boxPreview.style.left = x + 'px';
  boxPreview.style.top = y + 'px';
  boxPreview.style.width = Math.abs(pos.x - drawState.startX) + 'px';
  boxPreview.style.height = Math.abs(pos.y - drawState.startY) + 'px';
});

function promptInline({ x, y, placeholder, extraClass, onCommit, onCancel }) {
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = placeholder;
  input.className = 'anno-input' + (extraClass ? ' ' + extraClass : '');
  input.style.left = x + 'px';
  input.style.top = y + 'px';
  annoViewport.appendChild(input);
  requestAnimationFrame(() => input.focus());

  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    const value = input.value.trim();
    input.remove();
    if (commit && value) onCommit(value);
    else if (onCancel) onCancel();  // empty commit == cancel; lets caller persist the bare box
  };
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); finish(true); }
    else if (ev.key === 'Escape') { ev.preventDefault(); finish(false); }
    ev.stopPropagation();
  });
  input.addEventListener('blur', () => finish(true));
}

annoLayer.addEventListener('mouseup', e => {
  if (activeTool !== 'box' || !drawState) return;
  const pos = screenToModel(e.clientX, e.clientY);
  const x = Math.min(drawState.startX, pos.x);
  const y = Math.min(drawState.startY, pos.y);
  const w = Math.abs(pos.x - drawState.startX);
  const h = Math.abs(pos.y - drawState.startY);
  if (boxPreview) { boxPreview.remove(); boxPreview = null; }
  drawState = null;
  if (w < 20 || h < 20) return;
  const id = 'ann_' + Date.now();
  annotations.push({ id, type: 'box', x, y, w, h, label: '', color: '#8b7cf8' });
  renderAnnotations();
  promptInline({
    x: x + 10, y: y - 13, placeholder: 'Label (optional)',
    onCommit: (value) => {
      const ann = annotations.find(a => a.id === id);
      if (ann) { ann.label = value; renderAnnotations(); saveAnnotations(); }
    },
    onCancel: () => { saveAnnotations(); },
  });
});

// Text placement
annoLayer.addEventListener('click', e => {
  if (activeTool !== 'text') return;
  const pos = screenToModel(e.clientX, e.clientY);
  promptInline({
    x: pos.x, y: pos.y - 10, placeholder: 'Type text…', extraClass: 'anno-input-text',
    onCommit: (text) => {
      annotations.push({ id: 'ann_' + Date.now(), type: 'text', x: pos.x, y: pos.y, text, color: '#ffffff', fontSize: 16 });
      renderAnnotations();
      saveAnnotations();
    },
  });
});

// Zoom pass-through while in annotation mode
annoLayer.addEventListener('wheel', e => {
  e.preventDefault();
  const rect = document.getElementById('cy').getBoundingClientRect();
  const level = cy.zoom() * (e.deltaY > 0 ? 0.9 : 1.1);
  cy.zoom({
    level: Math.max(0.1, Math.min(3, level)),
    renderedPosition: { x: e.clientX - rect.left, y: e.clientY - rect.top },
  });
  syncViewport();
}, { passive: false });
