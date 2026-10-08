// The Cmd/Ctrl-K palette: React Aria's Autocomplete keeps the caret in the field while the arrows move through the
// results, which come from the Studio's MiniSearch index with Arabic normalisation (src/search).
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { Autocomplete, Dialog, Header, ListBox, ListBoxItem, ListBoxSection, Modal, ModalOverlay } from 'react-aria-components'
import { SearchField } from '../components/Controls'
import { Icon, type IconName } from '../components/Icon'
import { useStudio } from '../data/context'
import { WORDS } from '../i18n/catalog'
import { usePrefs } from '../i18n/prefs'
import { Id, Txt } from '../i18n/text'
import { buildIndex, type Entry, type EntryKind } from '../search'
import { visibleSections } from './sections'
import css from './Palette.module.css'

const KIND: Record<EntryKind, { icon: IconName; word: 'kindPage' | 'kindComponent' | 'kindCard' | 'kindDecision' | 'kindDoc' }> = {
  page: { icon: 'gallery', word: 'kindPage' },
  component: { icon: 'folder', word: 'kindComponent' },
  card: { icon: 'problems', word: 'kindCard' },
  decision: { icon: 'inbox', word: 'kindDecision' },
  doc: { icon: 'file', word: 'kindDoc' },
}
const ORDER: EntryKind[] = ['page', 'decision', 'component', 'card', 'doc']

/** Every place the palette can open: the visible sections (in both languages), components, cards, decisions, docs. */
export function useEntries(): Entry[] {
  const data = useStudio()
  const { lang, dev } = usePrefs()
  return useMemo(() => {
    const index = lang === 'ar' ? 0 : 1
    const entries: Entry[] = visibleSections(dev).map((s) => ({
      id: `page:${s.id}`, kind: 'page', title: WORDS[s.nav][index], keywords: [...WORDS[s.nav], ...WORDS[s.tab]].join(' '), to: s.to,
    }))
    if (!data) return entries
    for (const c of data.story?.current.components ?? []) entries.push({ id: `component:${c.name}`, kind: 'component', title: c.name, to: `/system?focus=${encodeURIComponent(c.name)}` })
    for (const d of data.decisions?.decisions ?? []) entries.push({ id: `decision:${d.id}`, kind: 'decision', title: d.question, keywords: d.recommendation, to: '/decisions' })
    for (const c of data.cards?.cards ?? []) entries.push({ id: `card:${c.id}`, kind: 'card', title: c.title, keywords: [c.id, ...c.paths, c.kind].join(' '), to: `/problems?card=${encodeURIComponent(c.id)}` })
    if (dev) for (const d of data.docs?.docs ?? []) entries.push({ id: `doc:${d.id}`, kind: 'doc', title: d.title, keywords: d.path, to: '/library' })
    return entries
  }, [data, lang, dev])
}

export function Palette({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = usePrefs()
  const navigate = useNavigate()
  const entries = useEntries()
  const index = useMemo(() => buildIndex(entries), [entries])
  const [query, setQuery] = useState('')
  useEffect(() => { if (!isOpen) setQuery('') }, [isOpen])
  const results = useMemo(() => index.search(query, 40), [index, query])
  const groups = ORDER.map((kind) => ({ kind, items: results.filter((r) => r.kind === kind) })).filter((g) => g.items.length)

  const open = (entry: Entry) => {
    onOpenChange(false)
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
