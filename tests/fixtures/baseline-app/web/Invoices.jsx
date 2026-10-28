// The invoices screen: each invoice and a confirmation before one is cancelled.
import React, { useEffect, useState } from 'react';

export default function Invoices({ invoices }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const close = (e) => { if (e.key === 'Escape') setOpen(false); };
    addEventListener('keydown', close);
    return () => removeEventListener('keydown', close);
  }, []);
  return (
    <main>
      <h1>Invoices</h1>
      <ul>{invoices.map(i => <li key={i.id}>{i.number}, {new Date(i.at).toLocaleDateString()}</li>)}</ul>
      <button onClick={() => setOpen(true)}>Cancel invoice</button>
      {open && (
        <div className="overlay fixed inset-0">
          <div className="modal rounded p-6">
            <h2 className="modal-title">Are you sure?</h2>
            <p className="modal-body">The invoice is cancelled for good.</p>
            <div className="modal-actions"><button className="btn">Yes</button><button className="btn ghost" onClick={() => setOpen(false)}>No</button></div>
          </div>
        </div>
      )}
    </main>
  );
}
