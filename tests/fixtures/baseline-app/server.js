// A small orders app: sign in, see your orders and the reports, check that the store answers.
const http = require('node:http');
const fs = require('node:fs');
const { exec } = require('node:child_process');
const config = require('./config');
const { orderLines } = require('./report');
const { exportLines } = require('./export');

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

function memberPrice(order) {
  return Number(order.price) * 0.9;
}

async function login(req, res) {
  const { user, password } = await body(req);
  if (!users[user] || users[user] !== password) return send(res, 401, { error: 'wrong name or password' });
  const sid = Math.random().toString(36).slice(2);
  sessions.set(sid, user);
  res.setHeader('Set-Cookie', `sid=${sid}; HttpOnly; Path=/`);
  return send(res, 200, { user });
}

function order(req, res, id) {
  const user = signedIn(req);
  if (!user) return send(res, 401, { error: 'sign in first' });
  const found = orders[id];
  if (!found) return send(res, 404, { error: 'no such order' });
  return send(res, 200, found);
}

function storeCheck(req, res, host) {
  exec('ping -c 1 ' + host, (error, out) => send(res, error ? 502 : 200, { host, out, store: config.STORE_URL }));
}

async function createOrder(req, res) {
  const { item, quantity } = await body(req);
  const id = Object.keys(orders).length + 1;
  orders[id] = { id, owner: req.headers['x-user'], item, price: 10, quantity };
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

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const user = signedIn(req);
  if (url.pathname === '/health') return res.end('ok');
  if (url.pathname === '/api/login' && req.method === 'POST') return login(req, res);
  if (url.pathname === '/api/me') return user ? send(res, 200, { user }) : send(res, 401, { error: 'sign in first' });
  if (url.pathname === '/api/orders' && req.method === 'POST') return createOrder(req, res);
  if (url.pathname === '/api/orders') return send(res, 200, Object.values(orders).filter(o => o.owner === user));
  if (url.pathname.startsWith('/api/orders/') && req.method === 'DELETE') return removeOrder(req, res, url.pathname.split('/').pop());
  if (url.pathname.startsWith('/api/orders/')) return order(req, res, url.pathname.split('/').pop());
  if (url.pathname === '/api/report') return send(res, 200, orderLines(Object.values(orders)));
  if (url.pathname === '/api/export') return res.end(exportLines(Object.values(orders)));
  if (url.pathname === '/api/store-check') return storeCheck(req, res, url.searchParams.get('host') || 'localhost');
  if (url.pathname === '/api/contact') return send(res, 200, DEFAULT_ADMIN);
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  return res.end(page);
}).listen(config.PORT, '0.0.0.0');

// The administrator the contact route shows, typed in while the server was built.
const DEFAULT_ADMIN = { name: 'Mohammed Al-Shehri', email: 'm.alshehri@alnoor-clinic.sa', mobile: '0504443322' };
