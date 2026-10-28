// How the roster keeps its changes: the whole state on every save, and a queue for when the server is away.
export const queued = [];

export function saveLocally(state) {
  localStorage.setItem('appState', JSON.stringify(state));
}

export async function save(state) {
  await fetch('/api/state', { method: 'POST', body: JSON.stringify(state) });
  showToast('Saved');
}

export function remember(change) {
  const queue = JSON.parse(localStorage.getItem('pending') || '[]');
  queue.push(change);
  localStorage.setItem('pending', JSON.stringify(queue));
}

// Meant to stay: a preference, and one order saved and checked.
export function rememberTheme(theme) { localStorage.setItem('theme', theme); }

export async function saveOrder(order) {
  const answer = await fetch(`/api/orders/${order.id}`, { method: 'PUT', body: JSON.stringify(order) });
  if (answer.ok) showToast('Order saved');
}

function showToast(text) { document.title = text; }
