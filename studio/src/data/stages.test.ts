import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { describe, expect, it } from 'vitest'
import { withSections } from './load'
import { CARD_NEEDS, GROUP_NEEDS, HOME_NEEDS, PROBLEMS_NEEDS, SHELL_NEEDS } from './stages'
import { SECTIONS, type StudioData } from './types'

/** boot.js's FIRST table, read from the shipped boot script itself. */
function bootFirst(): Record<string, string[]> {
  const boot = fs.readFileSync(path.resolve(__dirname, '../../public/boot.js'), 'utf8')
  const table = /(var shell = \[[^\]]*\];\s*var FIRST = \{[\s\S]*?\};)/.exec(boot)
  if (!table) throw new Error('boot.js has no FIRST table')
  const scope: { FIRST?: Record<string, string[]> } = {}
  vm.runInNewContext(`${table[1]} this.FIRST = FIRST`, scope)
  return scope.FIRST!
}

describe('the sections a page reads first', () => {
  it('boot.js reads first exactly the sections Home, Problems and a card detail wait for', () => {
    const first = bootFirst()
    expect(new Set(first['/'])).toEqual(new Set(HOME_NEEDS))
    expect(new Set(first['/problems'])).toEqual(new Set(PROBLEMS_NEEDS))
    expect(new Set(first['/problems?card'])).toEqual(new Set(CARD_NEEDS))
    expect(Object.keys(first).sort()).toEqual(['/', '/problems', '/problems?card'])
  })

  it('names only report sections, and the frame and selection sheet need nothing a first page lacks', () => {
    for (const list of [SHELL_NEEDS, HOME_NEEDS, PROBLEMS_NEEDS, CARD_NEEDS, GROUP_NEEDS]) {
      for (const name of list) expect(SECTIONS).toContain(name)
    }
    for (const page of [HOME_NEEDS, PROBLEMS_NEEDS]) for (const name of SHELL_NEEDS) expect(page).toContain(name)
  })

  it('moves a section from pending into the report, or into missing when its file did not load', () => {
    const data = { manifest: {}, missing: ['docs'], pending: ['paths', 'evidence', 'gaps'] } as unknown as StudioData
    const next = withSections(data, ['paths', 'evidence'], { paths: { paths: [] } })
    expect(next.pending).toEqual(['gaps'])
    expect(next.missing).toEqual(['docs', 'evidence'])
    expect((next as unknown as Record<string, unknown>).paths).toEqual({ paths: [] })
    expect(data.pending).toEqual(['paths', 'evidence', 'gaps'])
    expect(data.missing).toEqual(['docs'])
  })
})
