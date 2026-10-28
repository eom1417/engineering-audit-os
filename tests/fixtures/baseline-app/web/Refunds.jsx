// The refunds screen: each refund and a confirmation before one is sent.
import React, { useEffect, useState } from 'react';

export default function Refunds({ refunds }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const close = (e) => { if (e.key === 'Escape') setOpen(false); };
    addEventListener('keydown', close);
    return () => removeEventListener('keydown', close);
  }, []);
  const day = (iso) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' }).format(new Date(iso));
  return (
    <section>
      <table><tbody>{refunds.map(r => <tr key={r.id}><td>{r.item}</td><td>{day(r.at)}</td></tr>)}</tbody></table>
      <button onClick={() => setOpen(true)}>Send refund</button>
      {open && (
        <div className="overlay fixed inset-0">
          <div className="modal rounded p-6">
            <h2 className="modal-title">Are you sure?</h2>
            <p className="modal-body">This cannot be undone.</p>
            <div className="modal-actions"><button className="btn">Yes</button><button className="btn ghost" onClick={() => setOpen(false)}>No</button></div>
          </div>
        </div>
      )}
    </section>
  );
}
