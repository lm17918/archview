// ── Node focus ───────────────────────────────────────────────────────────
const selectedNodes = new Set();

function applyFocus() {
  // Prune stale/hidden IDs left over from graph refresh or folder collapse
  selectedNodes.forEach(id => {
    const n = cy.getElementById(id);
    if (!n.length || !n.visible()) selectedNodes.delete(id);
  });
  if (selectedNodes.size === 0) {
    cy.elements().removeClass('faded highlighted');
    if (hoveredNode) renderNodeTooltip(hoveredNode);
    return;
  }
  let neighborhood = cy.collection();
  selectedNodes.forEach(id => {
    const n = cy.getElementById(id);
    if (n.length) neighborhood = neighborhood.union(n.closedNeighborhood());
  });
  // also include proxy edges where a selected node is an endpoint
  cy.edges('[?is_proxy]').forEach(e => {
    if (selectedNodes.has(e.data('source')) || selectedNodes.has(e.data('target'))) {
      neighborhood = neighborhood.union(e);
    }
  });
  cy.elements().removeClass('highlighted').addClass('faded');
  neighborhood.removeClass('faded').addClass('highlighted');
  neighborhood.nodes().forEach(n => {
    let parent = n.parent();
    while (parent && parent.length > 0) {
      parent.removeClass('faded');
      parent = parent.parent();
    }
  });
  if (hoveredNode && !hoveredNode.hasClass('faded')) renderNodeTooltip(hoveredNode);
}

cy.on('tap', 'node', evt => {
  const node = evt.target;
  if (isCollapsible(node)) {
    if (selectedNodes.size > 0) {
      selectedNodes.clear();
      cy.elements().removeClass('faded highlighted');
    }
    toggleFolder(node.id());
    return;
  }
  const id = node.id();
  if (selectedNodes.has(id)) selectedNodes.delete(id);
  else selectedNodes.add(id);
  applyFocus();
});

cy.on('tap', evt => {
  if (evt.target === cy) {
    selectedNodes.clear();
    cy.elements().removeClass('faded highlighted');
    if (hoveredNode) renderNodeTooltip(hoveredNode);
  }
});

let hoveredNode = null;

function renderNodeTooltip(node) {
  const d = node.data();
  const focused = node.hasClass('highlighted');
  tooltip.querySelector('.tt-name').textContent = d.label;
  tooltip.querySelector('.tt-doc').textContent = d.docstring || '(no docstring)';
  const labels = { entry: 'Entry Point', leaf: 'Utility', intermediate: 'Connector', isolated: 'Isolated' };
  tooltip.querySelector('.tt-type').textContent = labels[d.type] || d.type;
  const symsEl = tooltip.querySelector('.tt-symbols');
  if (focused && d.symbols) {
    symsEl.innerHTML = renderSymbolLines(d.symbols);
    symsEl.style.display = 'block';
  } else {
    symsEl.style.display = 'none';
  }
  tooltip.style.display = 'block';
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderSymbolLines(text) {
  return text.split('\n').map(l => {
    const [type, ...rest] = l.split(' ');
    return `<span style="color:#8b7cf8;font-weight:700">${escapeHtml(type)}</span> <span style="color:#fff;font-weight:500">${escapeHtml(rest.join(' '))}</span>`;
  }).join('<br>');
}

function hideTooltip() {
  tooltip.style.display = 'none';
}

function moveTooltip(e) {
  tooltip.style.left = (e.clientX + 16) + 'px';
  tooltip.style.top  = (e.clientY + 16) + 'px';
}

cy.on('mouseover', 'node', evt => {
  if (evt.target.hasClass('faded')) return;
  if (isCollapsible(evt.target)) return;
  hoveredNode = evt.target;
  renderNodeTooltip(hoveredNode);
});

cy.on('mousemove', 'node', evt => moveTooltip(evt.originalEvent));
cy.on('mouseout',  'node', () => { hoveredNode = null; hideTooltip(); });

cy.on('mouseover', 'edge.highlighted', evt => {
  const d = evt.target.data();
  if (!d.label) return;
  tooltip.querySelector('.tt-name').textContent = '';
  tooltip.querySelector('.tt-doc').innerHTML = renderSymbolLines(d.label);
  tooltip.querySelector('.tt-type').textContent = '';
  tooltip.querySelector('.tt-symbols').style.display = 'none';
  tooltip.style.display = 'block';
});

cy.on('mousemove', 'edge', evt => moveTooltip(evt.originalEvent));
cy.on('mouseout',  'edge', hideTooltip);

cy.on('dblclick', 'node', evt => {
  if (isCollapsible(evt.target)) return;
  const filepath = evt.target.data('filepath');
  if (!filepath) return;
  fetch('/open', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file: filepath }),
  });
});
