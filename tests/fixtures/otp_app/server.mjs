// A tiny app behind a sign-in by a one-time code (EAOS's sign-in proof, tests/test_sign_in.py): the person gives an
// e-mail address, the app prints the code it made and, when it has a mail server (SMTP_HOST, SMTP_PORT), e-mails it;
// the code signs them in with a cookie signed by AUTH_SECRET, so a session outlives a restart. Every page but the
// sign-in sends a visitor to /login.
import { createHmac, randomInt } from 'node:crypto';
import { createServer } from 'node:http';
import net from 'node:net';

const secret = process.env.AUTH_SECRET || 'development';
const codes = new Map();
const sign = (value) => createHmac('sha256', secret).update(value).digest('hex');
const page = (title, body) => `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">` +
  `<title>${title}</title></head><body><main><h1>${title}</h1>${body}</main></body></html>`;
const nav = '<nav><a href="/dashboard">Dashboard</a> <a href="/reports">Reports</a> <a href="/settings">Settings</a> <a href="/logout">Sign out</a></nav>';

function who(request) {
  const cookie = /(?:^|;\s*)session=([^;]+)/.exec(request.headers.cookie || '')?.[1];
  const [email, until, mac] = decodeURIComponent(cookie || '').split('|');
  return mac && mac === sign(`${email}|${until}`) && Number(until) > Date.now() ? email : null;
}

function mail(to, code) {     // the code by e-mail, to the run's mail catcher when there is one
  if (!process.env.SMTP_HOST || !Number(process.env.SMTP_PORT)) return;
  const lines = ['HELO otp-app', 'MAIL FROM:<otp@otp-app.test>', `RCPT TO:<${to}>`, 'DATA',
    `From: otp@otp-app.test\r\nTo: ${to}\r\nSubject: Your sign-in code\r\n\r\nYour sign-in code is ${code}\r\n.`, 'QUIT'];
  const socket = net.connect(Number(process.env.SMTP_PORT), process.env.SMTP_HOST);
  socket.on('data', () => (lines.length ? socket.write(lines.shift() + '\r\n') : socket.end()));
  socket.on('error', () => {});
}

async function form(request) {
  let text = '';
  for await (const part of request) text += part;
  return Object.fromEntries(new URLSearchParams(text));
}

const send = (response, status, html, headers = {}) => { response.writeHead(status, { 'content-type': 'text/html', ...headers }); response.end(html); };
const go = (response, to, headers = {}) => { response.writeHead(303, { location: to, ...headers }); response.end(); };
const reports = { 1: 'Sales of the month', 2: 'Visitors by country' };

// The app's routes, one handler each; a visitor is sent to /login from every page but the sign-in.
const app = { routes: new Map(), get(path, handler) { this.routes.set(`GET ${path}`, handler); }, post(path, handler) { this.routes.set(`POST ${path}`, handler); } };

app.get('/login', (request, response) => send(response, 200, page('Sign in', '<form method="post"><label>E-mail <input name="email" type="email" required></label> <button>Send me a code</button></form>')));
app.post('/login', async (request, response) => {
  const to = (await form(request)).email || '';
  const code = String(randomInt(100000, 1000000));
  codes.set(to, code);
  console.log(`[otp-app] sign-in code for ${to}: ${code}`);
  mail(to, code);
  go(response, `/verify?email=${encodeURIComponent(to)}`);
});
app.get('/verify', (request, response, url) => send(response, 200, page('Enter your code', `<p>A code was sent to ${url.searchParams.get('email')}.</p><form method="post"><input type="hidden" name="email" value="${url.searchParams.get('email')}"><label>Code <input name="code" inputmode="numeric" autocomplete="one-time-code" required></label> <button>Sign in</button></form>`)));
app.post('/verify', async (request, response) => {
  const { email: to, code } = await form(request);
  if (!code || codes.get(to) !== code.trim()) return send(response, 401, page('Sign in', '<p>That code is not right.</p><a href="/login">Try again</a>'));
  codes.delete(to);
  const until = Date.now() + 86400000;
  go(response, '/dashboard', { 'set-cookie': `session=${encodeURIComponent(`${to}|${until}|${sign(`${to}|${until}`)}`)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400` });
});
app.get('/logout', (request, response) => go(response, '/login', { 'set-cookie': 'session=; Path=/; Max-Age=0' }));
app.get('/', (request, response, url, email) => send(response, 200, page('Dashboard', `${nav}<p>Signed in as ${email}.</p>`)));
app.get('/dashboard', (request, response, url, email) => send(response, 200, page('Dashboard', `${nav}<p>Signed in as ${email}.</p>`)));
app.get('/reports', (request, response) => send(response, 200, page('Reports', `${nav}<ul>${Object.entries(reports).map(([id, name]) => `<li><a href="/reports/${id}">${name}</a></li>`).join('')}</ul>`)));
app.get('/settings', (request, response, url, email) => send(response, 200, page('Settings', `${nav}<p>The account of ${email}.</p>`)));

const OPEN = new Set(['GET /login', 'POST /login', 'GET /verify', 'POST /verify']);
createServer(async (request, response) => {
  const url = new URL(request.url, 'http://app');
  const email = who(request);
  const key = `${request.method} ${url.pathname}`;
  if (!OPEN.has(key) && !email) return go(response, '/login');
  const report = /^\/reports\/(\d+)$/.exec(url.pathname);
  if (report && reports[report[1]]) return send(response, 200, page(reports[report[1]], `${nav}<p>Only ${email} sees this report.</p>`));
  const handler = app.routes.get(key);
  return handler ? handler(request, response, url, email) : send(response, 404, page('Not found', nav));
}).listen(Number(process.env.PORT) || 3000, '127.0.0.1');
