// The check's pictures of the person's app (live/screens/…): read with the launch token (/api/report-image, a data:
// address, kept for the page), drawn at their own aspect with the findings placed on them as numbered regions (placed from the picture's own left:
// a picture does not mirror). The
// read-only copy carries no pictures: it says so.
import { t, num, esc, data, refresh, offline } from 'eaos';

const got = new Map();
/** The picture's data: address once read; null while it is read or when it cannot be (then `failed`). */
function picture(path) {
  if (offline()) return { state: 'offline' };
  if (!got.has(path)) {
    const entry = { state: 'loading' };
    got.set(path, entry);
    data.tokenImage('/api/report-image?path=' + encodeURIComponent(path)).then(src => { Object.assign(entry, src ? { state: 'ready', src } : { state: 'failed' }); refresh(); });
  }
  return got.get(path);
}

/** A figure of `shot` ({path, width, height}) with `pins` [{n, region {x, y, width, height} | null, on}]. */
export function figure(shot, pins, caption) {
  const w = shot.width || 390, h = shot.height || (w <= 480 ? 844 : 900);
  const pic = picture(shot.path);
  const regions = (pins || []).filter(p => p.region).map(p => `<span class="un-pin ${p.on ? 'is-on' : ''}" style="left:${(p.region.x * 100).toFixed(1)}%;top:${(p.region.y * 100).toFixed(1)}%;width:${(p.region.width * 100).toFixed(1)}%;height:${(p.region.height * 100).toFixed(1)}%" aria-hidden="true"><b>${num(p.n)}</b></span>`).join('');
  const inner = pic.state === 'ready' ? `<img src="${pic.src}" alt="${esc(caption)}" width="${w}" height="${h}">${regions}`
    : `<span class="un-picwait small muted" ${pic.state === 'loading' ? 'aria-busy="true"' : ''}>${t(pic.state === 'loading' ? 'un.pic.loading' : pic.state === 'offline' ? 'un.pic.offline' : 'un.scr.unreadable')}</span>`;
  return `<figure class="un-picfig ${w <= 480 ? 'un-picfig--phone' : ''}"><div class="un-picwrap" style="aspect-ratio:${w}/${h}">${inner}</div>
    <figcaption class="small muted">${esc(caption)}</figcaption></figure>`;
}
