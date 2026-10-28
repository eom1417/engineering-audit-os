// The sheet primitive of the design system: alike its siblings on purpose.
import React from 'react';

export function Sheet({ title, children, actions }) {
  return (
    <div className="overlay fixed inset-0">
      <div className="sheet rounded p-6">
        <h2 className="sheet-title">{title}</h2>
        <div className="sheet-body">{children}</div>
        <div className="sheet-actions">{actions}</div>
      </div>
    </div>
  );
}
