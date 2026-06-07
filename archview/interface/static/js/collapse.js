// ── Folder collapse / expand ──────────────────────────────────────────────
// Collapsing only HIDES a folder's children in place — it never detaches them
// or re-runs the layout. The box shrinks via the .collapsed style; dragging a
// collapsed box carries its hidden children along, so expanding restores them
// exactly where they were. Nothing moves on its own.
const expandedFolders = new Set();
const compoundNodes = new Set();   // ids of nodes that are folders/compounds

function getCollapsedAncestor(nodeId) {
  const n = cy.getElementById(nodeId);
  if (!n.length || !n.hidden()) return nodeId;
  // Walk up to the nearest visible ancestor (the collapsed folder box).
  let p = n.parent();
  while (p.length && p.hidden()) p = p.parent();
  return p.length ? p.id() : nodeId;
}

function updateProxyEdges() {
  cy.edges('[?is_proxy]').remove();
  const proxyLabels = {};
  cy.edges().not('[?is_proxy]').forEach(edge => {
    const src = getCollapsedAncestor(edge.data('source'));
    const tgt = getCollapsedAncestor(edge.data('target'));
    if (src === tgt) return;
    if (src === edge.data('source') && tgt === edge.data('target')) return;
    const key = `${src}→${tgt}`;
    if (!proxyLabels[key]) proxyLabels[key] = { src, tgt, lines: new Set() };
    const label = edge.data('label');
    if (label) label.split('\n').forEach(l => { if (l.trim()) proxyLabels[key].lines.add(l.trim()); });
  });
  for (const [key, info] of Object.entries(proxyLabels)) {
    const label = [...info.lines].sort().join('\n');
    cy.add({ data: { id: `__proxy__${key}`, source: info.src, target: info.tgt, is_proxy: true, label } });
  }
}

// A node is visible only if every folder above it is expanded.
function isVisibleByFolders(node) {
  let p = node.parent();
  while (p.length) {
    if (!expandedFolders.has(p.id())) return false;
    p = p.parent();
  }
  return true;
}

function applyCollapse() {
  // A compound with all children hidden reports position {0,0}. So, before
  // hiding, remember where each box-about-to-collapse currently sits, then
  // re-apply it afterwards: this pins the box and keeps its (hidden) children
  // exactly in place via their preserved relative offsets.
  cy.nodes().forEach(n => {
    const id = n.id();
    if (compoundNodes.has(id) && !expandedFolders.has(id) && n.children(':visible').nonempty()) {
      userPositions[id] = { ...n.position() };
    }
  });

  cy.nodes().forEach(n => {
    if (isVisibleByFolders(n)) n.show();
    else n.hide();
    if (compoundNodes.has(n.id())) {
      n.toggleClass('collapsed', !expandedFolders.has(n.id()));
    }
  });

  cy.nodes().forEach(n => {
    const id = n.id();
    if (compoundNodes.has(id) && !expandedFolders.has(id) && !n.hidden() && userPositions[id]) {
      n.position(userPositions[id]);
    }
  });

  updateProxyEdges();
}

function isCollapsible(node) {
  return node.data('is_folder') || compoundNodes.has(node.id());
}

function updateFolderLabels() {
  // Force a style recalc so label style functions (:parent / .collapsed) re-evaluate
  cy.nodes().filter(n => isCollapsible(n)).forEach(n => n.style());
}

// Toggle visibility only — no layout, no animation, no repositioning.
function toggleFolder(id) {
  if (expandedFolders.has(id)) expandedFolders.delete(id);
  else expandedFolders.add(id);
  applyCollapse();
  updateFolderLabels();
  cy.nodes(':hidden').forEach(n => selectedNodes.delete(n.id()));
  applyFocus();
  updateFolderButtonLabel();
}

function updateFolderButtonLabel() {
  const btn = document.getElementById('btn-folders');
  if (!btn) return;
  if (compoundNodes.size === 0) {
    btn.style.display = 'none';
    return;
  }
  btn.style.display = '';
  const anyExpanded = [...compoundNodes].some(id => expandedFolders.has(id));
  btn.textContent = anyExpanded ? 'Collapse all' : 'Expand all';
}
