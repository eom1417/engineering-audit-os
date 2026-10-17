import { describe, expect, it } from 'vitest'
import { checkInputs, freshOf, toggled } from './CheckOptions'

describe('the choice of a check', () => {
  it('keeps the complete check alone and falls back to it when nothing is chosen', () => {
    expect(toggled(['complete'], 'security')).toEqual(['security'])
    expect(toggled(['security'], 'look')).toEqual(['security', 'look'])
    expect(toggled(['security', 'look'], 'complete')).toEqual(['complete'])
    expect(toggled(['security'], 'security')).toEqual(['complete'])
  })
  it('sends no paths for the complete check, and the mode always', () => {
    expect(checkInputs({ paths: ['complete'], mode: 'speed' })).toEqual({ mode: 'speed' })
    expect(checkInputs({ paths: ['security'], mode: 'normal' })).toEqual({ mode: 'normal', paths: ['security'] })
  })
  it('leaves the AI out of this one check only when it is turned off', () => {
    expect(checkInputs({ paths: ['complete'], mode: 'normal', ai: false })).toEqual({ mode: 'normal', without_ai: true })
    expect(checkInputs({ paths: ['complete'], mode: 'normal', ai: true })).toEqual({ mode: 'normal' })
  })
  it('makes every check pressed a new one, unless it goes on from a stage', () => {
    // Home's next step and the palette ask for the check with no inputs: EAOS then answered "already checked"
    expect(freshOf({ action: 'audit' }, {})).toEqual({ fresh: true })
    expect(freshOf({ action: 'audit', inputs: { again_from: 'facts' } }, {})).toEqual({})
    expect(freshOf({ action: 'audit' }, { again_from: 'facts' })).toEqual({})
    expect(freshOf({ action: 'fix_start' }, {})).toEqual({})
  })
})
