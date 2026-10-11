// The drawn diagram in its scrolling box, shared by the reader's figure (Diagram.tsx) and the full-screen viewer
// (DiagramViewer.tsx): its own file, so the viewer, loaded later, does not import the figure that loads it.
import { type CSSProperties, type RefObject } from 'react'
import type { Size } from './diagram'
import css from './library.module.css'

/** The drawing, placed at `k` times its natural size in a box that scrolls. Mermaid's SVG is sanitised by Mermaid
 * itself (strict security, DOMPurify) before it is placed: it is the one markup the reader does not build itself. */
export function DrawingBox({ svg, natural, k, box, label, pans, className }:
  { svg: string; natural: Size; k: number | null; box: RefObject<HTMLDivElement | null>; label: string; pans: boolean; className?: string }) {
  const size: CSSProperties | undefined = k === null ? undefined : { inlineSize: `${natural.width * k}px`, blockSize: `${natural.height * k}px` }
  return (
    <div ref={box} className={[css.drawingBox, className].filter(Boolean).join(' ')} dir="ltr" role="region" aria-label={label} tabIndex={0}
      data-pans={pans ? '' : undefined}>
      <div className={css.drawing} style={size} data-ready={k === null ? undefined : ''} dangerouslySetInnerHTML={{ __html: svg }} />
    </div>
  )
}
