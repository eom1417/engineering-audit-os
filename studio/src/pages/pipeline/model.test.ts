import { describe, expect, it } from 'vitest'
import fixture from './fixture.json'
import { dataNames, firstPipeline, follow, geometry, ordered, scopeOf, trail, type PipelineData } from './model'

const DATA = fixture as unknown as PipelineData

describe('the pipeline map reads pipeline.json and computes no place of its own', () => {
  it('shows the top product pipeline first and nests the sub-pipeline under its stage', () => {
    expect(firstPipeline(DATA)).toBe('main')
    expect(trail(DATA, 'facts').map((p) => p.id)).toEqual(['main', 'facts'])
  })

  it('keeps every element of one pipeline and nothing of another', () => {
    const scope = scopeOf(DATA, 'facts')!
    expect(scope.stages.every((s) => s.pipeline === 'facts')).toBe(true)
    // an edge either stays inside, or comes in from the stage the pipeline runs inside
    expect(scope.edges.every((e) => (scope.stage.has(e.from) || e.from === scope.pipeline.parent) && scope.stage.has(e.to))).toBe(true)
    expect(scope.unresolved.length).toBe(1)
    expect(scopeOf(DATA, 'nowhere')).toBeNull()
  })

  it('places each stage by the layer and order EAOS wrote, the same in every view and both directions', () => {
    const scope = scopeOf(DATA, 'main')!
    const across = geometry(scope.stages, scope.errors, false)
    const down = geometry(scope.stages, scope.errors, true)
    for (const s of scope.stages) {
      const same = scope.stages.filter((o) => o.layer === s.layer)
      for (const o of same) expect(across.at.get(o.id)!.x).toBe(across.at.get(s.id)!.x)
      expect(down.at.get(s.id)!.y).toBe(down.at.get(scope.stages.find((o) => o.layer === s.layer)!.id)!.y)
    }
    expect([...across.ends.keys()]).toEqual([...new Set(scope.errors.map((e) => e.to))])
  })

  it('follows the data only along the edges the data holds', () => {
    const scope = scopeOf(DATA, 'main')!
    const lit = follow(scope, 'features.json')
    expect(lit.stages.has('main:features')).toBe(true)
    expect(lit.stages.has('main:lock')).toBe(true)
    expect(lit.stages.has('main:facts')).toBe(false)
    for (const id of lit.edges) {
      const e = scope.edges.find((x) => x.id === id)!
      expect(lit.stages.has(e.from) && lit.stages.has(e.to)).toBe(true)
    }
    expect(dataNames(scope)).toContain('facts/index.json')
  })

  it('reads the stages in layer order for the steps view', () => {
    const rows = ordered(scopeOf(DATA, 'main')!.stages)
    for (let i = 1; i < rows.length; i++) expect(rows[i - 1].layer <= rows[i].layer).toBe(true)
  })
})
