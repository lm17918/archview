// [background, text] color per node role. Colors live here, in the interface —
// the backend only classifies each node's type.
const NODE_COLORS = {
  entry:        ['#6ee7b7', '#0a2a1a'],
  intermediate: ['#93c5fd', '#0a1a2e'],
  leaf:         ['#fca5a5', '#2e0a0a'],
  isolated:     ['#3a3a46', '#e2e2e8'],
  error:        ['#dc2626', '#ffffff'],
};
const typeColorStyles = Object.entries(NODE_COLORS).map(([type, [bg, fg]]) => ({
  selector: `node[type="${type}"]`,
  style: { 'background-color': bg, 'color': fg },
}));

const cyStyle = [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '12px',
        'font-family': "'SF Mono', 'Fira Code', 'Consolas', monospace",
        'font-weight': '700',
        'text-wrap': 'wrap',
        'text-max-width': '160px',
        'width': 'label',
        'height': 'label',
        'padding': '14px',
        'shape': 'roundrectangle',
        'border-width': 1,
        'border-color': 'rgba(255,255,255,0.12)',
      }
    },
    ...typeColorStyles,
    {
      selector: 'edge',
      style: {
        'width': 1.5,
        'line-color': '#5a5a72',
        'target-arrow-color': '#6e6e88',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'arrow-scale': 0.85,
        'label': '',
      }
    },
    {
      selector: 'edge[?is_proxy]',
      style: {
        'width': 1.5,
        'line-color': '#5a5a72',
        'target-arrow-color': '#6e6e88',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'line-style': 'dashed',
        'line-dash-pattern': [6, 4],
        'arrow-scale': 0.85,
      }
    },
    {
      selector: 'node:selected',
      style: {
        'border-color': '#7c6af7',
        'border-width': 2.5,
      }
    },
    {
      selector: '.faded',
      style: { 'opacity': 0.12 }
    },
    {
      selector: '.highlighted',
      style: { 'opacity': 1 }
    },
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#7c6af7',
        'target-arrow-color': '#7c6af7',
        'width': 2.5,
      }
    },
    {
      selector: '.new-node',
      style: {
        'border-color': '#4ade80',
        'border-width': 2.5,
        'border-style': 'dashed',
      }
    },
    {
      selector: ':parent',
      style: {
        'label': ele => '▼ ' + ele.data('label').replace(/^[▶▼] /, ''),
        'text-valign': 'top',
        'text-halign': 'center',
        'font-size': '13px',
        'font-weight': '700',
        'color': '#c8c8e0',
        'background-color': '#1e1e2a',
        'background-opacity': 1,
        'border-width': 1.5,
        'border-color': '#3a3a55',
        'border-style': 'solid',
        'padding': '40px',
        'padding-top': '10px',
        'shape': 'roundrectangle',
        'text-margin-y': 8,
      }
    },
    {
      selector: 'node[?is_folder]',
      style: {
        'background-color': '#1e1e2a',
        'border-color': '#4a4a6a',
        'border-width': 1.5,
        'color': '#c8c8e0',
        'font-size': '13px',
        'font-weight': '700',
      }
    },
    {
      selector: '.collapsed',
      style: {
        'label': ele => '▶ ' + ele.data('label').replace(/^[▶▼] /, ''),
        'width': '140px',
        'height': '40px',
        'min-width': '140px',
        'min-height': '40px',
        'text-valign': 'center',
        'text-halign': 'center',
        'background-color': '#1e1e2a',
        'border-width': 1.5,
        'border-color': '#4a4a6a',
        'border-style': 'solid',
        'shape': 'roundrectangle',
        'font-size': '13px',
        'font-weight': '700',
        'color': '#c8c8e0',
        'padding': '10px',
      }
    },
    {
      selector: '.diff-added',
      style: {
        'border-color': '#4ade80',
        'border-width': 2.5,
        'border-style': 'solid',
      }
    },
    {
      selector: '.diff-removed',
      style: {
        'opacity': 0.3,
        'background-color': '#3a3a46',
        'border-color': '#f87171',
        'border-width': 2,
        'border-style': 'dashed',
      }
    },
    {
      selector: '.diff-modified',
      style: {
        'border-color': '#facc15',
        'border-width': 2.5,
        'border-style': 'solid',
      }
    },
    {
      selector: 'edge.diff-added',
      style: {
        'line-color': '#4ade80',
        'target-arrow-color': '#4ade80',
        'width': 2.5,
      }
    },
    {
      selector: 'edge.diff-removed',
      style: {
        'line-color': '#f87171',
        'target-arrow-color': '#f87171',
        'width': 1.5,
        'line-style': 'dashed',
        'opacity': 0.3,
      }
    },
    {
      selector: 'edge.diff-modified',
      style: {
        'line-color': '#facc15',
        'target-arrow-color': '#facc15',
        'width': 2.5,
      }
    },
];
