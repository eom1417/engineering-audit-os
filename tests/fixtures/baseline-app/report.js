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

module.exports = { orderLines };
