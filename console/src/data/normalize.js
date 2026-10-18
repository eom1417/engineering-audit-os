// The one Arabic (and Latin) normaliser of the console's search (studio/src/search/normalize.ts, ported): the indexed
// text and the query both pass through it, so what a person types matches however the report spells it.

const DIACRITICS = /[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]/g; // harakat, shadda, sukun, Quranic marks
const TATWEEL = /ـ/g;
const ALEF = /[آأإٱٲٳ]/g; // آ أ إ ٱ ٲ ٳ -> ا
const ARABIC_INDIC = /[٠-٩]/g;
const PERSIAN_DIGITS = /[۰-۹]/g;
const FORMAT = /[​-‏‪-‮⁦-⁩﻿]/g; // zero-width and bidi controls
const LATIN_MARKS = /[̀-ͯ]/g;
// The Arabic definite article and the particles glued before it: المشاكل، والمشاكل، بالخطة، للمكون
const ARTICLE = /^(?:[وفبكل]?ال|لل)(?=[ء-ي]{2,})/;

/** Folds the spellings people use interchangeably into one: alef forms to bare alef, ta marbuta to ha, alef maqsura
 *  to ya, hamza on waw or ya to the letter, diacritics, tatweel and invisible controls removed, Arabic-Indic digits to
 *  0-9, Latin lower-cased without accents, runs of space collapsed. */
export function normalize(text) {
  text = String(text || '');
  if (/^[\x00-\x7f]*$/.test(text)) return text.toLowerCase().replace(/\s+/g, ' ').trim();
  return text.normalize('NFKD').replace(FORMAT, '').replace(DIACRITICS, '').replace(LATIN_MARKS, '').replace(TATWEEL, '').normalize('NFC')
    .replace(ALEF, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/ؤ/g, 'و').replace(/ئ/g, 'ي').replace(/ی/g, 'ي').replace(/ک/g, 'ك')
    .replace(ARABIC_INDIC, d => String(d.charCodeAt(0) - 0x0660)).replace(PERSIAN_DIGITS, d => String(d.charCodeAt(0) - 0x06F0))
    .toLowerCase().replace(/\s+/g, ' ').trim();
}

/** Splits text into search terms: letters (with their marks) and digits of any script; paths and identifiers also
 *  split at / . _ - */
export function tokenize(text) { return String(text || '').split(/[^\p{L}\p{M}\p{N}]+/u).filter(Boolean); }

/** The search terms one normalised word stands for: itself and, for an Arabic word with the article, the bare word. */
export function terms(word) {
  const bare = word.replace(ARTICLE, '');
  return bare !== word ? [word, bare] : [word];
}

/** Whether every word of the query is found in the text (a word with the article also matches without it). */
export function matches(text, q) {
  const words = tokenize(normalize(q));
  if (!words.length) return true;
  const hay = tokenize(normalize(text)).flatMap(terms).join(' ');
  return words.every(w => terms(w).some(x => hay.includes(x)));
}
