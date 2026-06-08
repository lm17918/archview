// Initialization — runs after all other scripts (load order).
loadSavedPositions().then(refresh);

// Live updates pushed over SSE; refresh the instant the server reports a change.
const events = new EventSource('/events');
events.onmessage = refresh;  // EventSource auto-reconnects on drop
// Safety-net poll in case SSE is unavailable or the connection silently dies.
setInterval(refresh, REFRESH_MS);

// Diff UI intentionally disabled — #diff-controls stays hidden until design is finalized
loadAnnotations();
setTimeout(syncViewport, 200);
