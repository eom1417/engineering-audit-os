// Library (developer flag only until NS37.T3 builds the reader): the documents the check wrote, grouped by purpose.
import { Panel, Section } from '../components/Panel'
import type { StudioData } from '../data/types'
import { usePrefs } from '../i18n/prefs'
import { Id, Txt } from '../i18n/text'
import { usePageChrome } from '../shell/chrome'
import { layout, PageTitle, WithData } from '../shell/Layout'
import css from './Pages.module.css'

function LibraryBody({ data }: { data: StudioData }) {
  const { t } = usePrefs()
  usePageChrome(t('library'), undefined, data.manifest.project.name)
  const groups = new Map<string, StudioData['docs'] extends { docs: infer D } | undefined ? D : never>()
  for (const doc of data.docs?.docs ?? []) groups.set(doc.group, [...(groups.get(doc.group) ?? []), doc])
  return (
    <div className={layout.page}>
      <PageTitle title={t('documents')} />
      {[...groups].map(([group, docs]) => (
        <Section key={group} title={group} count={docs.length}>
          <Panel><ul>{docs.map((doc) => <li key={doc.id} className={css.docRow}><Txt block>{doc.title}</Txt><Id value={doc.path} className={css.muted} /></li>)}</ul></Panel>
        </Section>
      ))}
    </div>
  )
}

export function LibraryPage() {
  return <WithData>{(data) => <LibraryBody data={data} />}</WithData>
}
