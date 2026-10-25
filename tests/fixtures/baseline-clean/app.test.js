const test = require('node:test');
const assert = require('node:assert');
const { orderLines } = require('./report');
const { server, sessions } = require('./server');

test('the report adds every order', () => {
  assert.equal(orderLines([{ item: 'a', price: 2, quantity: 2 }, { item: 'b', price: 1 }]).total, '5.00');
});

async function call(port, method, path, sid, body) {
  const headers = sid ? { cookie: `sid=${sid}` } : {};
  const res = await fetch(`http://127.0.0.1:${port}${path}`, { method, headers, body: body && JSON.stringify(body) });
  return res.status;
}

test('a wrong password is refused at /api/login', async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  try {
    assert.equal(await call(port, 'POST', '/api/login', null, { user: 'ali', password: 'no' }), 401);
  } finally {
    server.close();
  }
});

test('only the owner places and removes an order', async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  sessions.set('s-ali', 'ali');
  sessions.set('s-sara', 'sara');
  try {
    assert.equal(await call(port, 'POST', '/api/orders', null, { item: 'cup', quantity: 1 }), 401);
    assert.equal(await call(port, 'POST', '/api/orders', 's-ali', { item: 'cup', quantity: 11 }), 400);
    assert.equal(await call(port, 'POST', '/api/orders', 's-ali', { item: 'cup', quantity: 2 }), 201);
    assert.equal(await call(port, 'GET', '/api/orders/2', 's-ali'), 404);
    assert.equal(await call(port, 'DELETE', '/api/orders/2', 's-ali'), 404);
    assert.equal(await call(port, 'DELETE', '/api/orders/2', 's-sara'), 204);
  } finally {
    server.close();
  }
});
