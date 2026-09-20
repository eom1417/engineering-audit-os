import { priceFor } from '../lib/pricing';

const PREMIUM_DISCOUNT = 0.1;

export async function listOrders(req, res) {
  res.json({ orders: [] });
}

export async function createOrder(req, res) {
  const base = priceFor(req.body.items);
  // Duplicated rule: the premium discount also lives in core/pricing.py
  const total = req.body.tier === 'premium' ? base * (1 - PREMIUM_DISCOUNT) : base;
  res.json({ total });
}
