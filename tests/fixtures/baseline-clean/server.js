// A small orders app: sign in, see your orders and the reports, check that the store answers.
const http = require('node:http');
const fs = require('node:fs');
const { execFile } = require('node:child_process');
const config = require('./config');
const { orderLines } = require('./report');
const { exportLines } = require('./export');
const { orderProblem } = require('./rules');
const { logger } = require('./log');

const users = { ali: 'ali-pass', sara: 'sara-pass' };
const orders = {
  1: { id: 1, owner: 'ali', item: 'book', price: 40, quantity: 1 },
  2: { id: 2, owner: 'sara', item: 'pen', price: 5, quantity: 3 },
  3: { id: 3, owner: 'sara', item: 'bag', price: 120, quantity: 1 },
};
const sessions = new Map();
const page = fs.readFileSync(__dirname + '/index.html');

function signedIn(req) {
  const sid = /(?:^|;\s*)sid=([^;]+)/.exec(req.headers.cookie || '');
  return sid ? sessions.get(sid[1]) : undefined;
}

function body(req) {
  return new Promise(resolve => {
    let text = '';
    req.on('data', chunk => { text += chunk; });
    req.on('end', () => { try { resolve(JSON.parse(text || '{}')); } catch { resolve({}); } });
  });
}

function send(res, status, value) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(value));
}

function mine(user) {
  return Object.values(orders).filter(o => o.owner === user);
}

async function login(req, res) {
  const { user, password } = await body(req);
  if (!users[user] || users[user] !== password) {
    logger.info('sign-in refused');
    return send(res, 401, { error: 'wrong name or password' });
  }
  const sid = require('node:crypto').randomBytes(16).toString('hex');
  sessions.set(sid, user);
  res.setHeader('Set-Cookie', `sid=${sid}; HttpOnly; Path=/`);
  return send(res, 200, { user });
}

function order(req, res, id) {
  const user = signedIn(req);
  if (!user) return send(res, 401, { error: 'sign in first' });
  const found = orders[id];
  if (!found || found.owner !== user) return send(res, 404, { error: 'no such order' });
  return send(res, 200, found);
}

function storeCheck(req, res) {
  execFile('ping', ['-c', '1', new URL(config.STORE_URL).hostname], error => send(res, error ? 502 : 200, { ok: !error }));
}

async function createOrder(req, res) {
  const user = signedIn(req);
  if (!user) return send(res, 401, { error: 'sign in first' });
  const wanted = await body(req);
  const problem = orderProblem(wanted);
  if (problem) return send(res, 400, { error: problem });
  const id = Object.keys(orders).length + 1;
  orders[id] = { id, owner: user, item: wanted.item, price: 10, quantity: Number(wanted.quantity) };
  return send(res, 201, orders[id]);
}

function removeOrder(req, res, id) {
  const user = signedIn(req);
  if (!user) return send(res, 401, { error: 'sign in first' });
  const found = orders[id];
  if (!found || found.owner !== user) return send(res, 404, { error: 'no such order' });
  delete orders[id];
  return send(res, 204, {});
}

function guarded(req, res, answer) {
  const user = signedIn(req);
  return user ? answer(user) : send(res, 401, { error: 'sign in first' });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/health') return res.end('ok');
  if (url.pathname === '/api/login' && req.method === 'POST') return login(req, res);
  if (url.pathname === '/api/me') return guarded(req, res, user => send(res, 200, { user }));
  if (url.pathname === '/api/orders' && req.method === 'POST') return createOrder(req, res);
  if (url.pathname === '/api/orders') return guarded(req, res, user => send(res, 200, mine(user)));
  if (url.pathname.startsWith('/api/orders/') && req.method === 'DELETE') return removeOrder(req, res, url.pathname.split('/').pop());
  if (url.pathname.startsWith('/api/orders/')) return order(req, res, url.pathname.split('/').pop());
  if (url.pathname === '/api/report') return guarded(req, res, user => send(res, 200, orderLines(mine(user))));
  if (url.pathname === '/api/export') return guarded(req, res, user => res.end(exportLines(mine(user))));
  if (url.pathname === '/api/store-check') return guarded(req, res, () => storeCheck(req, res));
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  return res.end(page);
});

if (require.main === module) server.listen(config.PORT, '0.0.0.0');
module.exports = { server, sessions };
