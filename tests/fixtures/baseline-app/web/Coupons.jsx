// The coupons screen: each coupon and a confirmation before one is removed.
import React, { useEffect, useState } from 'react';

export default function Coupons({ coupons }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const close = (e) => { if (e.key === 'Escape') setOpen(false); };
    addEventListener('keydown', close);
    return () => removeEventListener('keydown', close);
  }, []);
  return (
    <article>
      <form><input name="code" /><select name="kind"><option>percent</option></select></form>
      {coupons.map(c => <p key={c.code}>{c.code} until {new Date(c.until).toISOString().slice(0, 10)}</p>)}
      <button onClick={() => setOpen(true)}>Remove coupon</button>
      {open && (
        <div className="overlay fixed inset-0">
          <div className="modal rounded p-6">
            <h2 className="modal-title">Are you sure?</h2>
            <p className="modal-body">The coupon stops working.</p>
            <div className="modal-actions"><button className="btn">Yes</button><button className="btn ghost" onClick={() => setOpen(false)}>No</button></div>
          </div>
        </div>
      )}
    </article>
  );
}
