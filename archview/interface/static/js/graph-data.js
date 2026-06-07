function indexElements(elements) {
  const nodeIds = new Set(), edgeIds = new Set();
  const nodeMap = {}, edgeMap = {};
  for (const el of elements) {
    if (el.data.source) { edgeIds.add(el.data.id); edgeMap[el.data.id] = el; }
    else                { nodeIds.add(el.data.id); nodeMap[el.data.id] = el; }
  }
  return { nodeIds, edgeIds, nodeMap, edgeMap };
}

function reconcileGraph({ nodeIds, edgeIds, nodeMap, edgeMap }) {
  // Remove stale nodes and edges
  cy.nodes().forEach(n => {
    const id = n.id();
    if (!nodeIds.has(id)) {
      delete userPositions[id];
      expandedFolders.delete(id);
      selectedNodes.delete(id);
      if (hoveredNode && hoveredNode.id() === id) {
        hoveredNode = null;
        hideTooltip();
      }
      n.remove();
    }
  });
  cy.edges().forEach(e => { if (!edgeIds.has(e.id())) e.remove(); });

  // Upsert nodes — parents first so children can reference them
  const sorted = Object.values(nodeMap).sort((a, b) =>
    (a.data.parent ? 1 : 0) - (b.data.parent ? 1 : 0)
  );
  const addedNodes = [];
  for (const el of sorted) {
    const existing = cy.getElementById(el.data.id);
    if (existing.length > 0) {
      // Don't overwrite parent — managed by collapse logic via move()
      const { parent, ...rest } = el.data;
      existing.data(rest);
      existing.removeClass('new-node');
    } else {
      cy.add(el);
      addedNodes.push(el.data.id);
    }
  }

  // Upsert edges
  for (const [id, el] of Object.entries(edgeMap)) {
    if (cy.getElementById(id).length === 0) cy.add(el);
  }

  return addedNodes;
}

function trackCompoundNodes(elements) {
  compoundNodes.clear();
  for (const el of elements) {
    if (el.data.source) continue; // edges
    if (el.data.parent) compoundNodes.add(el.data.parent);
    if (el.data.is_folder) compoundNodes.add(el.data.id);
  }
}

function highlightNewNodes(addedNodes) {
  addedNodes.forEach(id => cy.getElementById(id).addClass('new-node'));
  setTimeout(() => addedNodes.forEach(id => cy.getElementById(id).removeClass('new-node')), 5000);
}

async function refresh() {
  try {
    const resp = await fetch('/graph.json?t=' + Date.now());
    if (resp.status === 404) {
      // graph.json not generated yet — keep waiting
      setStatus('Waiting for analysis…', false);
      return;
    }
    if (!resp.ok) { setStatus('Error ' + resp.status, false); return; }
    const newElements = await resp.json();

    if (newElements.length === 0) {
      // No modules found — clear graph, don't crash
      cy.elements().remove();
      setStatus('No modules found · ' + new Date().toLocaleTimeString());
      firstLoad = false;
      return;
    }

    const index = indexElements(newElements);
    const addedNodes = reconcileGraph(index);
    trackCompoundNodes(newElements);

    if (!firstLoad && addedNodes.length > 0) highlightNewNodes(addedNodes);

    if (firstLoad) {
      // The only automatic layout. Expand every folder so dagre gives each child
      // a real position, then default to collapsed (unless a saved layout exists).
      const hasSaved = Object.keys(userPositions).length > 0;
      compoundNodes.forEach(id => expandedFolders.add(id));
      runLayout();
      if (!hasSaved) { expandedFolders.clear(); applyCollapse(); compactTopLevel(); applyCollapse(); }
      cy.fit(undefined, 48);
      updateFolderLabels();
      updateFolderButtonLabel();
      firstLoad = false;
    } else {
      // Live refresh: only place brand-new nodes; never move existing ones.
      applyCollapse();
      if (addedNodes.length > 0) placeNewNodesNearSiblings(addedNodes);
      applyFocus();
    }

    const n = cy.nodes().length;
    setStatus(`${n} module${n !== 1 ? 's' : ''} · ${new Date().toLocaleTimeString()}`);
  } catch(e) {
    console.error('refresh error:', e);
    setStatus('Fetch error: ' + e.message, false);
  }
}

