import { describe, expect, it } from 'vitest'
import type { BranchRow } from '../data/actions/types'
import { latestRun, shownBranches } from './model'

const row = (name: string, kind: 'local' | 'remote', extra: Partial<BranchRow> = {}): BranchRow => ({
  id: `${kind}/${extra.remote ?? ''}/${name}`, name, kind, remote: null, ref: '', tip: 'abcdef1234', last_commit: null, subject: '', upstream: null,
  tracking: null, roles: [], protected: null, ownership: { owner: 'unknown' } as BranchRow['ownership'], work: false,
  compare: { base: null, ahead: null, behind: null, merged: null }, worktree: null, runs: [], remote_as_of: null, ...extra,
})

describe('the branches page lists', () => {
  // The incident (#/branches, 2026-10-12): the work tab showed develop, then main three times (local, origin, history-bundle)
  it('only the work branches and the branch the person works on, by default', () => {
    const rows = [
      row('develop', 'local', { roles: ['checkout', 'analysis', 'report', 'base'] }),
      row('main', 'local', { roles: ['default'], protected: { code: 'default', en: 'd', ar: 'd' } }),
      row('main', 'remote', { remote: 'origin', roles: ['default'] }),
      row('main', 'remote', { remote: 'history-bundle', roles: ['default'] }),
      row('develop', 'remote', { remote: 'origin' }),
      row('eaos/develop/wave-1', 'local', { work: true }),
      row('mobile-parity', 'local'),
    ]
    const shown = shownBranches(rows, 'work')
    expect(shown.local.map((r) => r.name)).toEqual(['develop', 'eaos/develop/wave-1'])
    expect(shown.remote.map((r) => `${r.remote}/${r.name}`)).toEqual(['origin/develop'])
    expect(shownBranches(rows, 'all').local).toHaveLength(4)
    expect(latestRun([{ id: 'a', created: '2026-10-11', state: 'done', label: { en: '', ar: '' }, action: 'audit', role: 'work' },
      { id: 'b', created: '2026-10-12', state: 'done', label: { en: '', ar: '' }, action: 'audit', role: 'work' }])).toMatchObject({ run: { id: 'b' }, more: 1 })
  })
})
