// The checkout screen: the order a person places, checked by the same rules the server applies.
import React, { useState } from 'react';
import { orderProblem } from '../rules';

export default function Checkout() {
  const [error, setError] = useState('');
  async function place(item, quantity) {
    const problem = orderProblem({ item, quantity });
    if (problem) return setError(problem);
    await fetch('/api/orders', { method: 'POST', body: JSON.stringify({ item, quantity }) });
  }
  return <button onClick={() => place('book', 1)}>Order {error}</button>;
}
