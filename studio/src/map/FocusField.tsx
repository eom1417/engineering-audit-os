// "Focus a component…": a combo box over the map's components (React Aria: typing filters, arrows move, Enter picks).
import { useState } from 'react'
import { ComboBox, Input, ListBox, ListBoxItem, Popover } from 'react-aria-components'
import { Icon } from '../components/Icon'
import { normalize } from '../search/normalize'
import { Id } from '../i18n/text'
import css from './FocusField.module.css'

export function FocusField({ ids, label, onPick, comfortable }: { ids: string[]; label: string; onPick: (id: string) => void; comfortable?: boolean }) {
  const [text, setText] = useState('')
  const query = normalize(text)
  const items = ids.filter((id) => !query || normalize(id).includes(query)).slice(0, 40).map((id) => ({ id }))
  return (
    <ComboBox aria-label={label} items={items} inputValue={text} onInputChange={setText} selectedKey={null} menuTrigger="input"
      onSelectionChange={(key) => { if (key !== null) { onPick(String(key)); setText('') } }}
      className={[css.box, comfortable && css.comfortable].filter(Boolean).join(' ')}>
      <div className={css.field}>
        <Icon name="search" />
        <Input placeholder={label} className={css.input} />
      </div>
      <Popover className={css.popover} placement="bottom start" offset={4}>
        <ListBox className={css.list}>
          {(item: { id: string }) => <ListBoxItem id={item.id} textValue={item.id} className={css.option}><Id value={item.id} /></ListBoxItem>}
        </ListBox>
      </Popover>
    </ComboBox>
  )
}
