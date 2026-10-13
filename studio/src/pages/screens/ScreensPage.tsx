// System -> Screens (#/screens) and one screen (#/screens/<screenId>), C-experience 3.4. The gallery: every screen a
// person opens as a card (its shot, else a designed "not captured" frame with its route), its open issues or "not
// checked", the journeys' flags; filter chips in the URL (?show=). One screen: its shot at a true viewport with the
// issues pinned (390 / 1440, before / after / slider when a batch changed it), its issues, inputs, file and route.
// What EAOS has not measured (shots, issues, inputs) is said, with the step that brings it, never shown as "none".
import { Link, useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { useMemo, useRef, useState } from 'react'
import { Button } from '../../components/Button'
import { DirectAction } from '../../command/Direct'
import { Chip } from '../../components/Chip'
import { Segmented } from '../../components/Controls'
import { Go } from '../../components/Go'
import { Icon } from '../../components/Icon'
import { Panel, Section, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import { TokenImage } from '../../components/TokenImage'
import type { StudioData } from '../../data/types'
import { usePrefs } from '../../i18n/prefs'
import { Id, N, Txt } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout, MissingBanner, WithData } from '../../shell/Layout'
import type { FunctionsData } from '../functions/model'
import { useCoverageRow, useLazySection } from '../library/model'
import { usePhone } from '../SystemMap'
import { SystemViews } from '../system/SystemViews'
import { FILTERS, filterScreens, gallery, marks, measured, pins, shotsAt, thumbnail, widths, type Issue, type PageFinding, type Picture, type PicturedPage,
  type Screen, type ScreenFilter, type ScreensData, type Shot } from './model'
import { SCREEN_WORDS, useScreenWords, type ScreenWord } from './words'
import css from './Screens.module.css'

type Search = { show?: string; vp?: string; compare?: string; every?: string }

function ScreenLink({ id, className, children, label }: { id: string; className?: string; children: React.ReactNode; label?: string }) {
  return <Link to="/screens/$screenId" params={{ screenId: id }} className={className} aria-label={label}>{children}</Link>
}

/** The designed state of what is not captured or checked yet, with the request that captures the screens. */
function NotCaptured({ sx }: { sx: ScreensData }) {
  const w = useScreenWords()
  const { lang } = usePrefs()
  const gap = (sx.missing ?? []).find((g) => g.id === 'shots')
  if (!gap) return null
  return (
    <Panel>
      <StateMessage icon="eye" title={w('notCaptured')}
        sub={<>{w('notCapturedSub')}<br /><Txt>{gap.detail[lang]}</Txt></>}
        action={<div><DirectAction request={{ action: 'run_setup' }} label={w('askCapture')} block copy={{ request: w('captureRequest'), tool: 'run_setup' }} /></div>} />
    </Panel>
  )
}

function Badge({ screen, checked }: { screen: Screen; checked: boolean }) {
  const w = useScreenWords()
  const open = screen.issues.filter((i) => i.state === 'open').length
  if (!screen.shots.length) return null              // the frame already says it is not captured
  if (!checked) return <span className={css.badgeMuted}>{w('notChecked')}</span>
  return open ? <span className={css.badgeIssues}>{w('issuesN', { n: open })}</span> : <span className={css.badgeOk}>{w('noIssues')}</span>
}

function Frame({ screen }: { screen: Screen }) {
  const w = useScreenWords()
  const shot = thumbnail(screen)
  const [broken, setBroken] = useState(false)
  if (shot && !broken) return <TokenImage className={css.thumbImg} path={shot.path} alt="" loading="lazy" decoding="async" onError={() => setBroken(true)} />
  return (
    <span className={css.thumbEmpty} aria-hidden="true">
      <span className={css.thumbBar} /><span className={css.thumbRoute}><Id value={screen.route} /></span>
      <span className={css.thumbWord}>{w('noShot')}</span>
    </span>
  )
}

function Card({ screen, checked }: { screen: Screen; checked: boolean }) {
  const w = useScreenWords()
  return (
    <li className={css.cardItem}>
      <ScreenLink id={screen.id} className={css.card}>
        <span className={css.thumb}><Frame screen={screen} /></span>
        <span className={css.cardBody}>
          <span className={css.cardTitle}><Txt>{screen.title}</Txt></span>
          <span className={css.cardRoute}><Id value={screen.route} /></span>
          <span className={css.cardMeta}>
            <Badge screen={screen} checked={checked} />
            {(screen.flags ?? []).slice(0, 1).map((f) => <span key={f} className={css.flag}>{w(`flag_${f}`)}</span>)}
          </span>
        </span>
      </ScreenLink>
    </li>
  )
}

function Heading({ data, sx, pictured }: { data: StudioData; sx?: ScreensData; pictured?: { total: number; found: number } }) {
  const w = useScreenWords()
  if (pictured) {
    return (
      <>
        <MissingBanner data={data} />
        <SystemViews current="screens" />
        <div className={layout.titleBlock}>
          <h1 className={layout.largeTitle}>{w('screens')}</h1>
          <p className={layout.lead}>{w('galleryLead', { t: pictured.total, f: pictured.found })}</p>
        </div>
      </>
    )
  }
  const shot = sx ? sx.screens.filter((s) => s.shots.length).length : 0
  const open = sx ? sx.screens.reduce((n, s) => n + s.issues.filter((i) => i.state === 'open').length, 0) : 0
  return (
    <>
      <MissingBanner data={data} />
      <SystemViews current="screens" />
      <div className={layout.titleBlock}>
        <h1 className={layout.largeTitle}>{w('screens')}</h1>
        {sx && <p className={layout.lead}>{sx.screens.length ? <>{w('lead', { s: sx.screens.length })}{shot ? <> {w('leadShots', { n: shot, i: open })}</> : null}</> : w('leadNone')}</p>}
      </div>
    </>
  )
}

/** The pictured pages' gallery when the check pictured the app; every declared screen as cards otherwise (or on ?every=1). */
function Gallery({ data, sx }: { data: StudioData; sx: ScreensData }) {
  const search = useSearch({ strict: false }) as Search
  return (sx.pages ?? []).length && search.every !== '1' ? <PicturedGallery data={data} sx={sx} /> : <ScreenGrid data={data} sx={sx} />
}

function ScreenGrid({ data, sx }: { data: StudioData; sx: ScreensData }) {
  const w = useScreenWords()
  const search = useSearch({ strict: false }) as Search
  const navigate = useNavigate()
  const filter = (FILTERS as readonly string[]).includes(search.show ?? '') ? search.show as ScreenFilter : 'all'
  const checked = measured(sx, 'issues')
  const offered = FILTERS.filter((f) => f === 'all' || f === 'flagged' || (f === 'issues' ? checked : sx.screens.some((s) => s.shots.length)))
  const kept = filterScreens(sx.screens, filter)
  const set = (show: ScreenFilter) => navigate({ to: '/screens', replace: true, search: { ...(search.every ? { every: search.every } : {}), ...(show === 'all' ? {} : { show }) } })
  const { t } = usePrefs()
  const phone = usePhone()
  const [open, setOpen] = useState(false)
  const first = phone ? 12 : 48
  return (
    <div className={layout.page}>
      <Heading data={data} sx={sx} />
      {(sx.pages ?? []).length > 0 && <div className={css.links}><Go to="/screens" className={css.inlineLink}>{w('backToGallery')}</Go></div>}
      <NotCaptured sx={sx} />
      {sx.screens.length > 0 && (
        <>
          <div className={css.toolbar}>
            <div className={css.chips} role="group" aria-label={w('filter')}>
              {offered.map((f) => (
                <button key={f} type="button" className={css.chipBtn} aria-pressed={filter === f} onClick={() => set(f)}>
                  {w(`filter_${f}`)}
                </button>
              ))}
            </div>
            <span className={css.count} aria-live="polite">{w('shown', { n: kept.length, t: sx.screens.length })}</span>
          </div>
          {kept.length ? (
            <>
              <ul className={css.grid} aria-label={w('screens')}>{kept.slice(0, open ? kept.length : first).map((s) => <Card key={s.id} screen={s} checked={checked} />)}</ul>
              {kept.length > first && (
                <div className={css.more}><Button variant="ghost" onPress={() => setOpen(!open)} aria-expanded={open}>{open ? t('showLess') : t('showAllN', { n: kept.length })}</Button></div>
              )}
            </>
          ) : <Panel><StateMessage title={w('none')} /></Panel>}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- the gallery of the pictured pages

function useKindWord() {
  const w = useScreenWords()
  return (kind?: string | null) => (kind && `kind_${kind}` in SCREEN_WORDS ? w(`kind_${kind}` as ScreenWord) : null)
}

function viewportWord(w: ReturnType<typeof useScreenWords>, picture: Picture): string {
  const name = picture.viewport ?? ''
  if (name === 'phone' || name === 'tablet' || name === 'desktop') return w(`vp_${name}`)
  return picture.width ? w('width', { w: picture.width }) : name
}

/** One picture with its findings drawn over it as numbered boxes (regions are fractions of the picture, so the boxes
 * hold at any size). `large` draws it whole; otherwise in a frame that scrolls, loaded only when near the screen. */
function Marked({ picture, list, picked, onPick, onOpen, large }:
  { picture: Picture; list: (PageFinding & { n: number })[]; picked?: number; onPick: (n: number) => void; onOpen?: () => void; large?: boolean }) {
  const w = useScreenWords()
  const [broken, setBroken] = useState(false)
  if (broken) {
    return (
      <div className={css.noShot}>
        <span className={css.noShotFrame} aria-hidden="true"><Icon name="eye" size={20} /></span>
        <div><p className={css.noShotTitle}>{w('shotUnreadable')}</p><p className={css.noShotSub}>{w('shotUnreadableSub')}</p></div>
      </div>
    )
  }
  return (
    <div className={large ? css.markedLarge : css.marked} dir="ltr">
      <div className={css.markedCanvas}>
        <TokenImage className={css.shot} path={picture.path} alt={w('shotAlt', { r: picture.path, w: picture.width ?? '' })}
          loading={large ? 'eager' : 'lazy'} decoding="async" onError={() => setBroken(true)}
          onClick={onOpen} style={onOpen ? { cursor: 'zoom-in' } : undefined} />
        {list.filter((f) => f.region).map((f) => (
          <button key={f.n} type="button" data-mark={f.n} className={[css.box, picked === f.n && css.pinOn].filter(Boolean).join(' ')}
            style={{ insetInlineStart: `${f.region!.x * 100}%`, insetBlockStart: `${f.region!.y * 100}%`,
              inlineSize: `${Math.max(f.region!.width * 100, 2)}%`, blockSize: `${Math.max(f.region!.height * 100, 1)}%` }}
            aria-label={w('pinAria', { n: f.n, s: f.title ?? w('problemHere') })} title={w('problemHere')} onClick={() => onPick(f.n)}>
            <span className={css.pinN}>{f.n}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/** The findings beside their picture, numbered as the boxes, in plain words. */
function Notes({ picture, list, picked, onPick }: { picture: Picture; list: (PageFinding & { n: number })[]; picked?: number; onPick: (n: number) => void }) {
  const w = useScreenWords()
  const kindWord = useKindWord()
  return (
    <div className={css.notes}>
      <ol className={css.noteList}>
        {list.map((f) => (
          <li key={f.n}>
            <button type="button" className={[css.note, picked === f.n && css.issueOn].filter(Boolean).join(' ')} onClick={() => onPick(f.n)} aria-pressed={picked === f.n}>
              <span className={css.issueN}>{f.n}</span>
              <span className={css.issueMain}>
                <span className={css.issueTitle}><Txt>{f.title ?? w('problemHere')}</Txt></span>
                <span className={css.issueSub}>
                  {f.severity && `sev_${f.severity}` in SCREEN_WORDS ? w(`sev_${f.severity}` as ScreenWord) : null}
                  {kindWord(f.kind) ? <> · {kindWord(f.kind)}</> : null}
                  {!f.region ? <> · {w('noRegion')}</> : null}
                </span>
                {f.why && <span className={css.noteWhy}><Txt block>{f.why}</Txt></span>}
              </span>
            </button>
          </li>
        ))}
      </ol>
      {picture.checks.length > 0 && (
        <details className={css.checks}>
          <summary>{w('pageChecks', { n: picture.checks.length })}</summary>
          <ul>{picture.checks.map((c, i) => <li key={i}><Id value={c} /></li>)}</ul>
        </details>
      )}
    </div>
  )
}

/** One page with findings: its pictures that carry them (phone, tablet, desktop as tabs), the problems marked on the
 * picture and explained beside it; the picture opens large. */
function PageCard({ page }: { page: PicturedPage }) {
  const w = useScreenWords()
  const pictures = useMemo(() => [...page.pictures].sort((a, b) => (a.width ?? 0) - (b.width ?? 0)), [page])
  const [at, setAt] = useState(0)
  const [picked, setPicked] = useState<number>()
  const [large, setLarge] = useState(false)
  const frame = useRef<HTMLDivElement>(null)
  const picture = pictures[Math.min(at, pictures.length - 1)]
  const list = useMemo(() => marks(picture), [picture])
  const pick = (n: number) => {
    setPicked(n)
    frame.current?.querySelector(`[data-mark="${n}"]`)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
  }
  const found = picture.findings.length
  return (
    <article className={css.pageCard} aria-label={page.path}>
      <header className={css.pageHead}>
        <h2 className={css.pageTitle}><Id value={page.path} /></h2>
        <span className={css.badgeIssues}>{w('issuesN', { n: page.findings })}</span>
        {page.same_as.length > 0 && <span className={css.cardRoute}>{w('sameAs', { n: page.same_as.length })}</span>}
      </header>
      {pictures.length > 1 && (
        <Segmented<string> label={w('viewport')} value={String(at)} onChange={(v) => { setAt(Number(v)); setPicked(undefined) }}
          options={pictures.map((p, i) => ({ id: String(i), label: `${viewportWord(w, p)} (${p.findings.length})` }))} />
      )}
      <div className={css.pageBody}>
        <div ref={frame} className={css.pageFrame}>
          <Marked key={picture.path} picture={picture} list={list} picked={picked} onPick={pick} onOpen={() => setLarge(true)} />
          <Button variant="ghost" icon="eye" onPress={() => setLarge(true)}>{w('openLarge')}</Button>
        </div>
        <Notes picture={picture} list={list} picked={picked} onPick={pick} />
      </div>
      <Sheet isOpen={large} onOpenChange={setLarge} title={`${page.path} · ${viewportWord(w, picture)} · ${w('issuesN', { n: found })}`}>
        <div className={css.largeBody}>
          <Marked picture={picture} list={list} picked={picked} onPick={setPicked} large />
          <Notes picture={picture} list={list} picked={picked} onPick={setPicked} />
        </div>
      </Sheet>
    </article>
  )
}

/** A one-line summary of pages that are not pictured here (clean, or not reviewed), their addresses folded away. */
function PagesLine({ pages, words }: { pages: PicturedPage[]; words: string }) {
  const w = useScreenWords()
  if (!pages.length) return null
  return (
    <details className={css.pagesLine}>
      <summary><span>{words}</span> <span className={css.cardRoute}>{w('showAddresses')}</span></summary>
      <ul className={css.addresses}>{pages.map((p) => <li key={p.path}><Id value={p.path} /></li>)}</ul>
    </details>
  )
}

/** The Screens page when the check pictured the app: only the pages with problems, most severe first, each problem
 * marked on its picture; the clean and the unreviewed pages in one line each. */
function PicturedGallery({ data, sx }: { data: StudioData; sx: ScreensData }) {
  const w = useScreenWords()
  const { t } = usePrefs()
  const pages = sx.pages ?? []
  const { shown, clean, notReviewed } = useMemo(() => gallery(pages), [pages])
  const [all, setAll] = useState(false)
  const first = 12
  return (
    <div className={layout.page}>
      <Heading data={data} pictured={{ total: pages.length, found: shown.length }} />
      <div className={css.summary}>
        <PagesLine pages={clean} words={w('cleanLine', { n: clean.length })} />
        <PagesLine pages={notReviewed} words={w('notReviewedLine', { n: notReviewed.length })} />
      </div>
      {shown.length ? (
        <>
          <div className={css.pages}>{shown.slice(0, all ? shown.length : first).map((page) => <PageCard key={page.path} page={page} />)}</div>
          {shown.length > first && (
            <div className={css.more}><Button variant="ghost" onPress={() => setAll(!all)} aria-expanded={all}>{all ? t('showLess') : t('showAllN', { n: shown.length })}</Button></div>
          )}
        </>
      ) : !notReviewed.length ? <Panel><StateMessage icon="eye" title={w('galleryNone')} /></Panel> : null}
      {sx.screens.length > 0 && (
        <div className={css.links}><Go to="/screens" search={{ every: '1' }} className={css.inlineLink}>{w('everyScreen', { n: sx.screens.length })}</Go></div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- one screen

function Pins({ list, onPick, picked }: { list: (Issue & { n: number })[]; onPick: (id: string) => void; picked?: string }) {
  const w = useScreenWords()
  return (
    <>
      {list.map((p) => (
        <button key={p.id} type="button" className={[css.pin, picked === p.id && css.pinOn].filter(Boolean).join(' ')}
          style={{ insetInlineStart: `${p.box!.x}px`, insetBlockStart: `${p.box!.y}px`, inlineSize: `${Math.max(p.box!.w, 24)}px`, blockSize: `${Math.max(p.box!.h, 24)}px` }}
          aria-label={w('pinAria', { n: p.n, s: p.summary })} onClick={() => onPick(p.id)}>
          <span className={css.pinN}>{p.n}</span>
        </button>
      ))}
    </>
  )
}

function Viewer({ screen }: { screen: Screen }) {
  const w = useScreenWords()
  const search = useSearch({ strict: false }) as Search
  const navigate = useNavigate()
  const sizes = widths(screen)
  const vp = sizes.includes(Number(search.vp)) ? Number(search.vp) : sizes[0]
  const at = shotsAt(screen, vp)
  const pair = Boolean(at.before && at.after)
  const mode = pair && (search.compare === 'before' || search.compare === 'after' || search.compare === 'slider') ? search.compare : pair ? 'slider' : 'one'
  const [cut, setCut] = useState(50)
  const [picked, setPicked] = useState<string>()
  const [failed, setFailed] = useState<string[]>([])
  const set = (patch: Search) => navigate({ to: '.', replace: true, search: (prev: Search) => ({ ...prev, ...patch }) })
  const list = pins(screen, vp)
  const img = (shot: Shot, extra?: string) => (
    <TokenImage className={[css.shot, extra].filter(Boolean).join(' ')} path={shot.path} width={shot.width} alt={w('shotAlt', { r: screen.route, w: shot.width })} onError={() => setFailed((f) => [...f, shot.path])} />
  )
  const shown = mode === 'before' ? at.before : mode === 'after' ? at.after : at.one
  const broken = (mode === 'slider' ? [at.before, at.after] : [shown]).some((shot) => shot && failed.includes(shot.path))
  return (
    <div className={css.viewer}>
      <div className={css.viewerBar}>
        {sizes.length > 1 && (
          <Segmented<string> label={w('viewport')} value={String(vp)} onChange={(v) => set({ vp: v })}
            options={sizes.map((s) => ({ id: String(s), label: s < 768 ? w('phone', { w: s }) : w('desktop', { w: s }) }))} />
        )}
        {pair && (
          <Segmented<string> label={w('compare')} value={mode} onChange={(v) => set({ compare: v })}
            options={[{ id: 'before', label: w('before') }, { id: 'slider', label: w('slider') }, { id: 'after', label: w('after') }]} />
        )}
      </div>
      {broken ? (
        <Panel>
          <div className={css.noShot}>
            <span className={css.noShotFrame} aria-hidden="true"><Icon name="eye" size={20} /></span>
            <div>
              <p className={css.noShotTitle}>{w('shotUnreadable')}</p>
              <p className={css.noShotSub}>{w('shotUnreadableSub')}</p>
            </div>
          </div>
        </Panel>
      ) : <div className={css.stage} dir="ltr">
        <div className={css.canvas} style={{ inlineSize: `${vp}px` }}>
          {mode === 'slider' && at.before && at.after ? (
            <div className={css.compare}>
              {img(at.after)}
              <div className={css.beforeClip} style={{ clipPath: `inset(0 ${100 - cut}% 0 0)` }}>{img(at.before)}</div>
            </div>
          ) : shown ? img(shown) : null}
          <Pins list={list} onPick={setPicked} picked={picked} />
        </div>
      </div>}
      {mode === 'slider' && !broken && (
        <input type="range" className={css.range} min={0} max={100} value={cut} onChange={(e) => setCut(Number(e.target.value))} aria-label={w('sliderAria')} />
      )}
      <IssueList screen={screen} numbered={list} picked={picked} />
    </div>
  )
}

function IssueList({ screen, numbered, picked }: { screen: Screen; numbered: (Issue & { n: number })[]; picked?: string }) {
  const w = useScreenWords()
  const number = new Map(numbered.map((p) => [p.id, p.n]))
  return (
    <Section title={w('issues')} count={screen.issues.length}>
      <Panel>
        {screen.issues.length ? (
          <ul>{screen.issues.map((i) => (
            <li key={i.id} className={[css.issue, picked === i.id && css.issueOn].filter(Boolean).join(' ')}>
              {number.has(i.id) && <span className={css.issueN}>{number.get(i.id)}</span>}
              <span className={css.issueMain}>
                <span className={css.issueTitle}><Txt>{i.summary}</Txt></span>
                <span className={css.issueSub}>{w(`sev_${i.severity}`)} · <Id value={i.rule} />{i.element ? <> · <Id value={i.element} /></> : null} · {i.state === 'open' ? w('open') : w('fixed')}</span>
              </span>
              {i.card && <Go to="/problems" search={{ card: i.card }} className={css.inlineLink}>{w('openProblem')}</Go>}
            </li>
          ))}</ul>
        ) : <p className={css.empty}>{w('issuesNone')}</p>}
      </Panel>
    </Section>
  )
}

function ScreenDetail({ data, sx, id }: { data: StudioData; sx: ScreensData; id: string }) {
  const w = useScreenWords()
  const { lang } = usePrefs()
  const fx = useLazySection<FunctionsData>(data, 'functions')
  const screen = sx.screens.find((s) => s.id === id)
  if (!screen) {
    return (
      <div className={layout.page}>
        <Panel><StateMessage title={w('notFound')} sub={w('notFoundSub')} action={<div><Go to="/screens" className={css.inlineLink}>{w('backToList')}</Go></div>} /></Panel>
      </div>
    )
  }
  const inFile = fx.kind === 'ready' && screen.file ? fx.data.functions.filter((f) => f.module === screen.file).length : 0
  const issuesChecked = measured(sx, 'issues')
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <div className={layout.titleBlock}>
        <span className={css.kicker}>{w('screens')}</span>
        <h1 className={layout.largeTitle}><Txt>{screen.title}</Txt></h1>
        <p className={css.routeLine}><Id value={screen.route} /></p>
        {(screen.flags ?? []).length > 0 && <div className={css.flags}>{screen.flags!.map((f) => <Chip key={f} tone="warning">{w(`flag_${f}`)}</Chip>)}</div>}
      </div>
      <div className={css.links}>
        <Go to="/system/journeys" search={{ focus: screen.id }} className={css.inlineLink}>{w('inJourneys')}</Go>
        {inFile > 0 && screen.file && <Go to="/system/functions" search={{ module: screen.file }} className={css.inlineLink}><span>{w('fileFunctions')} (<N value={inFile} />)</span></Go>}
      </div>
      {screen.shots.length ? <Viewer key={screen.id} screen={screen} /> : (
        <>
          <Panel>
            <div className={css.noShot}>
              <span className={css.noShotFrame} aria-hidden="true"><Icon name="eye" size={20} /></span>
              <div>
                <p className={css.noShotTitle}>{w('shotMissing')}</p>
                {(sx.missing ?? []).filter((g) => g.id === 'shots').map((g) => <p key={g.id} className={css.noShotSub}><Txt>{g.detail[lang]}</Txt></p>)}
              </div>
            </div>
          </Panel>
          <Section title={w('issues')}>
            <Panel><p className={css.empty}>{issuesChecked ? w('issuesNone') : w('issuesNotChecked')}</p></Panel>
          </Section>
        </>
      )}
      <Section title={w('inputs')} count={measured(sx, 'inputs') ? screen.inputs.length : undefined}>
        <Panel>
          {!measured(sx, 'inputs') ? <p className={css.empty}>{w('inputsNotMeasured')}</p>
            : screen.inputs.length ? (
              <ul>{screen.inputs.map((i) => (
                <li key={i.id} className={css.issue}>
                  <span className={css.issueMain}>
                    <span className={css.issueTitle}>{i.label ? <Txt>{i.label}</Txt> : <Id value={i.id} />}</span>
                    <span className={css.issueSub}><Id value={i.kind} /> · {i.labelled ? w('labelled') : w('unlabelled')}{i.required ? <> · {w('required')}</> : null}{i.validated ? <> · {w('validated')}</> : null}</span>
                  </span>
                </li>
              ))}</ul>
            ) : <p className={css.empty}>{w('inputsNone')}</p>}
        </Panel>
      </Section>
      <Section title={w('file')}>
        <Panel pad>
          <dl className={css.props}>
            <div><dt>{w('route')}</dt><dd><Id value={screen.route} /></dd></div>
            {screen.file && <div><dt>{w('file')}</dt><dd><Id value={screen.file} /></dd></div>}
            {screen.router && <div><dt>{w('declared')}</dt><dd><Id value={screen.router + (screen.line ? `:${screen.line}` : '')} /></dd></div>}
            {screen.component && <div><dt>{w('component')}</dt><dd><Go to="/system" search={{ focus: screen.component }} className={css.inlineLink}><Id value={screen.component} /></Go></dd></div>}
          </dl>
        </Panel>
      </Section>
    </div>
  )
}

function Body({ data, id }: { data: StudioData; id?: string }) {
  const w = useScreenWords()
  const { t } = usePrefs()
  const slot = useLazySection<ScreensData>(data, 'screens')
  const sx = slot.kind === 'ready' ? slot.data : undefined
  const screen = id && sx ? sx.screens.find((s) => s.id === id) : undefined
  usePageChrome(screen ? screen.title : w('screens'), id ? { to: '/screens', label: w('backToList') } : undefined, data.manifest.project.name)
  if (slot.kind === 'loading') return <div className={layout.page}><Heading data={data} /><Panel><Skeleton label={t('loading')} /></Panel></div>
  if (!sx) return <NotExported data={data} />
  return id ? <ScreenDetail data={data} sx={sx} id={id} /> : <Gallery data={data} sx={sx} />
}

/** The report has no screens section: its coverage row says why and which step writes it. */
function NotExported({ data }: { data: StudioData }) {
  const w = useScreenWords()
  const row = useCoverageRow(data, 'screens')
  return (
    <div className={layout.page}>
      <Heading data={data} />
      <Panel><StateMessage icon="eye" title={w('notCaptured')} sub={<>{row ? <Txt>{row.detail}</Txt> : w('notCapturedSub')}</>} /></Panel>
    </div>
  )
}

export function ScreensPage() {
  return <WithData>{(data) => <Body data={data} />}</WithData>
}

export function ScreenPage() {
  const { screenId } = useParams({ strict: false }) as { screenId?: string }
  return <WithData>{(data) => <Body data={data} id={screenId} />}</WithData>
}
