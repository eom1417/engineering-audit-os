// The small parts every view of a branch shows (#/branches): its badges, how it compares with the base, its worktree,
// its runs, a commit subject, and the reasons a command is blocked.
import { Chip, type Tone } from '../../components/Chip'
import { Go } from '../../components/Go'
import type { BranchRow, Reason, RunLink } from '../../data/actions/types'
import { labelOf } from '../../data/actions/derive'
import { STATE_WORDS } from '../../data/actions/contract'
import { usePrefs } from '../../i18n/prefs'
import { latestRun } from '../../branches/model'
import { useBranchWords } from '../../branches/words'
import css from '../../branches/branches.module.css'

export function Reasons({ reasons }: { reasons: Reason[] }) {
  const { lang } = usePrefs()
  const w = useBranchWords()
  if (!reasons.length) return null
  return (
    <div className={css.blocked} data-blocked={reasons.map((r) => r.code).join(' ')}>
      <span>{w('blockedBecause')}</span>
      <ul>{reasons.map((r) => <li key={r.code + r.en}>{r[lang]}</li>)}</ul>
    </div>
  )
}

export function Badges({ row }: { row: BranchRow }) {
  const w = useBranchWords()
  // the exceptions only: a branch is the person's own unless EAOS made it, and its group already says where it lives
  const owner: [Tone, string] | null = row.ownership.owner === 'eaos' ? ['accent', w('ownerEaos')] : row.ownership.owner === 'shared' ? ['warning', w('ownerShared')] : null
  return (
    <span className={css.badges}>
      {row.kind === 'remote' && row.remote !== 'origin' && <Chip dot={false}>{w('remote', { r: row.remote ?? '' })}</Chip>}
      {row.roles.includes('checkout') && <Chip tone="good">{w('checkout')}</Chip>}
      {row.roles.includes('analysis') && !row.roles.includes('checkout') && <Chip tone="accent">{w('analysis')}</Chip>}
      {row.roles.includes('default') && <Chip>{w('defaultBranch')}</Chip>}
      {row.protected && <Chip tone="warning">{w('protected')}</Chip>}
      {owner && <Chip tone={owner[0]}>{owner[1]}</Chip>}
    </span>
  )
}

export function Compare({ row }: { row: BranchRow }) {
  const w = useBranchWords()
  const c = row.compare
  if (c.ahead === null || c.behind === null) return <span className={css.muted}>{w('compareUnknown')}</span>
  if (c.merged && c.base && c.base !== row.name) return <span>{w('merged', { b: c.base })} · {w('aheadBehind', { a: c.ahead, b: c.behind })}</span>
  return <span>{w('aheadBehind', { a: c.ahead, b: c.behind })}</span>
}

export function WorktreeNote({ row }: { row: BranchRow }) {
  const w = useBranchWords()
  if (!row.worktree) return null
  const dirty = row.worktree.dirty ? row.worktree.dirty.tracked + row.worktree.dirty.untracked : 0
  return <span className={css.muted}>{row.worktree.current ? w('worktreeHere') : w('worktreeOther', { p: row.worktree.path })}{dirty ? ` · ${w('unsaved', { n: dirty })}` : ''}</span>
}

export function RunLinks({ runs, all = false }: { runs: RunLink[]; all?: boolean }) {
  const { lang } = usePrefs()
  const w = useBranchWords()
  if (!runs.length) return null
  const { run, more } = latestRun(runs)
  const link = (r: RunLink) => <li key={r.id + r.role}><Go to={`/runs/${encodeURIComponent(r.id)}`} className={css.inlineLink}>{labelOf(r.label, lang)}</Go> <span className={css.muted}>· {STATE_WORDS[r.state]?.[lang] ?? r.state}</span></li>
  if (all) return <ul className={css.runLinks}>{runs.slice(0, 20).map(link)}</ul>
  return (
    <ul className={css.runLinks}>
      {run && link(run)}
      {more > 0 && <li className={css.muted}>{w('moreRuns', { n: more })}</li>}
    </ul>
  )
}

/** A commit subject: often English inside an Arabic line, so it keeps its own direction. */
export function Subject({ text }: { text: string }) {
  return text ? <bdi dir="ltr" className={css.subject}>{text}</bdi> : null
}
