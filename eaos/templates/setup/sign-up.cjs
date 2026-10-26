// EAOS's test account by rules (eaos/live/access/test_account.py): the app's own sign-in page filled as a person fills it, and,
// when the account is not there yet, its own sign-up page first. Run as the run's seed against the app in its isolated
// copy: BASE_URL, EAOS_STORAGE_STATE (where the session is saved), EAOS_TEST_USER and EAOS_TEST_PASSWORD (the run's own
// account), EAOS_SIGN_IN_PAGE (where the app sent a visitor). Prints one JSON line: the account as the lock's E2E_USER
// and E2E_PASSWORD, or {"signed_in": false, "tried": [...]} and exit 1.
const { chromium } = require(process.env.EAOS_PLAYWRIGHT);

const base = process.env.BASE_URL, user = process.env.EAOS_TEST_USER || 'demo', password = process.env.EAOS_TEST_PASSWORD;
const email = `${user}@example.com`;
const SIGN_IN = ['/login', '/signin', '/sign-in', '/auth/login', '/accounts/login/', '/users/sign_in', '/session/new', '/account/login'];
const SIGN_UP = ['/register', '/signup', '/sign-up', '/auth/register', '/auth/signup', '/accounts/signup/', '/users/sign_up', '/join'];
const JOIN = /sign ?up|register|create (an |your )?account|join|إنشاء حساب|تسجيل جديد|سجّل/i;
const SUBMIT = /sign ?in|log ?in|sign ?up|register|create|join|submit|continue|دخول|تسجيل|إنشاء|متابعة/i;
const tried = [];

// Each visible field filled by what it asks for; false when the page has no password field (no form of this kind).
async function fill(page, signingUp) {
  const passwords = page.locator('input[type=password]:visible');
  if (!(await passwords.count())) return false;
  for (const input of await page.locator('input:visible, textarea:visible').all()) {
    const type = ((await input.getAttribute('type')) || 'text').toLowerCase();
    const about = ['name', 'id', 'placeholder', 'autocomplete', 'aria-label'].map((a) => input.getAttribute(a));
    const words = (await Promise.all(about)).join(' ').toLowerCase();
    if (type === 'password') await input.fill(password);
    else if (type === 'email' || /e-?mail/.test(words)) await input.fill(email);
    else if (type === 'checkbox') { if (signingUp && /terms|agree|accept|policy/.test(words)) await input.check().catch(() => {}); }
    else if (['hidden', 'submit', 'button', 'radio', 'file', 'search'].includes(type)) continue;
    else if (/user|login|handle|nick|account|ident/.test(words)) await input.fill(user);
    else if (/name/.test(words)) await input.fill('Demo');
    else if (signingUp && !(await input.inputValue())) await input.fill('Demo');
  }
  const form = page.locator('form', { has: passwords.first() });
  const button = form.locator('button[type=submit], input[type=submit], button:not([type])').first();
  const pressed = (await button.count()) ? button : page.getByRole('button', { name: SUBMIT }).first();
  await Promise.all([page.waitForLoadState('load').catch(() => {}), pressed.click({ timeout: 5000 }).catch(() => passwords.first().press('Enter'))]);
  try { await page.waitForLoadState('networkidle', { timeout: 5000 }); } catch {}
  return true;
}

// Whether the page a sign-in led to is the app signed in: no password field left, and not a sign-in address.
async function inside(page) {
  await page.waitForTimeout(500);
  return !(await page.locator('input[type=password]:visible').count()) && !/\/(login|signin|sign-in|session)\b/i.test(new URL(page.url()).pathname);
}

async function attempt(page, paths, signingUp) {
  for (const path of paths) {
    const response = await page.goto(new URL(path, base).href, { waitUntil: 'load' }).catch(() => null);
    if (!response || response.status() >= 400) continue;
    if (await fill(page, signingUp)) { tried.push({ did: signingUp ? 'signed_up' : 'signed_in', at: path }); return true; }
  }
  return false;
}

(async () => {
  const browser = await chromium.launch({ args: ['--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost;[::1]'] });
  const context = await browser.newContext();
  const page = await context.newPage();
  const sent = process.env.EAOS_SIGN_IN_PAGE ? [new URL(process.env.EAOS_SIGN_IN_PAGE).pathname + new URL(process.env.EAOS_SIGN_IN_PAGE).search] : [];
  const signIn = [...sent, ...SIGN_IN];
  let ok = (await attempt(page, signIn, false)) && (await inside(page));
  if (!ok) {
    // the sign-up page: one the sign-in page links to, else a usual address
    await page.goto(new URL(signIn[0], base).href).catch(() => {});
    const link = page.getByRole('link', { name: JOIN }).first();
    const linked = (await link.count()) ? [new URL(await link.getAttribute('href'), page.url()).pathname] : [];
    if (await attempt(page, [...linked, ...SIGN_UP], true)) ok = (await inside(page)) || ((await attempt(page, signIn, false)) && (await inside(page)));
  }
  if (ok) await context.storageState({ path: process.env.EAOS_STORAGE_STATE });
  await browser.close();
  console.log(JSON.stringify(ok ? { E2E_USER: user, E2E_PASSWORD: password } : { signed_in: false, tried }));
  process.exit(ok ? 0 : 1);
})();
