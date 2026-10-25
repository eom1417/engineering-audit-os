// The orders screen of the new front end: it asks the server, which knows who is signed in.
import React, { useEffect, useState } from 'react';

export default function Orders() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    fetch('/api/orders').then(res => (res.ok ? res.json() : [])).then(setRows);
  }, []);
  return (
    <ul>
      {rows.map(row => <li key={row.id}>{row.item}: {row.price}</li>)}
    </ul>
  );
}
