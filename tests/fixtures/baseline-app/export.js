// The orders as a file to download.
function exportLines(orders) {
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
  return lines.map(line => [line.item, line.quantity, line.price, line.amount].join(',')).join('\n') + `\ntotal,${total.toFixed(2)}`;
}

module.exports = { exportLines };
