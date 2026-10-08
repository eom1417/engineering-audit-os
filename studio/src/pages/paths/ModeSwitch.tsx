// The Current / Target / Change switch shared by the paths overview and a single path.
import { Segmented } from '../../components/Controls'
import { PATH_MODES, type PathMode } from './model'
import { MODE_WORD, usePathWords } from './words'

export function ModeSwitch({ mode, onChange, comfortable }: { mode: PathMode; onChange: (m: PathMode) => void; comfortable?: boolean }) {
  const w = usePathWords()
  return <Segmented label={w('view')} value={mode} onChange={onChange} comfortable={comfortable}
    options={PATH_MODES.map((m) => ({ id: m, label: w(MODE_WORD[m]) }))} />
}
