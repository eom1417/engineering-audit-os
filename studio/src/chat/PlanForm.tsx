// A new project from its plan (eaos/studio/actions/plan.py): its name, its files (documents and the pictures of its
// screens) or its pasted text; the person's assistant then reads it and draws the blueprint, followed in Runs.
import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '../components/Button'
import { useActions } from '../data/actions/store'
import { usePrefs } from '../i18n/prefs'
import css from './chat.module.css'

const WORDS = {
  name: ['اسم المشروع الجديد', 'The new project\'s name'],
  files: ['ملفات الخطة وصور الشاشات (PDF، Word، HTML، Markdown، نص، صور)', 'The plan\'s files and screen pictures (PDF, Word, HTML, Markdown, text, pictures)'],
  text: ['أو الصق نص الخطة هنا', 'Or paste the plan here'],
  go: ['ارسم البنية والخطة', 'Draw the structure and the plan'],
  note: ['يُبنى في مجلد جديد جنب هذا المشروع. المساعد يقرأ الخطة والصور، ويسألك الخيارات الحقيقية فقط، ويرسم البنية والشكل وخطة البناء كاملة. البناء نفسه يبدأ بعد موافقتك.',
    'It is made in a new folder beside this project. The assistant reads the plan and pictures, asks you only real choices, and draws the structure, the look and the whole build plan. The build itself starts once you agree.'],
} as const
const ACCEPT = '.md,.markdown,.txt,.text,.rst,.pdf,.docx,.html,.htm,.json,.yaml,.yml,.png,.jpg,.jpeg,.webp,.gif'

const base64 = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '')
  reader.onerror = () => reject(reader.error)
  reader.readAsDataURL(file)
})

export function PlanForm() {
  const { lang } = usePrefs()
  const at = lang === 'ar' ? 0 : 1
  const { client } = useActions()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')
  if (!client?.plan) return null
  const go = async () => {
    setBusy(true)
    setProblem('')
    try {
      const sent = await Promise.all(files.map(async (file) => ({ name: file.name, data: await base64(file) })))
      const run = await client.plan!({ name, text, files: sent })
      navigate({ to: `/runs/${encodeURIComponent(run.id)}` })
    } catch (error) {
      setProblem(error instanceof Error ? error.message : String(error))
    } finally { setBusy(false) }
  }
  return (
    <div className={css.card} data-plan-form="">
      <label className={css.field}>{WORDS.name[at]}
        <input className={css.input} value={name} dir="ltr" onChange={(e) => setName(e.target.value)} />
      </label>
      <label className={css.field}>{WORDS.files[at]}
        <input type="file" multiple accept={ACCEPT} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
      </label>
      <textarea className={css.input} rows={3} value={text} placeholder={WORDS.text[at]} onChange={(e) => setText(e.target.value)} />
      <span className={css.hint}>{WORDS.note[at]}</span>
      {problem && <span className={css.error} role="alert">{problem}</span>}
      <div><Button variant="primary" icon="plan" busy={busy} isDisabled={!name.trim() || (!files.length && !text.trim())} onPress={() => void go()}>{WORDS.go[at]}</Button></div>
    </div>
  )
}
