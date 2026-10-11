// #/library/images/<id>: one image or diagram of the report. An image is shown from the Studio's own data (a data URI,
// which runs nothing); a Mermaid diagram is drawn by the reader's diagram engine (Diagram, docs/adoption/docs-reader.md)
// and links to the Studio's own interactive drawing of the same facts.
import { useParams } from '@tanstack/react-router'
import { Chip } from '../../components/Chip'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import { Panel, Skeleton, StateMessage } from '../../components/Panel'
import { buttonClass } from '../../components/Button'
import type { StudioData } from '../../data/types'
import { Id, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, WithData } from '../../shell/Layout'
import { Diagram } from './Diagram'
import { mediaOf } from './LibraryPage'
import { decoded, useLazySection, type LibraryData } from './model'
import { useLibraryWords } from './words'
import css from './library.module.css'

/** The Studio page that draws what a report diagram shows. */
function drawnBy(id: string): { to: string; search?: Record<string, string>; word: 'mapToday' | 'mapTarget' | 'mapJourneys' } {
  if (/target/i.test(id)) return { to: '/system', search: { view: 'target' }, word: 'mapTarget' }
  if (/(^|\/)system\.mmd$/.test(id)) return { to: '/system/journeys', word: 'mapJourneys' }
  return { to: '/system', word: 'mapToday' }
}

function ImageBody({ data }: { data: StudioData }) {
  const w = useLibraryWords()
  const { imageId } = useParams({ strict: false }) as { imageId?: string }
  const id = decoded(imageId ?? '')
  const image = mediaOf(data).find((i) => i.id === id)
  const library = useLazySection<LibraryData>(data, 'library')
  usePageChrome(image?.title ?? w('imageNotFound'), { to: '/library/docs', label: w('library') }, data.manifest.project.name)
  if (!image) {
    return <div className={layout.page}><Panel><StateMessage icon="eye" title={w('imageNotFound')} sub={<Id value={id || '—'} />} /></Panel></div>
  }
  const content = library.kind === 'ready' ? library.data.images.find((i) => i.id === image.id) : undefined
  const map = drawnBy(image.id)
  return (
    <div className={layout.page}>
      <header className={css.docHead}>
        <h1 className={css.docTitle}><Txt>{image.title}</Txt></h1>
        <div className={css.docMeta}><Chip>{w(`kind_${image.kind}`)}</Chip><Id value={image.path} /></div>
      </header>
      {library.kind === 'loading' && <Panel><Skeleton label={w('loadingText')} /></Panel>}
      {library.kind !== 'loading' && !content && <Panel><StateMessage icon="eye" title={w('imageMissing')} sub={<>{w('textMissingSub')} <Id value={image.path} /></>} /></Panel>}
      {content?.data && (
        <figure className={css.figure}>
          <div className={css.picture}><img src={content.data} alt={image.title} /></div>
        </figure>
      )}
      {content && !content.data && !content.source && content.reason === 'too_large' && (
        <Panel><StateMessage icon="eye" title={w('imageTooLarge', { n: Math.round((content.bytes ?? 0) / 1024) })} sub={<Id value={image.path} />} /></Panel>
      )}
      {content?.source !== null && content?.source !== undefined && (
        <figure className={css.figure}>
          <div className={css.notice} role="note"><Icon name="flow" /><span>{w('diagramNote')}</span></div>
          <div className={css.actions}><Go to={map.to} search={map.search} className={buttonClass('primary')}><Icon name="system" />{w(map.word)}</Go></div>
          <Diagram source={content.source} n={1} />
        </figure>
      )}
    </div>
  )
}

export function ImagePage() {
  return <WithData>{(data) => <ImageBody data={data} />}</WithData>
}
