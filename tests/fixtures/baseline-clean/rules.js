// The order rules, shared by the checkout screen and the server.
const LIMITS = { quantity: { min: 1, max: 10 } };

function orderProblem(order) {
  if (!order || typeof order.item !== 'string' || !order.item) return 'an item is needed';
  const quantity = Number(order.quantity);
  if (!Number.isInteger(quantity) || quantity < LIMITS.quantity.min || quantity > LIMITS.quantity.max) {
    return `choose between ${LIMITS.quantity.min} and ${LIMITS.quantity.max}`;
  }
  return null;
}

module.exports = { LIMITS, orderProblem };
