// SSE pushes updates instantly; this poll is only a fallback if the stream drops.
const REFRESH_MS = 30000;
const statusEl = document.getElementById('status');
const tooltip = document.getElementById('tooltip');

const userPositions = {};
let savedExpanded = null;  // folder ids that were expanded when saved (null = legacy file)

async function loadSavedPositions() {
  try {
    const resp = await fetch('/positions.json?t=' + Date.now());
    if (!resp.ok) return;
    const data = await resp.json();
    if (data && data.positions) {            // new format: { positions, expanded }
      Object.assign(userPositions, data.positions);
      savedExpanded = Array.isArray(data.expanded) ? data.expanded : null;
    } else {
      Object.assign(userPositions, data);    // legacy: flat { id: {x,y} } map
    }
  } catch(e) {}
}

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: [],
  style: cyStyle,
  layout: { name: 'preset' },
  wheelSensitivity: 0.3,
});

cy.on('dragfree', 'node', evt => {
  const node = evt.target;
  const id = node.id();
  // Dragging a folder box moves its children too (even hidden ones); persist
  // their new positions so collapse/expand keeps everything in place.
  node.descendants().forEach(d => { userPositions[d.id()] = { ...d.position() }; });
  // An expanded compound's own position is derived from its children — don't pin it.
  if (!(compoundNodes.has(id) && expandedFolders.has(id))) {
    userPositions[id] = { ...node.position() };
  }
});
