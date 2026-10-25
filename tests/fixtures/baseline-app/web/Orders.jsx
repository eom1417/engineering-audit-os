// The orders screen of the new front end.
import React, { useEffect, useState } from 'react';
import { Pool } from 'pg';

const db = new Pool({ connectionString: import.meta.env.VITE_DATABASE_URL });

export default function Orders() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    db.query('select id, item, price, quantity from orders order by id').then(result => setRows(result.rows));
  }, []);
  return (
    <ul>
      {rows.map(row => <li key={row.id}>{row.item}: {row.price}</li>)}
    </ul>
  );
}
