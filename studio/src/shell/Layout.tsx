// Page layouts and the page frame that shows the report's loading, empty, error and partial states the same way on
// every page.
import type { ReactNode } from 'react'
import { Icon } from '../components/Icon'
import { Panel, Skeleton, StateMessage } from '../components/Panel'
import { Button, CopyRequestButton } from '../components/Button'
import { useCommandMaybe } from '../command/command'
import { useActionsMaybe } from '../data/actions/store'
import { useLoaded, useSections } from '../data/context'
import type { SectionName, StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import css from './Layout.module.css'

export { css as layout }

/** Renders children with the loaded report, or the designed state when there is none. `needs` names the sections the
 * page reads (data/stages.ts); without it the page waits for every section of the report. `empty`: what a page still
 * shows above the empty state before the first check (the inbox: a run's question). */
export function WithData({ children, needs = 'all', empty }: { children: (data: StudioData) => ReactNode; needs?: readonly SectionName[] | 'all'; empty?: ReactNode }) {
  const loaded = useLoaded()
  const waiting = useSections(needs)
  const { t, lang } = usePrefs()
  const command = useCommandMaybe()
  const live = useActionsMaybe()?.mode === 'live' && command !== null
  if (loaded.kind === 'loading') return <div className={css.page}><Panel><Skeleton label={t('loading')} /></Panel></div>
  if (loaded.kind === 'empty') {
    const request = lang === 'ar' ? 'افحص هذا المشروع بأداة audit من EAOS، ثم افتح الاستوديو من مجلد التقرير.' : 'Check this project with the EAOS audit tool, then open the Studio from the report folder.'
    // Live, the check starts from here (its preview first); the request to copy stays as the secondary way
    return (
      <div className={css.page}>
        {empty}
        <Panel><StateMessage title={t('emptyTitle')} sub={t(live ? 'emptySubLive' : 'emptySub')} action={
          <div className={css.emptyActions}>
            {live && <Button variant="primary" icon="play" data-start-action="audit" onPress={() => command?.open({ action: 'audit', inputs: { fresh: true } })}>{t('checkNow')}</Button>}
            <CopyRequestButton request={request} tool="audit" />
          </div>} /></Panel>
      </div>
    )
  }
  if (loaded.kind === 'error') return <div className={css.page}><Panel><StateMessage kind="error" title={t('errorTitle')} sub={t('errorSub')} /></Panel></div>
  if (waiting.length) return <div className={css.page}><SectionsLoading waiting={waiting} /></div>
  return <>{children(loaded.data)}</>
}

/** A page whose own code is still being read (router.tsx: every page but Home and Problems is read when opened). */
export function PageLoading() {
  const { t } = usePrefs()
  return <div className={css.page}><Panel><Skeleton label={t('loadingPage')} /></Panel></div>
}

/** The state of a page (or a part of one) whose sections are still being read: how many parts are left. */
export function SectionsLoading({ waiting }: { waiting: readonly SectionName[] }) {
  const { t } = usePrefs()
  return (
    <Panel>
      <div role="status" aria-live="polite"><StateMessage icon="clock" title={t('loadingRest')} sub={t('loadingParts', { n: waiting.length })} /></div>
      <Skeleton label={t('loadingRest')} />
    </Panel>
  )
}

/** The note shown when some sections of the report did not load: what is shown is still correct. */
export function MissingBanner({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  if (!data.missing.length) return null
  return (
    <div className={css.banner} role="note">
      <Icon name="problems" />
      <div><strong>{t('partialTitle')}</strong> — {t('partialSub', { names: data.missing.join(', ') })}</div>
    </div>
  )
}

export function PageTitle({ title, kicker, lead }: { title: ReactNode; kicker?: boolean; lead?: ReactNode }) {
  return (
    <div className={css.titleBlock}>
      <h1 className={kicker ? css.kicker : css.largeTitle}>{title}</h1>
      {lead && <p className={css.lead}>{lead}</p>}
    </div>
  )
}
