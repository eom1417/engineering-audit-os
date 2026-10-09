// What floats over every page: the action bar while something is selected, the question toast when a run needs the
// person, and otherwise a small pill back to the run that holds the slot. Only one shows at a time, in that order,
// and the page keeps room for it at its end (html[data-dock]) so it never covers the last row.
import { useRouterState } from '@tanstack/react-router'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Go } from '../components/Go'
import { STATE_WORDS } from '../data/actions/contract'
import { labelOf } from '../data/actions/derive'
import { useActions } from '../data/actions/store'
import { usePrefs } from '../i18n/prefs'
import { Txt } from '../i18n/text'
import { ActionBar } from './ActionBar'
import { useCommand } from './command'
import { useLoaded } from '../data/context'
import { useOpenedOnce, whenIdle } from '../shell/later'
import { QuestionToast } from './Questions'
import css from './command.module.css'

// The selection and preview sheets are their own chunks (shell/later.ts): read once the report is drawn, drawn from
// their first opening
const loadGroupSheet = () => import('./GroupSheet')
const loadPreviewSheet = () => import('./PreviewSheet')
const GroupSheet = lazy(() => loadGroupSheet().then((module) => ({ default: module.GroupSheet })))
const PreviewSheet = lazy(() => loadPreviewSheet().then((module) => ({ default: module.PreviewSheet })))

const DISMISSED = 'eaos.dismissed-questions'

function dismissedAtStart(): string[] {
  try { return JSON.parse(sessionStorage.getItem(DISMISSED) || '[]') } catch { return [] }
}

export function CommandHost() {
  const command = useCommand()
  const actions = useActions()
  const { lang } = usePrefs()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const [dismissed, setDismissed] = useState<string[]>(dismissedAtStart)
  const onRun = (id: string) => pathname === `/runs/${id}` || pathname === `/runs/${encodeURIComponent(id)}`
  const question = actions.questions.find((q) => !dismissed.includes(q.id) && !onRun(q.run))
  const runOf = (id: string) => actions.runs.find((run) => run.id === id)
  const selecting = command.sel.ids.length > 0
  const toast = !selecting && question && pathname !== '/decisions' ? question : null
  const pill = !selecting && !toast && actions.active && !onRun(actions.active.id) && pathname !== '/runs' ? actions.active : null
  const dock = selecting ? 'bar' : toast ? 'toast' : pill ? 'pill' : ''
  const ready = useLoaded().kind === 'ready'
  useEffect(() => (ready ? whenIdle(() => { void loadGroupSheet(); void loadPreviewSheet() }) : undefined), [ready])
  const groupsOpened = useOpenedOnce(command.groupsOpen)
  const previewOpened = useOpenedOnce(command.request !== null)

  useEffect(() => {
    const root = document.documentElement
    if (dock) root.dataset.dock = dock
    else delete root.dataset.dock
  }, [dock])

  const dismiss = (id: string) => {
    const next = [...dismissed, id]
    setDismissed(next)
    try { sessionStorage.setItem(DISMISSED, JSON.stringify(next)) } catch { /* this visit only */ }
  }

  return (
    <>
      <ActionBar />
      {groupsOpened && <Suspense fallback={null}><GroupSheet /></Suspense>}
      {previewOpened && <Suspense fallback={null}><PreviewSheet /></Suspense>}
      {toast && <QuestionToast key={toast.id} question={toast} runLabel={(() => { const run = runOf(toast.run); return run ? labelOf(run.label, lang) : '' })()} onDismiss={() => dismiss(toast.id)} />}
      {pill && (
        <div className={css.pillDock}>
          <Go to={`/runs/${encodeURIComponent(pill.id)}`} className={css.pill} label={`${STATE_WORDS[pill.state][lang]}: ${labelOf(pill.label, lang)}`}>
            <span className={css.pillDot} data-state={pill.state} aria-hidden="true" />
            <span className={css.pillState}>{STATE_WORDS[pill.state][lang]}</span>
            <span className={css.pillLabel} data-truncate title={labelOf(pill.label, lang)}><Txt>{labelOf(pill.label, lang)}</Txt></span>
          </Go>
        </div>
      )}
    </>
  )
}
