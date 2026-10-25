// The orders as a file to download.
const { orderLines } = require('./report');

function exportLines(orders) {
  const report = orderLines(orders);
  return report.lines.map(line => [line.item, line.quantity, line.price, line.amount].join(',')).join('\n') + `\ntotal,${report.total}`;
}

module.exports = { exportLines };
