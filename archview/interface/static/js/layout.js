let firstLoad = true;

// dagre keeps siblings tight (NODE_SEP); FOLDER_GAP adds breathing room around
// folder boxes afterwards. Both apply only during runLayout (first load / reset).
const NODE_SEP = 18;
const FOLDER_GAP = 70;

function shiftNodeY(n, dy) {
  if (n.isParent()) {
    n.descendants().filter(d => d.isChildless()).forEach(d => {
      const p = d.position();
      d.position({ x: p.x, y: p.y + dy });
    });
  } else {
    const p = n.position();
    n.position({ x: p.x, y: p.y + dy });
  }
}

// Within each sibling group, ensure FOLDER_GAP of space before/after a folder
// box, shifting the rest of the group down. Only adds space — never overlaps.
function separateFolders() {
  const isFolder = n => n.data('is_folder') || compoundNodes.has(n.id());
  const groups = {};
  cy.nodes(':visible').forEach(n => {
    const key = n.parent().length ? n.parent().id() : '';
    (groups[key] = groups[key] || []).push(n);
  });
  Object.values(groups).forEach(list => {
    if (list.length < 2) return;
    list.sort((a, b) => a.boundingBox().y1 - b.boundingBox().y1);
    let delta = 0;
    for (let i = 1; i < list.length; i++) {
      if (delta) shiftNodeY(list[i], delta);
      if (!isFolder(list[i]) && !isFolder(list[i - 1])) continue;
      const gap = list[i].boundingBox().y1 - list[i - 1].boundingBox().y2;
      if (gap < FOLDER_GAP) {
        const extra = FOLDER_GAP - gap;
        shiftNodeY(list[i], extra);
        delta += extra;
      }
    }
  });
}

// Position freshly-added nodes near their folder siblings without touching any
// existing node. New files appear next to their folder; nothing else moves.
function placeNewNodesNearSiblings(addedNodes) {
  const added = new Set(addedNodes);
  addedNodes.forEach(id => {
    const n = cy.getElementById(id);
    if (!n.length || n.hidden()) return;
    const parent = n.parent();
    if (parent.length) {
      const sibs = parent.children().filter(s =>
        s.id() !== id && !s.hidden() && !added.has(s.id()));
      if (sibs.length) {
        let anchor = sibs[0];
        sibs.forEach(s => { if (s.boundingBox().y2 > anchor.boundingBox().y2) anchor = s; });
        n.position({ x: anchor.position().x, y: anchor.boundingBox().y2 + NODE_SEP + n.boundingBox().h / 2 });
      } else {
        n.position({ ...parent.position() });  // first child: sit on the folder
      }
    } else {
      // top-level module: drop it below the current graph so it overlaps nothing
      const bb = cy.elements(':visible').boundingBox();
      n.position({ x: bb.x1 + n.boundingBox().w / 2, y: bb.y2 + NODE_SEP + n.boundingBox().h / 2 });
    }
    userPositions[id] = { ...n.position() };
  });
}

// Pack each folder's children into a near-square grid (centered on the folder's
// laid-out position) so folders aren't tall single columns. Deepest folders
// first, so a parent grids its sub-folders at their final size.
const GRID_GAP = 14;
function gridFolderChildren() {
  const depth = id => { let d = 0, p = cy.getElementById(id).parent(); while (p.length) { d++; p = p.parent(); } return d; };
  [...compoundNodes].sort((a, b) => depth(b) - depth(a)).forEach(fid => {
    const folder = cy.getElementById(fid);
    const kids = folder.children();
    const n = kids.length;
    if (n < 2) return;
    const cw = Math.max(...kids.map(k => k.boundingBox().w)) + GRID_GAP;
    const chh = Math.max(...kids.map(k => k.boundingBox().h)) + GRID_GAP;
    // Choose the column count that makes the grid's footprint most square.
    let cols = 1, best = Infinity;
    for (let c = 1; c <= n; c++) {
      const diff = Math.abs(c * cw - Math.ceil(n / c) * chh);
      if (diff < best) { best = diff; cols = c; }
    }
    const rows = Math.ceil(n / cols);
    const ctr = folder.position();
    const x0 = ctr.x - (cols - 1) * cw / 2;
    const y0 = ctr.y - (rows - 1) * chh / 2;
    kids.forEach((k, i) => {
      k.position({ x: x0 + (i % cols) * cw, y: y0 + Math.floor(i / cols) * chh });
    });
  });
}

function shiftSubtree(n, dx, dy) {
  const leaves = n.isParent() ? n.descendants().filter(d => d.isChildless()) : n;
  leaves.forEach(d => { const p = d.position(); d.position({ x: p.x + dx, y: p.y + dy }); });
}

// A collapsed folder's own position() is unreliable (pulled toward its hidden
// children's bbox), so we locate it by the centroid of its leaf descendants.
function leafCentroid(n) {
  const leaves = n.isParent() ? n.descendants().filter(d => d.isChildless()) : n;
  let cx = 0, cy_ = 0;
  leaves.forEach(l => { const p = l.position(); cx += p.x; cy_ += p.y; });
  return { x: cx / leaves.length, y: cy_ / leaves.length };
}

const COLLAPSED_ROW = 64;  // height of a collapsed folder box (style: 40 + padding/border)

// The expanded dagre spaces top-level FOLDERS for their (huge) expanded heights,
// leaving them far apart once collapsed. Re-stack only the top-level folders
// tightly by their leaf centroid (reliable; a collapsed folder's own position()
// is not). Loose top-level nodes keep their dagre spot — they have no expanded
// height to compensate for, and a folder-less project must stay untouched.
function compactTopLevel() {
  const folders = cy.nodes().filter(n =>
    !n.parent().length && !n.hidden() && compoundNodes.has(n.id()));
  if (folders.length >= 2) {
    const items = folders.map(n => ({ n, c: leafCentroid(n) })).sort((a, b) => a.c.y - b.c.y);
    let cursor = items[0].c.y;
    items.forEach(it => {
      shiftSubtree(it.n, 0, cursor - it.c.y);
      cursor += COLLAPSED_ROW + FOLDER_GAP;
    });
  }
  updateProxyEdges();
  cy.nodes().forEach(n => {
    const id = n.id();
    if (n.isChildless()) userPositions[id] = { ...n.position() };
    else if (compoundNodes.has(id) && !expandedFolders.has(id)) userPositions[id] = leafCentroid(n);
  });
}

// Dagre runs ONCE on first load (and on explicit "Reset layout"). Folders are
// expanded for it so every child gets a real position; collapse only hides
// afterwards. animate:false — nodes never fly between positions. When restoring
// a saved layout, pass fresh=false: skip the grid/spacing passes so the user's
// saved child positions survive (the transform still pins them).
function runLayout(fresh = true) {
  applyCollapse();
  cy.layout({
    name: 'dagre',
    rankDir: 'LR',
    nodeSep: NODE_SEP,
    rankSep: 20,
    edgeSep: 8,
    compound: true,
    animate: false,
    fit: false,
    padding: 48,
    // Pin manually-placed/saved nodes; let dagre place the rest. Expanded
    // compounds float — their position derives from their children.
    transform: (node, pos) => {
      const id = node.id();
      if (compoundNodes.has(id) && expandedFolders.has(id)) return pos;
      return userPositions[id] || pos;
    },
  }).run();
  if (fresh) {
    separateFolders();
    gridFolderChildren();  // last word on intra-folder layout, so grids stay square
  }
  applyFocus();
}

function setStatus(msg, ok = true) {
  statusEl.textContent = msg;
  statusEl.style.color = ok ? 'var(--green)' : 'var(--red)';
}
