// A Mermaid diagram or chart in a document, drawn by the engine (diagramEngine.ts, read the first time a document
// holds one) in the Studio's theme and font, left to right inside a right-to-left page. It fits the column's width,
// but never below a readable scale: a large map then pans inside its box. Its toolbar zooms, opens it full screen
// (DiagramViewer, its own chunk), shows its source and copies it. A diagram the engine cannot read shows its source
// and why, never a broken page.
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { copyText, IconButton } from '../../components/Button'
import { Icon } from '../../components/Icon'
import { useToast } from '../../components/Toast'
import { usePrefs } from '../../i18n/prefs'
import { useOpenedOnce } from '../../shell/later'
import { diagramKind, floorFor, readTheme, ZOOM, type DiagramKind } from './diagram'
import type { Drawing } from './diagramEngine'
import { DrawingBox } from './DrawingBox'
import { usePanZoom } from './usePanZoom'
import { useLibraryWords } from './words'
import css from './library.module.css'

export const loadEngine = () => import('./diagramEngine')
const DiagramViewer = lazy(() => import('./DiagramViewer').then((module) => ({ default: module.DiagramViewer })))

type State = { kind: 'loading' } | { kind: 'drawn'; drawing: Drawing } | { kind: 'failed'; why: string }

/** The first line of an engine's error: what a person can act on, without its stack. */
function reason(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  return (text.split('\n').map((line) => line.trim()).find(Boolean) ?? '').replace(/[:\s]+$/, '').slice(0, 240)
}

export function useKindWord() {
  const w = useLibraryWords()
  return (kind: DiagramKind) => (kind === 'diagram' ? w('kind_any') : w(`kind_${kind}`))
}

function Source({ source, label }: { source: string; label: string }) {
  return <pre className={css.pre} dir="ltr" tabIndex={0} aria-label={label}><code>{source}</code></pre>
}

/** The diagram as the engine draws it in the page's theme, drawn again when the source or the theme changes. */
function useDrawing(figure: RefObject<HTMLElement | null>, source: string, dark: boolean): State {
  const [state, setState] = useState<State>({ kind: 'loading' })
  useEffect(() => {
    let live = true
    const el = figure.current
    if (!el) return
    // the theme is read once the engine has arrived, after the page has applied the new theme
    loadEngine().then((engine) => engine.draw(source, readTheme(el, dark)))
      .then((drawing) => { if (live) setState({ kind: 'drawn', drawing }) }, (error: unknown) => { if (live) setState({ kind: 'failed', why: reason(error) }) })
    return () => { live = false }
  }, [figure, source, dark])
  return state
}

function ZoomTools({ view, onFull }: { view: ReturnType<typeof usePanZoom>; onFull: () => void }) {
  const w = useLibraryWords()
  const { num } = usePrefs()
  return <>
    <IconButton small icon="zoomOut" label={w('zoomOut')} onPress={() => view.zoomBy(1 / ZOOM.step)} />
    <span className={css.zoomLevel} aria-live="polite">{view.k === null ? '' : `${num(Math.round(view.k * 100))}%`}</span>
    <IconButton small icon="zoomIn" label={w('zoomIn')} onPress={() => view.zoomBy(ZOOM.step)} />
    <IconButton small icon="fullScreen" label={w('fullScreen')} onPress={onFull} data-open="diagram" />
  </>
}

function Failed({ why }: { why: string }) {
  const w = useLibraryWords()
  return (
    <div className={css.diagramFailed} role="note">
      <Icon name="info" />
      <span>{w('diagramFailed')}{why && <> <span className={css.diagramWhy}>{w('diagramWhy', { why: '' })}<bdi dir="ltr">{why}</bdi></span></>}</span>
    </div>
  )
}

export function Diagram({ source, n }: { source: string; n: number }) {
  const w = useLibraryWords()
  const kindWord = useKindWord()
  const { theme } = usePrefs()
  const toast = useToast()
  const kind = diagramKind(source)
  const name = w('diagramN', { n, kind: kindWord(kind) })
  const figure = useRef<HTMLElement>(null)
  const box = useRef<HTMLDivElement>(null)
  const state = useDrawing(figure, source, theme === 'dark')
  const [showSource, setShowSource] = useState(false)
  const [full, setFull] = useState(false)
  const opened = useOpenedOnce(full)

  const drawing = state.kind === 'drawn' ? state.drawing : null
  const natural = useMemo(() => (drawing && drawing.width > 0 ? { width: drawing.width, height: drawing.height } : null), [drawing])
  const view = usePanZoom(box, natural, { floor: floorFor(kind) })
  const copy = async () => toast((await copyText(source)) ? w('copiedSource') : w('copyFailed'))

  return (
    <figure ref={figure} className={css.diagram} data-kind={kind} data-state={state.kind}>
      <div className={css.diagramBar}>
        <span className={css.diagramName}><Icon name="flow" />{name}</span>
        <span className={css.diagramTools}>
          {drawing && natural && <ZoomTools view={view} onFull={() => setFull(true)} />}
          {state.kind !== 'failed' && (
            <IconButton small icon="code" label={w('showSourceLong')} onPress={() => setShowSource((on) => !on)} aria-pressed={showSource} />
          )}
          <IconButton small icon="copy" label={w('copySource')} onPress={() => { void copy() }} />
        </span>
      </div>
      {state.kind === 'loading' && <div className={css.diagramLoading} role="status">{w('diagramLoading')}</div>}
      {drawing && natural && <DrawingBox svg={drawing.svg} natural={natural} k={view.k} box={box} label={name} pans={view.pans} />}
      {drawing && view.pans && <p className={css.diagramHint}>{w('diagramPan')}</p>}
      {state.kind === 'failed' && <Failed why={state.why} />}
      {(showSource || state.kind === 'failed') && <Source source={source} label={w('sourceOf', { name })} />}
      {opened && drawing && natural && (
        <Suspense fallback={null}>
          <DiagramViewer isOpen={full} onOpenChange={setFull} title={name} drawing={drawing} natural={natural} />
        </Suspense>
      )}
    </figure>
  )
}
