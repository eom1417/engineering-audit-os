// Report prose follows the display language, independently of its source language.
// Identity fields and source-code locations remain byte-for-byte stable.
import { script, type Loaded } from './load'
import { liveToken } from './live'
import type { Lang } from '../i18n/prefs'
export interface ReportLocale { schema_version: 1; source_locale: Lang; translations: Partial<Record<Lang, Record<string, string>>> }
declare global { interface Window { EAOS_LOCALE?: ReportLocale } }
const IDENTITY = new Set(['missing', 'pending', 'revision', 'recommended_option', 'id', 'key', 'path', 'paths', 'file', 'sha256', 'digest', 'commit', 'src', 'fact', 'symbol', 'from', 'to', 'parent', 'pipeline', 'stage', 'stages', 'component', 'components', 'cards', 'steps', 'target', 'module', 'signature', 'subject', 'subjects', 'sources', 'after', 'callers', 'callees', 'evidence', 'code', 'line', 'lines'])
function translate(value: unknown, table: Record<string, string>, key?: string): unknown {
  if (key && IDENTITY.has(key) && (typeof value === 'string' || (Array.isArray(value) && value.every((item) => typeof item === 'string')))) return value
  if (typeof value === 'string') return table[value] ?? value
  if (Array.isArray(value)) return value.map((item) => translate(item, table))
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, translate(item, table, name)]))
  return value
}
export function localizeValue<T>(value: T, lang: Lang, locale?: ReportLocale): T {
  const table = locale?.translations[lang]
  return table ? translate(value, table) as T : value
}

export function localizeReport(loaded: Loaded, lang: Lang, locale?: ReportLocale): Loaded {
  if (loaded.kind !== 'ready' || !locale) return loaded
  const table = locale.translations[lang]
  if (!table) return loaded
  return { kind: 'ready', data: translate(loaded.data, table) as typeof loaded.data }
}

/** Snapshots use a local script; the live server requires the same token header as report sections. */
export async function loadReportLocale(): Promise<ReportLocale | undefined> {
  const token = liveToken()
  if (token) {
    const response = await fetch('/api/locales/en', { headers: { 'X-EAOS-Token': token }, cache: 'no-store', credentials: 'same-origin' })
    return response.ok ? await response.json() as ReportLocale : undefined
  }
  return await script('locale') ? window.EAOS_LOCALE : undefined
}
