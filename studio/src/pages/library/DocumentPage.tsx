// #/library/docs/<path>?h=<heading>: one document read in the Studio. 68ch measure; its contents beside it on a wide
// screen and in a sheet on the phone; ids and links to other documents open their Studio pages; code and tables scroll
// on their own; the next and previous documents in the report's reading order at the end. ?h= opens it at a heading.
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { Button } from '../../components/Button'
import { Chip } from '../../components/Chip'
import { Go } from '../../components/Go'
import { Panel, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import type { Doc, StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, WithData } from '../../shell/Layout'
import { drawMarkdown, type Heading } from './markdown'
import { decoded, docPath, minutes, readingList, sameHeading, useLazySection, type LibraryData } from './model'
import { groupWord, useLibraryWords } from './words'
import css from './library.module.css'

/** The heading nearest above the top of the window, for the contents' current mark. */
function useCurrentHeading(headings: Heading[]): string | undefined {
  const [current, setCurrent] = useState<string>()
  useEffect(() => {
    if (!headings.length) return
    const onScroll = () => {
      const top = 120
      let found: string | undefined
      for (const h of headings) {
        const el = document.getElementById(h.id)
        if (el && el.getBoundingClientRect().top <= top) found = h.id
      }
      setCurrent(found)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [headings])
  return current
}

function Contents({ headings, current, onPick }: { headings: Heading[]; current?: string; onPick: (h: Heading) => void }) {
  return (
    <nav className={css.toc}>
      {headings.filter((h) => h.depth <= 3).map((h) => (
        <button key={h.id} type="button" className={css.tocItem} data-depth={h.depth} aria-current={current === h.id ? 'location' : undefined}
          onClick={() => onPick(h)}><Txt>{h.text}</Txt></button>
      ))}
    </nav>
  )
}

function Pager({ list, doc }: { list: Doc[]; doc: Doc }) {
  const w = useLibraryWords()
  const at = list.findIndex((d) => d.path === doc.path)
  const previous = at > 0 ? list[at - 1] : undefined
  const next = at >= 0 && at < list.length - 1 ? list[at + 1] : undefined
  if (!previous && !next) return null
  return (
    <nav className={css.pager} aria-label={w('next')}>
      {previous && <Go to={docPath(previous.path)} className={css.pagerItem}><span className={css.pagerLabel}>{w('previous')}</span><span className={css.pagerTitle}><Txt>{previous.title}</Txt></span></Go>}
      {next && <Go to={docPath(next.path)} className={[css.pagerItem, css.pagerNext].join(' ')}><span className={css.pagerLabel}>{w('next')}</span><span className={css.pagerTitle}><Txt>{next.title}</Txt></span></Go>}
    </nav>
  )
}

function Reader({ data, doc, h }: { data: StudioData; doc: Doc; h?: string }) {
  const w = useLibraryWords()
  const navigate = useNavigate()
  const library = useLazySection<LibraryData>(data, 'library')
  const docs = useMemo(() => data.docs?.docs ?? [], [data.docs])
  const list = useMemo(() => readingList(docs), [docs])
  const text = library.kind === 'ready' ? library.data.documents.find((d) => d.id === doc.id) : undefined
  // the words change with the language only: the document is drawn again then, not on every render (a scroll that
  // moves the contents' mark would otherwise redraw it and bring ?h= back)
  const { lang } = usePrefs()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const words = useMemo(() => w, [lang])
  const ctx = useMemo(() => ({
    path: doc.path, title: doc.title, docs: new Set(docs.map((d) => d.path)), cards: new Set((data.cards?.cards ?? []).map((c) => c.id)),
    images: new Map((library.kind === 'ready' ? library.data.images : []).map((i) => [i.id, i])),
    w: words,
  }), [doc, docs, data.cards, library, words])
  const drawn = useMemo(() => (text ? drawMarkdown(text.text, ctx) : null), [text, ctx])
  const headings = drawn?.headings ?? []
  const current = useCurrentHeading(headings)
  const [sheet, setSheet] = useState(false)

  // ?h= opens the document at that heading (by its words, or its anchor)
  useEffect(() => {
    if (!h || !drawn) return
    const target = drawn.headings.find((x) => x.id === h || sameHeading(x.text, h))
    const el = target && document.getElementById(target.id)
    if (el) { el.scrollIntoView({ block: 'start' }); el.focus({ preventScroll: true }) }
  }, [h, drawn])

  const pick = (heading: Heading) => {
    setSheet(false)
    document.getElementById(heading.id)?.scrollIntoView({ block: 'start' })
    navigate({ to: '.', search: { h: heading.text }, replace: true })
  }

  return (
    <div className={layout.page}>
      <div className={css.reader}>
        <div className={css.readerMain}>
          <header className={css.docHead}>
            <h1 className={css.docTitle} dir="auto"><Txt>{doc.title}</Txt></h1>
            <div className={css.docMeta}>
              <Go to="/library/docs" search={{ group: doc.group }} className={css.metaLink}><Chip>{groupWord(w, doc.group)}</Chip></Go>
              <span title={w('reportPath')}><Id value={doc.path} /></span>
              <span>{w('minReadAria', { n: minutes(doc.bytes) })}</span>
            </div>
            {headings.length > 1 && <span className={css.tocButton}><Button icon="plan" onPress={() => setSheet(true)} data-open="contents">{w('contents')}</Button></span>}
          </header>
          {library.kind === 'loading' && <Panel><Skeleton label={w('loadingText')} /></Panel>}
          {library.kind !== 'loading' && !text && (
            <Panel><StateMessage icon="book" title={w('textMissing')} sub={<>{w('textMissingSub')} <Id value={doc.path} /></>} /></Panel>
          )}
          {text?.truncated && <div className={css.notice} role="note">{w('truncated', { n: text.text.length })}</div>}
          {drawn && <article className={css.article} aria-label={doc.title}>{drawn.body}</article>}
          <Pager list={list} doc={doc} />
        </div>
        {headings.length > 1 && (
          <aside className={css.aside} aria-label={w('onThisPage')}>
            <div className={css.asideTitle}>{w('onThisPage')}</div>
            <Contents headings={headings} current={current} onPick={pick} />
          </aside>
        )}
      </div>
      <Sheet isOpen={sheet} onOpenChange={setSheet} title={w('contents')}>
        <div className={css.sheetToc}><Contents headings={headings} onPick={pick} /></div>
      </Sheet>
    </div>
  )
}

function DocumentBody({ data }: { data: StudioData }) {
  const w = useLibraryWords()
  const { docId } = useParams({ strict: false }) as { docId?: string }
  const { h } = useSearch({ strict: false }) as { h?: string }
  const path = decoded(docId ?? '')
  const doc = (data.docs?.docs ?? []).find((d) => d.path === path)
  usePageChrome(doc?.title ?? w('notFound'), { to: '/library/docs', label: w('library') }, data.manifest.project.name)
  if (!doc) {
    return (
      <div className={layout.page}>
        <Panel><StateMessage icon="book" title={w('notFound')} sub={<>{w('notFoundSub')} <Id value={path || '—'} /></>}
          action={<div><Go to="/library/docs" className={css.groupChip}>{w('backToLibrary')}</Go></div>} /></Panel>
      </div>
    )
  }
  return <Reader key={doc.path} data={data} doc={doc} h={h} />
}

export function DocumentPage() {
  return <WithData>{(data) => <DocumentBody data={data} />}</WithData>
}
