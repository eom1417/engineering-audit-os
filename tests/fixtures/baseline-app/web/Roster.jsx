// The roster screen: who works where, the orders of each month, and the menu.
import React from 'react';
import { STAFF, MONTHLY_ORDERS } from './staff';
import { MENU, EXAMPLE_ROW } from './menu';

export default function Roster() {
  const rows = STAFF.length ? STAFF : [EXAMPLE_ROW];
  return (
    <main>
      <nav>{MENU.map(link => <a key={link.path} href={link.path}>{link.label}</a>)}</nav>
      <ul>{rows.map(person => <li key={person.name}>{person.name}: {person.dept}</li>)}</ul>
      <p>{Object.keys(MONTHLY_ORDERS).length} months</p>
    </main>
  );
}
