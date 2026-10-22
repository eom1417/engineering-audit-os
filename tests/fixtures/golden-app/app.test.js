const test = require('node:test');
const assert = require('node:assert');
test('the page names its three screens', () => {
  const page = require('node:fs').readFileSync(__dirname + '/index.html', 'utf8');
  for (const hash of ['#/now', '#/tasks', '#/about']) assert.ok(page.includes(hash));
});
