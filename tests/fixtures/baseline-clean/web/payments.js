// Card payments on the checkout screen: the browser holds only the publishable key; the server charges.
import { loadStripe } from '@stripe/stripe-js';

export const stripe = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY);

export function charge(orderId) {
  return fetch(`/api/orders/${orderId}/payment`, { method: 'POST' });
}
