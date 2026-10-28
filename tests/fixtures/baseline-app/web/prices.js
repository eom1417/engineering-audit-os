// The price list, read from its file.
const fs = require('node:fs');

function prices() {
  return JSON.parse(fs.readFileSync(__dirname + '/prices.json', 'utf8'));
}

module.exports = { prices };
