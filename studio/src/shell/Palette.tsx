// The Cmd/Ctrl-K palette: React Aria's Autocomplete keeps the caret in the field while the arrows move through the
// results, which come from the Studio's MiniSearch index with Arabic normalisation (src/search).
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { Autocomplete, Dialog, Header, ListBox, ListBoxItem, ListBoxSection, Modal, ModalOverlay } from 'react-aria-components'
import { SearchField } from '../components/Controls'
import { useCommandMaybe } from '../command/command'
import { ACTIONS, VERBS } from '../data/actions/contract'
import type { VerbId } from '../data/actions/types'
import { Icon, type IconName } from '../components/Icon'
import { useStudio } from '../data/context'
import { WORDS } from '../i18n/catalog'
import { usePrefs } from '../i18n/prefs'
import { Id, Txt } from '../i18n/text'
import { DATA_WORDS } from '../pages/data/words'
import { buildIndex, type Entry, type EntryKind } from '../search'
import { visibleSections } from './sections'
import css from './Palette.module.css'

const KIND: Record<EntryKind, { icon: IconName; word: 'kindPage' | 'kindAction' | 'kindComponent' | 'kindCard' | 'kindDecision' | 'kindDoc' }> = {
  page: { icon: 'gallery', word: 'kindPage' },
  action: { icon: 'command', word: 'kindAction' },
  component: { icon: 'folder', word: 'kindComponent' },
  card: { icon: 'problems', word: 'kindCard' },
  decision: { icon: 'inbox', word: 'kindDecision' },
  doc: { icon: 'file', word: 'kindDoc' },
}
const ORDER: EntryKind[] = ['page', 'action', 'decision', 'component', 'card', 'doc']

/** Every place the palette can open: the visible sections (in both languages), every EAOS action by name (the command
 * centre, docs/studio-actions.json) and the verbs over the current selection, components, cards, decisions, docs. */
export function useEntries(): Entry[] {
  const data = useStudio()
  const { lang, dev } = usePrefs()
  const selected = useCommandMaybe()?.sel.ids.length ?? 0
  return useMemo(() => {
    const index = lang === 'ar' ? 0 : 1
    const entries: Entry[] = visibleSections(dev).map((s) => ({
      id: `page:${s.id}`, kind: 'page', title: WORDS[s.nav][index], keywords: [...WORDS[s.nav], ...WORDS[s.tab]].join(' '), to: s.to,
    }))
    if (selected) for (const verb of VERBS) entries.push({ id: `verb:${verb.id}`, kind: 'action', title: `${verb.label[lang]} (${selected})`, keywords: `${verb.label.en} ${verb.label.ar} ${verb.id}`, to: `verb:${verb.id}` })
    for (const action of ACTIONS) entries.push({ id: `action:${action.id}`, kind: 'action', title: action.label[lang], keywords: [action.label.en, action.label.ar, action.id, action.description[lang]].join(' '), to: `action:${action.id}` })
    if (!data) return entries
    // the System section's own maps, beside the territory
    if (data.data_paths) entries.push({ id: 'page:data', kind: 'page', title: DATA_WORDS.dataTitle[index], keywords: DATA_WORDS.dataTitle.join(' '), to: '/system/data' })
    if (data.infra) entries.push({ id: 'page:infra', kind: 'page', title: DATA_WORDS.infraTitle[index], keywords: DATA_WORDS.infraTitle.join(' '), to: '/system?lens=infra' })
    for (const s of data.data_paths?.stores ?? []) entries.push({ id: `component:${s.id}`, kind: 'component', title: s.name, to: `/system/data?store=${encodeURIComponent(s.id)}` })
    for (const c of data.story?.current.components ?? []) entries.push({ id: `component:${c.name}`, kind: 'component', title: c.name, to: `/system?focus=${encodeURIComponent(c.name)}` })
    for (const d of data.decisions?.decisions ?? []) entries.push({ id: `decision:${d.id}`, kind: 'decision', title: d.question, keywords: d.recommendation, to: '/decisions' })
    for (const c of data.cards?.cards ?? []) entries.push({ id: `card:${c.id}`, kind: 'card', title: c.title, keywords: [c.id, ...c.paths, c.kind].join(' '), to: `/problems?card=${encodeURIComponent(c.id)}` })
    for (const d of data.docs?.docs ?? []) entries.push({ id: `doc:${d.id}`, kind: 'doc', title: d.title, keywords: [d.path, ...(d.headings ?? []).map((h) => h.text)].join(' '), to: `/library/docs/${encodeURIComponent(d.path)}` })
    return entries
  }, [data, lang, dev, selected])
}

export function Palette({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = usePrefs()
  const navigate = useNavigate()
  const command = useCommandMaybe()
  const entries = useEntries()
  const index = useMemo(() => buildIndex(entries), [entries])
  const [query, setQuery] = useState('')
  useEffect(() => { if (!isOpen) setQuery('') }, [isOpen])
  const results = useMemo(() => index.search(query, 40), [index, query])
  const groups = ORDER.map((kind) => ({ kind, items: results.filter((r) => r.kind === kind) })).filter((g) => g.items.length)

  const open = (entry: Entry) => {
    onOpenChange(false)
    if (entry.to.startsWith('action:')) { command?.open({ action: entry.to.slice(7), selection: command.selection }); return }
    if (entry.to.startsWith('verb:')) { command?.open({ verb: entry.to.slice(5) as VerbId, selection: command.selection }); return }
    const [path, search] = entry.to.split('?')
    navigate({ to: path, search: Object.fromEntries(new URLSearchParams(search ?? '')) })
  }

  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable className={css.overlay}>
      <Modal className={css.modal}>
        <Dialog className={css.dialog} aria-label={t('searchAndCommands')}>
          <Autocomplete inputValue={query} onInputChange={setQuery}>
            <div className={css.input}>
              <SearchField label={t('searchAndCommands')} placeholder={t('searchPlaceholder')} value={query} onChange={setQuery} autoFocus />
            </div>
            <ListBox className={css.list} aria-label={t('searchAndCommands')} selectionMode="none"
              onAction={(key) => { const entry = results.find((r) => r.id === key); if (entry) open(entry) }}
              renderEmptyState={() => <p className={css.empty}>{t('noResults')}</p>}>
              {groups.map((group) => (
                <ListBoxSection key={group.kind} id={group.kind} className={css.section}>
                  <Header className={css.groupTitle}>{t(KIND[group.kind].word)}</Header>
                  {group.items.map((entry) => (
                    <ListBoxItem key={entry.id} id={entry.id} textValue={entry.title} className={css.row}>
                      <Icon name={KIND[entry.kind].icon} />
                      <span className={css.title}>{entry.kind === 'component' ? <Id value={entry.title} /> : <Txt>{entry.title}</Txt>}</span>
                      {entry.kind === 'card' && <Id value={entry.id.slice(5)} className={css.kind} />}
                      {entry.id.startsWith('action:') && <Id value={entry.id.slice(7)} className={css.kind} />}
                    </ListBoxItem>
                  ))}
                </ListBoxSection>
              ))}
            </ListBox>
          </Autocomplete>
          <div className={css.foot} aria-hidden="true">{t('paletteHint')}</div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  )
}
