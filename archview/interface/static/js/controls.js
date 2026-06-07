document.getElementById('btn-save').addEventListener('click', async () => {
  const allPositions = {};
  cy.nodes().forEach(n => {
    const id = n.id();
    if (compoundNodes.has(id) && expandedFolders.has(id)) return;  // derived, not pinned
    allPositions[id] = { ...n.position() };
  });
  try {
    const resp = await fetch('/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(allPositions),
    });
    if (resp.ok) {
      await resp.json();
      setStatus('Saved');
      Object.assign(userPositions, allPositions);
    } else {
      setStatus('Save failed: ' + resp.status, false);
    }
  } catch(e) { setStatus('Save error', false); }
});

// Reset layout: the only place (besides first load) that re-runs dagre. Lay out
// expanded so children get positions, then restore the current collapse state.
document.getElementById('btn-layout').addEventListener('click', () => {
  Object.keys(userPositions).forEach(k => delete userPositions[k]);
  const wasExpanded = new Set(expandedFolders);
  compoundNodes.forEach(id => expandedFolders.add(id));
  runLayout();
  expandedFolders.clear();
  wasExpanded.forEach(id => expandedFolders.add(id));
  applyCollapse();
  compactTopLevel();
  applyCollapse();
  updateFolderLabels();
  updateFolderButtonLabel();
  cy.animate({ fit: { eles: cy.elements(':visible'), padding: 48 } }, { duration: 400 });
});

// Collapse/expand all — visibility only, no layout, nothing moves.
document.getElementById('btn-folders').addEventListener('click', () => {
  const anyExpanded = [...compoundNodes].some(id => expandedFolders.has(id));
  if (anyExpanded) expandedFolders.clear();
  else compoundNodes.forEach(id => expandedFolders.add(id));
  applyCollapse();
  updateFolderLabels();
  cy.nodes(':hidden').forEach(n => selectedNodes.delete(n.id()));
  applyFocus();
  updateFolderButtonLabel();
});

document.getElementById('btn-fit').addEventListener('click', () => {
  cy.animate({ fit: { eles: cy.elements(), padding: 48 } }, { duration: 400 });
});

document.getElementById('btn-png').addEventListener('click', () => {
  const png = cy.png({ output: 'blob', bg: '#0a0a0d', scale: 2, full: true });
  const url = URL.createObjectURL(png);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'architecture.png';
  a.click();
  URL.revokeObjectURL(url);
  setStatus('PNG saved');
});

// ── Diff view ──────────────────────────────────────────────────────────
const diffSelect = document.getElementById('diff-ref');
let diffState = null;

async function loadRefs() {
  try {
    const resp = await fetch('/refs?t=' + Date.now());
    if (!resp.ok) return;
    const refs = await resp.json();
    // Clear existing options except the first
    while (diffSelect.options.length > 1) diffSelect.remove(1);

    if (refs.branches.length) {
      const grp = document.createElement('optgroup');
      grp.label = 'Branches';
      refs.branches.forEach(b => {
        const opt = document.createElement('option');
        opt.value = b; opt.textContent = b;
        grp.appendChild(opt);
      });
      diffSelect.appendChild(grp);
    }
    if (refs.tags.length) {
      const grp = document.createElement('optgroup');
      grp.label = 'Tags';
      refs.tags.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t; opt.textContent = t;
        grp.appendChild(opt);
      });
      diffSelect.appendChild(grp);
    }
    if (refs.commits.length) {
      const grp = document.createElement('optgroup');
      grp.label = 'Commits';
      refs.commits.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.hash;
        opt.textContent = c.hash.slice(0,7) + ' ' + c.message.slice(0,40);
        grp.appendChild(opt);
      });
      diffSelect.appendChild(grp);
    }
  } catch(e) {}
}

function clearDiff() {
  diffState = null;
  cy.elements('[?_diff_ghost]').remove();
  cy.elements().removeClass('diff-added diff-removed diff-modified');
}

function applyDiff(diff) {
  diffState = diff;

  // Add ghost elements for removed nodes/edges
  diff.removed_elements.forEach(el => {
    const d = { ...el.data, _diff_ghost: true };
    // Remove parent ref — ghost nodes are free-floating
    delete d.parent;
    cy.add({ data: d });
  });

  // Apply CSS classes
  diff.added_nodes.forEach(id => {
    const el = cy.getElementById(id);
    if (el.length) el.addClass('diff-added');
  });
  diff.removed_nodes.forEach(id => {
    const el = cy.getElementById(id);
    if (el.length) el.addClass('diff-removed');
  });
  diff.modified_nodes.forEach(id => {
    const el = cy.getElementById(id);
    if (el.length) el.addClass('diff-modified');
  });
  diff.added_edges.forEach(id => {
    const el = cy.getElementById(id);
    if (el.length) el.addClass('diff-added');
  });
  diff.removed_edges.forEach(id => {
    const el = cy.getElementById(id);
    if (el.length) el.addClass('diff-removed');
  });
  (diff.modified_edges || []).forEach(id => {
    const el = cy.getElementById(id);
    if (el.length) el.addClass('diff-modified');
  });

  // Run layout to place ghost nodes
  runLayout();
  cy.fit(cy.elements(':visible'), 48);

  const parts = [];
  if (diff.added_nodes.length) parts.push(`<span class="diff-badge diff-badge-add">+${diff.added_nodes.length}</span>`);
  if (diff.removed_nodes.length) parts.push(`<span class="diff-badge diff-badge-del">-${diff.removed_nodes.length}</span>`);
  const modCount = diff.modified_nodes.length + (diff.modified_edges || []).length;
  if (modCount) parts.push(`<span class="diff-badge diff-badge-mod">~${modCount}</span>`);
  statusEl.innerHTML = parts.length ? `Diff vs ${diff.ref} ` + parts.join(' ') : `Diff vs ${diff.ref} — no changes`;
}

diffSelect.addEventListener('change', async () => {
  clearDiff();
  const ref = diffSelect.value;
  if (!ref) {
    refresh();
    return;
  }
  setStatus('Computing diff…');
  try {
    const resp = await fetch('/diff?ref=' + encodeURIComponent(ref));
    if (!resp.ok) {
      const err = await resp.json();
      setStatus(err.error || 'Diff failed', false);
      diffSelect.value = '';
      return;
    }
    applyDiff(await resp.json());
  } catch(e) {
    setStatus('Diff error: ' + e.message, false);
    diffSelect.value = '';
  }
});
