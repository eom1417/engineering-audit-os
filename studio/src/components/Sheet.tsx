// A sheet: React Aria's modal dialog (focus trapped and restored, Esc and the scrim close it), drawn as a bottom
// sheet on the phone and a centred dialog on desktop. The dialog and React Aria's modal parts are their own chunk
// (SheetDialog, vite.config.ts classicChunks): read when the browser is idle once the report is drawn, drawn from the
// sheet's first opening, so no page carries them before it draws.
import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { useLoaded } from '../data/context'
import { useOpenedOnce, whenIdle } from '../shell/later'
import css from './Sheet.module.css'

const loadDialog = () => import('./SheetDialog')
const SheetDialog = lazy(() => loadDialog().then((module) => ({ default: module.SheetDialog })))

export function Sheet(props: { isOpen: boolean; onOpenChange: (open: boolean) => void; title: string; children: ReactNode }) {
  const opened = useOpenedOnce(props.isOpen)
  const ready = useLoaded().kind === 'ready'
  useEffect(() => (ready ? whenIdle(() => { void loadDialog() }) : undefined), [ready])
  if (!opened) return null
  return <Suspense fallback={null}><SheetDialog {...props} /></Suspense>
}

export function SheetSub({ children }: { children: ReactNode }) {
  return <h3 className={css.sub}>{children}</h3>
}

export function SheetLead({ children }: { children: ReactNode }) {
  return <p className={css.lead}>{children}</p>
}
