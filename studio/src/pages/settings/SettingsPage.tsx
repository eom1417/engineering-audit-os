// Settings (#/settings): what the person sets once, in one place: how the Studio shows (language, theme, time zone),
// the project's facts, the assistants on this computer with what they cost, and where the branches are protected.
import { Panel, RowLink, Section } from '../../components/Panel'
import { useStudio } from '../../data/context'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { LanguageAndTheme, ProjectFacts, TimeZoneSetting } from '../../shell/Settings'
import shell from '../../shell/Shell.module.css'
import { AssistantBody } from '../assistant/AssistantPage'

export function SettingsPage() {
  const { t } = usePrefs()
  const data = useStudio()
  usePageChrome(t('settings'), undefined, data?.manifest.project.name)
  return (
    <div className={layout.page}>
      <PageTitle title={t('settings')} lead={t('settingsLead')} />
      <Section title={t('display')}>
        <Panel pad><div className={shell.rowSet}><LanguageAndTheme comfortable /></div><TimeZoneSetting /></Panel>
      </Section>
      <Section title={t('project')}>
        <Panel pad><ProjectFacts /></Panel>
        <Panel><RowLink to="/branches" icon="branch" title={t('protectBranches')} /></Panel>
      </Section>
      <AssistantBody />
    </div>
  )
}
