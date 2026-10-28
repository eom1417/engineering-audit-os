// The API's amount, as the invoices it sends write it: an amount shown with its currency.
function apiAmount(amount, currency) {
  const value = Number(amount) || 0;
  const rounded = Math.round(value * 100) / 100;
  const sign = rounded < 0 ? '-' : '';
  const whole = Math.floor(Math.abs(rounded)).toLocaleString('en-US');
  const cents = String(Math.round(Math.abs(rounded) * 100) % 100).padStart(2, '0');
  return `${sign}${whole}.${cents} ${currency}`;
}

module.exports = { apiAmount };
