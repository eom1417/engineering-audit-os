// The orders report shown on the reports screen.
function orderLines(orders) {
  const lines = [];
  let total = 0;
  for (const order of orders) {
    const price = Number(order.price) || 0;
    const quantity = Number(order.quantity) || 1;
    const amount = price * quantity;
    total += amount;
    lines.push({
      item: order.item,
      quantity,
      price: price.toFixed(2),
      amount: amount.toFixed(2),
      owner: order.owner,
    });
  }
  lines.sort((a, b) => Number(b.amount) - Number(a.amount));
  return { lines, total: total.toFixed(2), count: lines.length };
}

module.exports = { orderLines, reportTotals };

// The report's total, worked out twice: the first way kept when the second came; and a switch that is on, meant to stay.
const SHOW_COUNT = true;
function reportTotals(orders) {
  const totals = { total: totalV2(orders), checked: totalV1(orders) };
  if (SHOW_COUNT) totals.count = orders.length;
  return totals;
}
function totalV1(orders) { return orders.reduce((sum, order) => sum + Number(order.price) * (Number(order.quantity) || 1), 0); }
function totalV2(orders) { let sum = 0; for (const order of orders) sum += (Number(order.price) || 0) * (Number(order.quantity) || 1); return sum; }
