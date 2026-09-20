export const PREMIUM_DISCOUNT = 0.1;

export function baseTotal(items) {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

export function priceFor(items, tier = 'standard') {
  const total = baseTotal(items);
  return tier === 'premium' ? total * (1 - PREMIUM_DISCOUNT) : total;
}
