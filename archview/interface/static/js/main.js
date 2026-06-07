// Initialization — runs after all other scripts (load order).
loadSavedPositions().then(refresh);
setInterval(refresh, REFRESH_MS);

// Diff UI intentionally disabled — #diff-controls stays hidden until design is finalized
loadAnnotations();
setTimeout(syncViewport, 200);
