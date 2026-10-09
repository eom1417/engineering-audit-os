// #/library/docs: every document the check wrote, grouped by purpose, in the report's reading order, with search over
// titles, paths and headings (Arabic spellings folded), and the images and diagrams beside them. ?group= shows one
// group, ?q= keeps the search in the address.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo } from 'react'
import { SearchField } from '../../components/Controls'
import { Go } from '../../components/Go'
import { FoldList, Panel, RowLink, Section, StateMessage } from '../../components/Panel'
import type { Doc, StudioData } from '../../data/types'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { docPath, grouped, imagePath, minutes, readingList, searchDocs, type MediaImage } from './model'
import { groupWord, useLibraryWords } from './words'
import css from './library.module.css'

interface LibrarySearch { group?: string; q?: string }

export function mediaOf(data: StudioData): MediaImage[] {
  return ((data.media as { images?: MediaImage[] } | undefined)?.images ?? [])
}

function DocRow({ doc, heading, numbered }: { doc: Doc; heading?: string; numbered?: number }) {
  const w = useLibraryWords()
  return (
    <RowLink to={docPath(doc.path)} search={heading ? { h: heading } : undefined} icon={numbered === undefined ? 'file' : undefined}
      title={<>{numbered !== undefined && <span className={css.order} aria-hidden="true"><span className="num">{numbered}</span></span>} <Txt>{doc.title}</Txt></>}
      sub={<span className={css.rowMeta}>
        {heading ? <span className={css.hitHeading}>{w('inSection')} <Txt>{heading}</Txt></span> : <Id value={doc.path} keep={2} />}
        <span aria-label={w('minReadAria', { n: minutes(doc.bytes) })}>{w('minRead', { n: minutes(doc.bytes) })}</span>
      </span>} />
  )
}

function LibraryBody({ data }: { data: StudioData }) {
  const w = useLibraryWords()
  usePageChrome(w('library'), undefined, data.manifest.project.name)
  const search = useSearch({ strict: false }) as LibrarySearch
  const navigate = useNavigate()
  const docs = useMemo(() => data.docs?.docs ?? [], [data.docs])
  const images = mediaOf(data)
  const groups = useMemo(() => grouped(docs), [docs])
  const first = useMemo(() => readingList(docs).filter((d) => d.order !== null), [docs])
  const query = search.q ?? ''
  const phone = usePhone()
  const hits = useMemo(() => searchDocs(docs, query), [docs, query])
  const shown = search.group ? groups.filter(([group]) => group === search.group) : groups
  const setQuery = (q: string) => navigate({ to: '/library/docs', search: { ...(search.group ? { group: search.group } : {}), ...(q ? { q } : {}) }, replace: true })

  if (!docs.length && !images.length) {
    return (
      <div className={layout.page}>
        <PageTitle title={w('documents')} />
        <Panel><StateMessage icon="book" title={w('noDocs')} sub={w('noDocsSub')} /></Panel>
      </div>
    )
  }
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={w('documents')} lead={<>{w('lead')} <span className="num">{w('counts', { d: docs.length, i: images.length })}</span></>} />
      <div className={css.tools}>
        <SearchField label={w('searchDocs')} placeholder={w('searchPlaceholder')} value={query} onChange={setQuery} />
        {!query && (
          <nav className={css.groupChips} aria-label={w('groupFilter')}>
            <Go to="/library/docs" className={css.groupChip} current={!search.group}>{w('allGroups')} <N value={docs.length} /></Go>
            {groups.map(([group, rows]) => (
              <Go key={group} to="/library/docs" search={{ group }} className={css.groupChip} current={search.group === group}>
                {groupWord(w, group)} <N value={rows.length} />
              </Go>
            ))}
          </nav>
        )}
      </div>
      {query ? (
        <Section title={w('results', { n: hits.length })} id="s-results">
          <Panel>
            {hits.length ? <FoldList items={hits} first={12} render={(hit) => <DocRow doc={hit.doc} heading={hit.heading} />} />
              : <StateMessage icon="search" title={w('noMatch')} />}
          </Panel>
        </Section>
      ) : (
        <div className={css.columns}>
          <div className={css.col}>
            {shown.map(([group, rows]) => (
              <Section key={group} title={groupWord(w, group)} count={rows.length} id={`g-${group}`}>
                <Panel><FoldList items={rows} first={phone && !search.group ? 3 : 6} render={(doc) => <DocRow doc={doc} />} label={groupWord(w, group)} /></Panel>
              </Section>
            ))}
          </div>
          <div className={[css.col, css.side].join(' ')}>
            {!search.group && first.length > 0 && (
              <Section title={w('readFirst')} count={first.length} id="s-read-first">
                <Panel><FoldList items={first} first={phone ? 5 : 8} render={(doc, i) => <DocRow doc={doc} numbered={i + 1} />} label={w('readFirst')} /></Panel>
              </Section>
            )}
            <Section title={w('images')} count={images.length} id="s-images">
              <Panel>
                {images.length ? <FoldList items={images} first={6} render={(image) => (
                  <RowLink to={imagePath(image.id)} icon={image.kind === 'diagram' ? 'flow' : 'eye'} title={<Txt>{image.title}</Txt>}
                    sub={<Id value={image.path} keep={2} />} />
                )} label={w('images')} /> : <StateMessage title={w('noImages')} />}
              </Panel>
            </Section>
          </div>
        </div>
      )}
    </div>
  )
}

export function LibraryPage() {
  return <WithData>{(data) => <LibraryBody data={data} />}</WithData>
}
