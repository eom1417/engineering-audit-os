const test = require('node:test');
const assert = require('node:assert');
const { orderLines } = require('./report');
test('the report adds every order', () => {
  assert.equal(orderLines([{ item: 'a', price: 2, quantity: 2 }, { item: 'b', price: 1 }]).total, '5.00');
});
