import { describe, expect, it } from 'vitest'
import { normalize, terms, tokenize } from './normalize'

describe('normalize', () => {
  it('folds every alef form to a bare alef', () => {
    expect(normalize('أحمد')).toBe(normalize('احمد'))
    expect(normalize('إصلاح')).toBe('اصلاح')
    expect(normalize('آخر')).toBe('اخر')
    expect(normalize('ٱلبنية')).toBe('البنيه')
  })

  it('folds ta marbuta to ha', () => {
    expect(normalize('مشكلة')).toBe('مشكله')
    expect(normalize('بطاقة')).toBe(normalize('بطاقه'))
  })

  it('folds alef maqsura to ya', () => {
    expect(normalize('مستوى')).toBe('مستوي')
    expect(normalize('على')).toBe(normalize('علي'))
  })

  it('removes diacritics and shadda', () => {
    expect(normalize('مُكَوِّن')).toBe('مكون')
    expect(normalize('يُعدَّل')).toBe('يعدل')
    expect(normalize('تحقُّقًا')).toBe('تحققا')
  })

  it('removes tatweel', () => {
    expect(normalize('الـمشاكل')).toBe('المشاكل')
    expect(normalize('مـــشـكلة')).toBe('مشكله')
  })

  it('folds hamza on waw and ya', () => {
    expect(normalize('مسؤول')).toBe('مسوول')
    expect(normalize('بيئة')).toBe('بييه')
  })

  it('turns Arabic-Indic and Persian digits into 0-9', () => {
    expect(normalize('٢١٧ مشكلة')).toBe('217 مشكله')
    expect(normalize('۱۶۵')).toBe('165')
  })

  it('drops invisible bidi and zero-width marks', () => {
    expect(normalize('EAOS‏ يصلحها⁨')).toBe('eaos يصلحها')
  })

  it('lower-cases Latin and removes accents', () => {
    expect(normalize('Café SRC/Pages')).toBe('cafe src/pages')
  })

  it('collapses spaces and trims', () => {
    expect(normalize('  خطة   الإصلاح \n')).toBe('خطه الاصلاح')
  })

  it('is idempotent', () => {
    for (const text of ['أَحْمَدُ', 'مسؤولية', 'الـمُستوى', 'src/components/Account.tsx', '٢٠٢٦']) {
      expect(normalize(normalize(text))).toBe(normalize(text))
    }
  })
})

describe('tokenize', () => {
  it('splits paths and identifiers into their parts', () => {
    expect(tokenize('src/components/account')).toEqual(['src', 'components', 'account'])
    expect(tokenize('TASK-001')).toEqual(['TASK', '001'])
  })

  it('keeps Arabic words whole', () => {
    expect(tokenize('خطة الإصلاح، 7 خطوات')).toEqual(['خطة', 'الإصلاح', '7', 'خطوات'])
  })
})

describe('tokenize with marks', () => {
  it('never splits a word at its diacritics', () => {
    expect(tokenize('الـمَشاكِل يُعدَّل')).toEqual(['الـمَشاكِل', 'يُعدَّل'])
  })
})

describe('terms', () => {
  it('adds the word without the definite article and its glued particles', () => {
    expect(terms('المشاكل')).toEqual(['المشاكل', 'مشاكل'])
    expect(terms('والمكونات')).toEqual(['والمكونات', 'مكونات'])
    expect(terms('بالخطه')).toEqual(['بالخطه', 'خطه'])
    expect(terms('للمكون')).toEqual(['للمكون', 'مكون'])
  })
  it('leaves short words, Latin and words without the article alone', () => {
    expect(terms('الا')).toEqual(['الا'])
    expect(terms('مشكله')).toEqual(['مشكله'])
    expect(terms('alpha')).toEqual(['alpha'])
  })
})
