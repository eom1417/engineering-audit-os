// The checkout screen: the order a person places.
import React, { useState } from 'react';
import { z } from 'zod';

const order = z.object({
  item: z.string().min(1),
  quantity: z.number().int().min(1).max(10),
});

export default function Checkout() {
  const [error, setError] = useState('');
  async function place(item, quantity) {
    const checked = order.safeParse({ item, quantity });
    if (!checked.success) return setError('Choose between 1 and 10');
    await fetch('/api/orders', { method: 'POST', body: JSON.stringify(checked.data) });
  }
  return <button onClick={() => place('book', 1)}>Order {error}</button>;
}
