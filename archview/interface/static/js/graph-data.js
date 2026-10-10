function indexElements(elements) {
  const nodeIds = new Set(), edgeIds = new Set();
  const nodeMap = {}, edgeMap = {};
  for (const el of elements) {
    if (el.data.source) { edgeIds.add(el.data.id); edgeMap[el.data.id] = el; }
    else                { nodeIds.add(el.data.id); nodeMap[el.data.id] = el; }
  }
  return { nodeIds, edgeIds, nodeMap, edgeMap };
}

// Fade stale elements out briefly before deleting them. Elements re-added
// before the timer fires lose the .removing class and survive the cleanup.
function fadeOutAndRemove(eles) {
  if (eles.length === 0) return;
  if (firstLoad) { eles.remove(); return; }
  const goners = eles.union(eles.nodes().connectedEdges());
  goners.addClass('removing');
  setTimeout(() => goners.filter('.removing').remove(), 320);
}

// Fade newly-added (visible) elements in.
function fadeInByIds(ids) {
  let eles = cy.collection();
  ids.forEach(id => { eles = eles.union(cy.getElementById(id)); });
  const vis = eles.filter(el => el.visible());
  if (vis.length === 0) return;
  vis.style('opacity', 0);
  vis.animate({ style: { opacity: 1 } }, {
    duration: 350,
    easing: 'ease-out',
    complete: () => vis.removeStyle('opacity'),
  });
}

function reconcileGraph({ nodeIds, edgeIds, nodeMap, edgeMap }) {
  // Stale nodes and edges fade out, then get removed (proxies are transient —
  // updateProxyEdges rebuilds them on every applyCollapse, so skip them here)
  const staleNodes = cy.nodes().filter(n => !nodeIds.has(n.id()));
  staleNodes.forEach(n => {
    const id = n.id();
    delete userPositions[id];
    expandedFolders.delete(id);
    selectedNodes.delete(id);
    if (hoveredNode && hoveredNode.id() === id) {
      hoveredNode = null;
      hideTooltip();
    }
  });
  const staleEdges = cy.edges().filter(e => !e.data('is_proxy') && !edgeIds.has(e.id()));
  fadeOutAndRemove(staleNodes.union(staleEdges));

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
      existing.removeClass('new-node removing');
    } else {
      cy.add(el);
      addedNodes.push(el.data.id);
    }
  }

  // Upsert edges — update data so labels/kind/cycle stay current
  const addedEdges = [];
  for (const [id, el] of Object.entries(edgeMap)) {
    const existing = cy.getElementById(id);
    if (existing.length === 0) {
      cy.add(el);
      addedEdges.push(id);
    } else {
      existing.data(el.data);
      existing.removeClass('removing');
    }
  }

  return { addedNodes, addedEdges };
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
    const { addedNodes, addedEdges } = reconcileGraph(index);
    trackCompoundNodes(newElements);

    if (firstLoad) {
      const hasSaved = Object.keys(userPositions).length > 0;
      if (hasSaved) {
        // Restore the saved layout: saved positions (via the layout transform)
        // and the saved open/closed state. Legacy files (no expanded list) keep
        // the old behavior of opening every folder.
        if (savedExpanded !== null) {
          savedExpanded.forEach(id => { if (compoundNodes.has(id)) expandedFolders.add(id); });
        } else {
          compoundNodes.forEach(id => expandedFolders.add(id));
        }
        runLayout(false);   // pin saved positions, no grid/compact
        applyCollapse();    // apply open/closed state + collapsed-box positions
      } else {
        // Fresh open: lay out expanded so every child gets a position, grid each
        // folder square, then collapse to a compact default view.
        compoundNodes.forEach(id => expandedFolders.add(id));
        runLayout();
        expandedFolders.clear(); applyCollapse(); compactTopLevel(); applyCollapse();
      }
      cy.fit(undefined, 48);
      updateFolderLabels();
      updateFolderButtonLabel();
      firstLoad = false;
    } else {
      // Live refresh: only place brand-new nodes; never move existing ones.
      applyCollapse();
      if (addedNodes.length > 0) {
        placeNewNodesNearSiblings(addedNodes);
        highlightNewNodes(addedNodes);
      }
      if (addedNodes.length > 0 || addedEdges.length > 0) {
        fadeInByIds(addedNodes.concat(addedEdges));
      }
      applyFocus();
    }

    const n = cy.nodes().not('.removing').length;
    setStatus(`${n} module${n !== 1 ? 's' : ''} · ${new Date().toLocaleTimeString()}`);
  } catch(e) {
    console.error('refresh error:', e);
    setStatus('Fetch error: ' + e.message, false);
  }
}

