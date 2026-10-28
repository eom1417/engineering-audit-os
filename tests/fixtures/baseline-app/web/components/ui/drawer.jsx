// The drawer primitive of the design system: alike its siblings on purpose.
import React from 'react';

export function Drawer({ title, children, actions }) {
  return (
    <div className="overlay fixed inset-0">
      <div className="drawer rounded p-6">
        <h2 className="drawer-title">{title}</h2>
        <div className="drawer-body">{children}</div>
        <div className="drawer-actions">{actions}</div>
      </div>
    </div>
  );
}
