// The dialog primitive of the design system: alike its siblings on purpose.
import React from 'react';

export function Dialog({ title, children, actions }) {
  return (
    <div className="overlay fixed inset-0">
      <div className="dialog rounded p-6">
        <h2 className="dialog-title">{title}</h2>
        <div className="dialog-body">{children}</div>
        <div className="dialog-actions">{actions}</div>
      </div>
    </div>
  );
}
