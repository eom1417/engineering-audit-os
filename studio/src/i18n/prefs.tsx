// The person's display choices (language, theme) and the developer flag, kept in localStorage and on <html>.
// public/boot.js applies them before the first paint; this context keeps React and <html> in step afterwards.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { I18nProvider } from 'react-aria-components'
import { WORDS, type WordKey } from './catalog'

export type Lang = 'ar' | 'en'
export type Theme = 'light' | 'dark'
const KEY = 'eaos.studio'

function saved(): { lang?: Lang; theme?: Theme; dev?: boolean } {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {} } catch { return {} }
}

function save(patch: Record<string, unknown>) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...saved(), ...patch })) } catch { /* private mode: the choice lasts this visit */ }
}

declare global { interface Window { EAOS_BOOT?: { dev?: boolean } } }

/** Unbuilt sections are hidden unless the developer flag is on: ?dev=1 in the address once (public/boot.js keeps it). */
function devFlag(): boolean {
  return (window.EAOS_BOOT?.dev ?? saved().dev) === true
}

export interface Prefs {
  lang: Lang
  dir: 'rtl' | 'ltr'
  theme: Theme
  dev: boolean
  setLang(lang: Lang): void
  setTheme(theme: Theme): void
  /** A fixed word in the current language; {name} placeholders are filled from vars */
  t(key: WordKey, vars?: Record<string, string | number>): string
  /** A number with Western digits and the language's grouping */
  num(value: number): string
  /** A date (and time, in UTC) in the current language */
  date(iso: string, withTime?: boolean): string
}

const PrefsContext = createContext<Prefs | null>(null)

function makePrefs(lang: Lang, theme: Theme, dev: boolean, setLang: (lang: Lang) => void, setTheme: (theme: Theme) => void): Prefs {
  const index = lang === 'ar' ? 0 : 1
  const locale = lang === 'ar' ? 'ar-u-nu-latn' : 'en-GB'
  const numbers = new Intl.NumberFormat(locale)
  // Building a date format is slow next to using one: each is built on its first use and kept with these prefs
  let days: Intl.DateTimeFormat | undefined
  let times: Intl.DateTimeFormat | undefined
  return {
    lang, theme, dev, setLang, setTheme,
    dir: lang === 'ar' ? 'rtl' : 'ltr',
    t(key, vars) {
      let text: string = WORDS[key][index]
      for (const [name, v] of Object.entries(vars || {})) text = text.replaceAll(`{${name}}`, typeof v === 'number' ? numbers.format(v) : v)
      return text
    },
    num: (value) => numbers.format(value),
    date(iso, withTime = true) {
      const when = new Date(iso)
      if (Number.isNaN(when.getTime())) return iso
      days ??= new Intl.DateTimeFormat(locale, { day: 'numeric', month: lang === 'ar' ? 'long' : 'short', year: 'numeric', timeZone: 'UTC' })
      const day = days.format(when)
      if (!withTime) return day
      times ??= new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hourCycle: 'h23' })
      const time = times.format(when)
      return `${day}${lang === 'ar' ? '،' : ','} ${time} UTC`
    },
  }
}


export function PrefsProvider({ children }: { children: ReactNode }) {
  const html = document.documentElement
  const [lang, setLangState] = useState<Lang>(html.lang === 'en' ? 'en' : 'ar')
  const [theme, setThemeState] = useState<Theme>(html.dataset.theme === 'dark' ? 'dark' : 'light')
  const [dev] = useState(devFlag)

  useEffect(() => {
    html.lang = lang
    html.dir = lang === 'ar' ? 'rtl' : 'ltr'
  }, [html, lang])
  useEffect(() => { html.dataset.theme = theme }, [html, theme])

  const setLang = useCallback((next: Lang) => { save({ lang: next }); setLangState(next) }, [])
  const setTheme = useCallback((next: Theme) => { save({ theme: next }); setThemeState(next) }, [])

  const value = useMemo(() => makePrefs(lang, theme, dev, setLang, setTheme), [lang, theme, dev, setLang, setTheme])

  return (
    <PrefsContext.Provider value={value}>
      <I18nProvider locale={lang === 'ar' ? 'ar-u-nu-latn' : 'en-GB'}>{children}</I18nProvider>
    </PrefsContext.Provider>
  )
}

export function usePrefs(): Prefs {
  const prefs = useContext(PrefsContext)
  if (!prefs) throw new Error('usePrefs outside PrefsProvider')
  return prefs
}

/** A part of the page in another language or theme (the gallery's frames): words, direction and tokens follow it. */
export function PrefsScope({ lang, theme, children, className }: { lang: Lang; theme: Theme; children: ReactNode; className?: string }) {
  const parent = usePrefs()
  const value = useMemo(() => makePrefs(lang, theme, parent.dev, parent.setLang, parent.setTheme), [lang, theme, parent])
  return (
    <PrefsContext.Provider value={value}>
      <I18nProvider locale={lang === 'ar' ? 'ar-u-nu-latn' : 'en-GB'}>
        <div lang={lang} dir={value.dir} data-theme={theme} className={className}>{children}</div>
      </I18nProvider>
    </PrefsContext.Provider>
  )
}
