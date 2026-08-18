// Runs the real renderDiagram() out of a rendered roadmap.html against a stub DOM, then
// checks the produced SVG markup: does every legend element fall inside the viewBox?
// Usage: node tests/test_diagram.js <rendered roadmap.html> ...
// Normally invoked by tests/test_clis.py, which builds the workspaces to point it at.
const fs = require('fs');

// Widest legend label is "Planned" at font-size 10, ~0.55em per char for a UI sans face.
const LEGEND_LABEL_PX = 7 * 10 * 0.55;

function renderSvg(file) {
  const html = fs.readFileSync(file, 'utf8');
  const data = JSON.parse(
    html.match(/<script id="roadmap-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const src = html.match(/function renderDiagram\(\) \{[\s\S]*?\n  \}\n/)[0];

  let out = '';
  const stubEl = {
    set innerHTML(v) { out = v; },
    get innerHTML() { return out; },
    querySelectorAll: () => [],   // the label-trimming pass needs a real text renderer; skipped
  };
  const sandbox = {
    MS: data.milestones,
    document: { getElementById: () => stubEl },
    esc: (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  };
  new Function('MS', 'document', 'esc', src + '; renderDiagram();')(
    sandbox.MS, sandbox.document, sandbox.esc);
  return { svg: out, n: data.milestones.length };
}

let failed = 0;
for (const file of process.argv.slice(2)) {
  const { svg, n } = renderSvg(file);
  const viewBox = svg.match(/viewBox="0 0 (\d+(?:\.\d+)?) /);
  if (!viewBox) { console.log(`  FAIL  ${file}: no svg rendered`); failed++; continue; }
  const width = parseFloat(viewBox[1]);

  // every legend circle/text must fit inside the viewBox
  let maxX = 0;
  for (const m of svg.matchAll(/<circle cx="(\d+(?:\.\d+)?)" cy="219"[^>]*r="(\d+)"/g)) {
    maxX = Math.max(maxX, parseFloat(m[1]) + parseFloat(m[2]));
  }
  for (const m of svg.matchAll(/<text x="(\d+(?:\.\d+)?)" y="222"[^>]*>([^<]*)<\/text>/g)) {
    maxX = Math.max(maxX, parseFloat(m[1]) + LEGEND_LABEL_PX);
  }
  const legendItems = (svg.match(/cy="219"/g) || []).length;
  const ok = legendItems === 3 && maxX <= width;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${n} milestone(s): viewBox width ${width}, ` +
              `legend needs ${maxX.toFixed(0)}, ${legendItems}/3 legend markers`);
  if (!ok) failed++;
}
process.exit(failed ? 1 : 0);
