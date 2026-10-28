// The person's settings, kept in the browser.
export function settings() {
  return JSON.parse(localStorage.getItem('settings') || '{}');
}
