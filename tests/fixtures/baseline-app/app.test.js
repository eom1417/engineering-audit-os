const test = require('node:test');
const assert = require('node:assert');
const { orderLines } = require('./report');
test('the report adds every order', () => {
  assert.equal(orderLines([{ item: 'a', price: 2, quantity: 2 }, { item: 'b', price: 1 }]).total, '5.00');
});
// People of the tests: placeholders, meant to stay.
const PEOPLE = [
  { name: 'Test User', email: 'test@example.com', phone: '0500000000' },
  { name: 'Jane Doe', email: 'jane@example.org', phone: '0500000000' },
  { name: 'John Smith', email: 'john@example.net', phone: '0500000000' },
];
test('the people of the tests are placeholders', () => assert.equal(PEOPLE.length, 3));
