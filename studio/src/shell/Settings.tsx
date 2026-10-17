// The person's settings, wherever they show (the Settings page, the project sheet, the phone's More): the language and
// the theme, the time zone every time is shown in, and the project's facts.
import { Segmented } from '../components/Controls'
import { Icon } from '../components/Icon'
import { Props } from '../components/Panel'
import { useBranchWords } from '../branches/words'
import { useStudio } from '../data/context'
import { deviceZone, usePrefs } from '../i18n/prefs'
import { Id, N, When } from '../i18n/text'
import css from './Shell.module.css'

export function LanguageAndTheme({ comfortable }: { comfortable?: boolean }) {
  const { t, lang, theme, setLang, setTheme } = usePrefs()
  return (
    <>
      <Segmented label={t('language')} value={lang} onChange={setLang} comfortable={comfortable}
        options={[{ id: 'ar', label: lang === 'en' ? 'Arabic' : 'عربي', lang: 'ar' }, { id: 'en', label: 'English', lang: 'en' }]} />
      <Segmented label={t('appearance')} value={theme} onChange={setTheme} comfortable={comfortable}
        options={[
          { id: 'light', label: comfortable ? <><Icon name="sun" />{t('light')}</> : <Icon name="sun" />, aria: comfortable ? undefined : t('light') },
          { id: 'dark', label: comfortable ? <><Icon name="moon" />{t('dark')}</> : <Icon name="moon" />, aria: comfortable ? undefined : t('dark') },
        ]} />
    </>
  )
}

/** Settings: the time zone every time is shown in; the device's unless the person chooses one, and remembered. */
export function TimeZoneSetting() {
  const { zone, zoneChoice, setZone } = usePrefs()
  const w = useBranchWords()
  const device = deviceZone()
  const zones = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? []
  const options = [...new Set([...(zoneChoice ? [zoneChoice] : []), 'UTC', ...zones])]
  return (
    <label className={css.zone}>
      <span>{w('timeZone')}</span>
      <select value={zoneChoice ?? ''} onChange={(event) => setZone(event.target.value || null)} data-zone={zone}>
        <option value="">{w('timeZoneDevice', { z: device })}</option>
        {options.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
      <small>{w('timeZoneLead')}</small>
    </label>
  )
}

/** The project's facts, drawn only while its sheet is open (a closed sheet renders nothing of its body). */
export function ProjectFacts() {
  const { t } = usePrefs()
  const data = useStudio()
  const rows: [React.ReactNode, React.ReactNode, boolean?][] = []
  if (data?.meta) {
    rows.push([t('files'), data.meta.files.value === null ? t('notMeasured') : <N value={data.meta.files.value} />, data.meta.files.value === null])
    rows.push([t('lines'), data.meta.lines.value === null ? t('notMeasured') : <N value={data.meta.lines.value} />, data.meta.lines.value === null])
    rows.push([t('languages'), <bdi dir="ltr">{data.meta.languages.map((l) => `${l.name} ${Math.round(l.share * 100)}%`).join(', ')}</bdi>])
  }
  if (data) {
    rows.push([t('scanned'), data.manifest.scanned.at ? <When iso={data.manifest.scanned.at} /> : t('notRecorded'), !data.manifest.scanned.at])
    rows.push([t('branch'), data.manifest.scanned.branch ? <Id value={data.manifest.scanned.branch} /> : t('notRecorded'), !data.manifest.scanned.branch])
    rows.push([t('eaosVersion'), <Id value={data.manifest.built.version} />])
  }
  return rows.length > 0 ? <Props rows={rows} /> : null
}
