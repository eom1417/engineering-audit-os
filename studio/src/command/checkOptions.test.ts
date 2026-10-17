import { describe, expect, it } from 'vitest'
import { checkInputs, toggled } from './CheckOptions'

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
})
