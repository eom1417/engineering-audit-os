// The one Arabic (and Latin) normaliser of the Studio's search: the indexed text and the query both pass through it,
// so what a person types matches however the report spells it (docs/adoption/ns37-t1-studio-shell.md).

const DIACRITICS = /[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]/g // harakat, shadda, sukun, Quranic marks, superscript alef
const TATWEEL = /ـ/g
const ALEF = /[آأإٱٲٳ]/g // آ أ إ ٱ ٲ ٳ -> ا
const ARABIC_INDIC = /[٠-٩]/g // ٠-٩
const PERSIAN_DIGITS = /[۰-۹]/g // ۰-۹
const FORMAT = /[​-‏‪-‮⁦-⁩﻿]/g // zero-width and bidi controls
const LATIN_MARKS = /[̀-ͯ]/g // combining accents left by NFKD

/** Folds the spellings people use interchangeably into one: alef forms to bare alef, ta marbuta to ha, alef maqsura
 * to ya, hamza on waw/ya to the letter, diacritics, tatweel and invisible controls removed, Arabic-Indic digits to
 * 0-9, Latin lower-cased without accents, and runs of space collapsed. */
export function normalize(text: string): string {
  return text
    .normalize('NFKD')
    .replace(FORMAT, '')
    .replace(DIACRITICS, '')
    .replace(LATIN_MARKS, '')
    .replace(TATWEEL, '')
    .normalize('NFC')
    .replace(ALEF, 'ا')
    .replace(/ة/g, 'ه') // ة -> ه
    .replace(/ى/g, 'ي') // ى -> ي
    .replace(/ؤ/g, 'و') // ؤ -> و
    .replace(/ئ/g, 'ي') // ئ -> ي
    .replace(/ی/g, 'ي') // Persian ya -> ya
    .replace(/ک/g, 'ك') // keheh -> kaf
    .replace(ARABIC_INDIC, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(PERSIAN_DIGITS, (d) => String(d.charCodeAt(0) - 0x06F0))
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

/** Splits text into search terms: letters (with their marks) and digits of any script; paths and identifiers also split at / . _ - */
export function tokenize(text: string): string[] {
  return text.split(/[^\p{L}\p{M}\p{N}]+/u).filter(Boolean)
}

// The Arabic definite article and the particles glued before it: "المشاكل", "والمشاكل", "بالخطة", "للمكون"
const ARTICLE = /^(?:[وفبكل]?ال|لل)(?=[\u0621-\u064A]{2,})/

/** The search terms one normalised word stands for: itself and, for an Arabic word with the article, the word
 * without it, so "مشاكل" finds "المشاكل" and "الخطة" finds "خطة". */
export function terms(word: string): string[] {
  const bare = word.replace(ARTICLE, '')
  return bare !== word ? [word, bare] : [word]
}
