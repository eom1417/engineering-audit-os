// Card payments on the checkout screen.
import Stripe from 'stripe';

export const stripe = new Stripe(import.meta.env.VITE_STRIPE_SECRET_KEY);

export function charge(amount) {
  return stripe.paymentIntents.create({ amount, currency: 'usd' });
}
