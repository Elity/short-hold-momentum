const assert = require('node:assert/strict');

// Measure rendered controls, not CSS implementation details. Labels are excluded
// so a button cannot pass by aligning to the label + select as one tall box.
async function assertToolbarLayout(page, selector, description) {
  const boxes = await page.locator(selector).locator('select, button').evaluateAll(nodes =>
    nodes.map(node => {
      const r = node.getBoundingClientRect();
      return {label:node.getAttribute('name') || node.textContent.trim(),
        left:r.left, top:r.top, right:r.right, bottom:r.bottom, height:r.height};
    }).filter(r => r.height > 0)
  );
  assert.ok(boxes.length >= 3, description + ': missing toolbar controls');
  const rows = [];
  for (const box of boxes) {
    const row = rows.find(items => items.some(other =>
      Math.min(other.bottom,box.bottom) - Math.max(other.top,box.top) > 1));
    if (row) row.push(box); else rows.push([box]);
  }
  for (const row of rows) {
    assert.ok(Math.max(...row.map(r=>r.top))-Math.min(...row.map(r=>r.top)) <= 1,
      description + ': control top edges are misaligned: ' + JSON.stringify(row));
    assert.ok(Math.max(...row.map(r=>r.bottom))-Math.min(...row.map(r=>r.bottom)) <= 1,
      description + ': control bottom edges are misaligned: ' + JSON.stringify(row));
  }
  assert.ok(Math.max(...boxes.map(r=>r.height))-Math.min(...boxes.map(r=>r.height)) <= 1,
    description + ': inconsistent control heights');
  for (let i=0; i<boxes.length; i++) {
    for (let j=i+1; j<boxes.length; j++) {
      const a=boxes[i],b=boxes[j];
      assert.ok(Math.min(a.right,b.right)-Math.max(a.left,b.left)<=1 ||
        Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<=1,
        description + ': controls overlap');
    }
  }
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),
    description + ': page overflows horizontally');
  return {description, rows:rows.length, controls:boxes};
}

module.exports = {assertToolbarLayout};
