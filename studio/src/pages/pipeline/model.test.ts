import { describe, expect, it } from 'vitest'
import fixture from './fixture.json'
import { dataNames, firstPipeline, follow, geometry, ordered, scopeOf, trail, type PipelineData } from './model'

const DATA = fixture as unknown as PipelineData
const STAGES = DATA.pipelines.find((p) => DATA.stages.some((s) => s.pipeline === p.id && s.label === 'claims'))!.id

describe('the pipeline map reads pipeline.json and computes no place of its own', () => {
  it('shows a top product pipeline first, and the trail of a pipeline ends at itself', () => {
    const first = DATA.pipelines.find((p) => p.id === firstPipeline(DATA))!
    expect(first.role).toBe('product')
    expect(first.parent).toBeNull()
    for (const p of DATA.pipelines) expect(trail(DATA, p.id).at(-1)!.id).toBe(p.id)
  })

  it('keeps every element of one pipeline and nothing of another', () => {
    for (const p of DATA.pipelines) {
      const scope = scopeOf(DATA, p.id)!
      expect(scope.stages.every((s) => s.pipeline === p.id)).toBe(true)
      // an edge either stays inside, or comes in from the stage the pipeline runs inside
      expect(scope.edges.every((e) => (scope.stage.has(e.from) || e.from === p.parent) && scope.stage.has(e.to))).toBe(true)
      expect(scope.added.every((s) => !scope.stage.has(s.id))).toBe(true)
    }
    expect(scopeOf(DATA, 'nowhere')).toBeNull()
  })

  it('places each stage by the layer and order EAOS wrote, the same in both directions', () => {
    const scope = scopeOf(DATA, STAGES)!
    const across = geometry(scope.stages, scope.errors, false)
    const down = geometry(scope.stages, scope.errors, true)
    for (const s of scope.stages) {
      for (const o of scope.stages) {
        expect(across.at.get(o.id)!.x === across.at.get(s.id)!.x).toBe(o.layer === s.layer)
        expect(down.at.get(o.id)!.y === down.at.get(s.id)!.y).toBe(o.layer === s.layer)
      }
    }
    expect([...across.ends.keys()]).toEqual([...new Set(scope.errors.map((e) => e.to))])
  })

  it('follows the data only along the edges the data holds', () => {
    const scope = scopeOf(DATA, STAGES)!
    const name = dataNames(scope).find((n) => scope.stages.some((s) => s.outputs.some((o) => o.name === n)))!
    const lit = follow(scope, name)
    const writers = scope.stages.filter((s) => s.outputs.some((o) => o.name === name))
    for (const w of writers) expect(lit.stages.has(w.id)).toBe(true)
    for (const id of lit.edges) {
      const e = scope.edges.find((x) => x.id === id)!
      expect(lit.stages.has(e.from) && lit.stages.has(e.to)).toBe(true)
    }
    for (const id of lit.stages) if (!writers.some((w) => w.id === id)) expect(scope.edges.some((e) => lit.edges.has(e.id) && e.to === id)).toBe(true)
  })

  it('reads the stages in layer order for the steps view', () => {
    const rows = ordered(scopeOf(DATA, STAGES)!.stages)
    for (let i = 1; i < rows.length; i++) expect(rows[i - 1].layer <= rows[i].layer).toBe(true)
  })
})
