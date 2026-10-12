import { describe, expect, it } from 'vitest'
import { normalize, terms, tokenize } from './normalize'

describe('normalize', () => {
  it('folds Arabic letter forms, marks, digits, bidi marks, Latin case and spaces', () => {
    expect(normalize('أحمد')).toBe(normalize('احمد'))
    expect(normalize('إصلاح')).toBe('اصلاح')
    expect(normalize('آخر')).toBe('اخر')
    expect(normalize('ٱلبنية')).toBe('البنيه')
    expect(normalize('بطاقة')).toBe(normalize('بطاقه'))
    expect(normalize('مستوى')).toBe('مستوي')
    expect(normalize('مُكَوِّن')).toBe('مكون')
    expect(normalize('تحقُّقًا')).toBe('تحققا')
    expect(normalize('مـــشـكلة')).toBe('مشكله')
    expect(normalize('مسؤول')).toBe('مسوول')
    expect(normalize('بيئة')).toBe('بييه')
    expect(normalize('٢١٧ مشكلة')).toBe('217 مشكله')
    expect(normalize('۱۶۵')).toBe('165')
    expect(normalize('EAOS‏ يصلحها⁨')).toBe('eaos يصلحها')
    expect(normalize('Café SRC/Pages')).toBe('cafe src/pages')
    expect(normalize('  خطة   الإصلاح \n')).toBe('خطه الاصلاح')
  })

  it('is idempotent', () => {
    for (const text of ['أَحْمَدُ', 'مسؤولية', 'الـمُستوى', 'src/components/Account.tsx', '٢٠٢٦']) {
      expect(normalize(normalize(text))).toBe(normalize(text))
    }
  })
})

describe('tokenize', () => {
  it('splits paths and identifiers, keeps Arabic words whole and never splits at diacritics', () => {
    expect(tokenize('src/components/account')).toEqual(['src', 'components', 'account'])
    expect(tokenize('TASK-001')).toEqual(['TASK', '001'])
    expect(tokenize('خطة الإصلاح، 7 خطوات')).toEqual(['خطة', 'الإصلاح', '7', 'خطوات'])
    expect(tokenize('الـمَشاكِل يُعدَّل')).toEqual(['الـمَشاكِل', 'يُعدَّل'])
  })
})

describe('terms', () => {
  it('adds the word without the article and its glued particles, leaving other words alone', () => {
    expect(terms('المشاكل')).toEqual(['المشاكل', 'مشاكل'])
    expect(terms('والمكونات')).toEqual(['والمكونات', 'مكونات'])
    expect(terms('بالخطه')).toEqual(['بالخطه', 'خطه'])
    expect(terms('للمكون')).toEqual(['للمكون', 'مكون'])
    expect(terms('الا')).toEqual(['الا'])
    expect(terms('مشكله')).toEqual(['مشكله'])
    expect(terms('alpha')).toEqual(['alpha'])
  })
})
