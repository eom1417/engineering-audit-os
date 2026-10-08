// Decisions: every question waiting for the person, one card each (Calm), then the answered ones.
import { Panel, StateMessage } from '../components/Panel'
import { DecisionCard } from '../components/Story'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { usePageChrome } from '../shell/chrome'
import { layout, MissingBanner, PageTitle, WithData } from '../shell/Layout'
import css from './Pages.module.css'

function DecisionsBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  usePageChrome(t('decisions'), undefined, data.manifest.project.name)
  const all = data.decisions?.decisions ?? []
  const ordered = [...all.filter((d) => d.state === 'waiting'), ...all.filter((d) => d.state !== 'waiting')]
  return (
    <div className={layout.page}>
      <MissingBanner data={data} />
      <PageTitle title={t('waitingForYou')} />
      {ordered.length === 0
        ? <Panel><StateMessage icon="inbox" title={t('nothingWaits')} sub={t('nothingWaitsSub')} /></Panel>
        : <div className={css.cards}>{ordered.map((d) => (
          <DecisionCard key={d.id} decision={d} cardsTo={d.blocks.every((b) => b.startsWith('TASK-')) ? { to: '/problems', search: { who: 'you' } } : undefined} />
        ))}</div>}
    </div>
  )
}

export function DecisionsPage() {
  return <WithData>{(data) => <DecisionsBody data={data} />}</WithData>
}
