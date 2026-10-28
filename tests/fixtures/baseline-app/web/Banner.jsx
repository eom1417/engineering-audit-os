// A banner: a variant of the notice, made different on purpose (a picture and a link, no buttons).
import React from 'react';

export default function Banner({ text, href, picture }) {
  return (
    <aside className="banner">
      <img src={picture} alt="" />
      <span className="banner-text">{text}</span>
      <a className="banner-link" href={href}>More</a>
      <small className="banner-note">Shown once</small>
    </aside>
  );
}
