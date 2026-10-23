// The first version of the price rules.
function legacyPrice(order) {
  if (!order) return 0;
  const base = Number(order.price) || 0;
  return order.member ? base * 0.8 : base;
}

module.exports = { legacyPrice };
