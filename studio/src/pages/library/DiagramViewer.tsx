// A diagram full screen: React Aria's modal dialog (focus trapped and restored, Esc closes it) over the whole window,
// the drawing fitted to it, then dragged, pinched, wheeled or zoomed with the buttons. Its own chunk, read the first
// time a reader opens one.
import { useMemo, useRef } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { IconButton } from '../../components/Button'
import { usePrefs } from '../../i18n/prefs'
import { renameIds, ZOOM, type Size } from './diagram'
import type { Drawing } from './diagramEngine'
import { DrawingBox } from './DrawingBox'
import { usePanZoom } from './usePanZoom'
import { useLibraryWords } from './words'
import css from './library.module.css'

function Viewer({ title, drawing, natural, close }: { title: string; drawing: Drawing; natural: Size; close: () => void }) {
  const w = useLibraryWords()
  const { t, num } = usePrefs()
  const box = useRef<HTMLDivElement>(null)
  const view = usePanZoom(box, natural, { fill: 0.96, fitHeight: true, pinch: true, wheel: true })
  // the page already holds the drawing in the document: this copy's ids are its own
  const svg = useMemo(() => renameIds(drawing.svg, drawing.id, '-full'), [drawing])
  return (
    <>
      <header className={css.viewerHead}>
        <Heading slot="title" className={css.viewerTitle}>{title}</Heading>
        <span className={css.diagramTools}>
          <IconButton icon="zoomOut" label={w('zoomOut')} onPress={() => view.zoomBy(1 / ZOOM.step)} />
          <span className={css.zoomLevel} aria-live="polite">{view.k === null ? '' : `${num(Math.round(view.k * 100))}%`}</span>
          <IconButton icon="zoomIn" label={w('zoomIn')} onPress={() => view.zoomBy(ZOOM.step)} />
          <IconButton icon="fit" label={w('zoomFit')} onPress={view.fit} />
          <IconButton icon="x" label={t('close')} onPress={close} />
        </span>
      </header>
      <DrawingBox svg={svg} natural={natural} k={view.k} box={box} label={title} pans={view.pans} className={css.viewerBox} />
    </>
  )
}

export function DiagramViewer({ isOpen, onOpenChange, title, drawing, natural }:
  { isOpen: boolean; onOpenChange: (open: boolean) => void; title: string; drawing: Drawing; natural: Size }) {
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable className={css.viewerOverlay}>
      <Modal className={css.viewer}>
        <Dialog className={css.viewerDialog}>
          {({ close }) => <Viewer title={title} drawing={drawing} natural={natural} close={close} />}
        </Dialog>
      </Modal>
    </ModalOverlay>
  )
}
