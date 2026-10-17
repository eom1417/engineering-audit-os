// The sign-in page (#/sign-in, from Waiting for you, or alone on its own port from `eaos sign-in`): while a check waits,
// the person signs in to their app by its own way in the pinned Chromium EAOS opens (eaos/api/sign_in.py). Its page is a
// picture they click; what they type is passed on and never kept; what the app sent (a code, a link) shows below; "I
// have signed in" saves the session for them alone and the check goes on. Without a check waiting it says so, and a
// kept session can be forgotten.
import { useCallback, useEffect, useState, type MouseEvent } from 'react'
import { Input, Label, TextField } from 'react-aria-components'
import { Button } from '../../components/Button'
import { Panel, Section, StateMessage } from '../../components/Panel'
import { useCmdWords } from '../../command/words'
import cmd from '../../command/command.module.css'
import { useActions } from '../../data/actions/store'
import type { SignInInput, SignInStatus, SignInView } from '../../data/actions/types'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import css from './signin.module.css'

const LOOK = 1500 // ms between two pictures while the browser is open

export function SignInPage() {
  const w = useCmdWords()
  const api = useActions().client?.signIn
  const [status, setStatus] = useState<SignInStatus | null>(null)
  const [view, setView] = useState<SignInView | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  usePageChrome(w('signInTitle'))

  const run = useCallback(async <T,>(step: () => Promise<T>) => {
    setBusy(true); setProblem(null)
    try { return await step() } catch (error) { setProblem(String((error as Error).message ?? error)); return null } finally { setBusy(false) }
  }, [])
  useEffect(() => {
    if (!api) return
    let stopped = false
    const read = () => api.status().then((next) => { if (!stopped) setStatus(next) }, () => {})
    void read()
    const timer = setInterval(read, 4000)
    return () => { stopped = true; clearInterval(timer) }
  }, [api])
  useEffect(() => {
    if (!api || !status?.open) return
    const timer = setInterval(() => { void api.input({ do: 'look' }).then(setView, () => {}) }, LOOK)
    return () => clearInterval(timer)
  }, [api, status?.open])

  const send = async (command: SignInInput) => {
    const next = api ? await run(() => api.input(command)) : null
    if (next) setView(next)
  }
  const click = (event: MouseEvent<HTMLImageElement>) => {
    const image = event.currentTarget
    const box = image.getBoundingClientRect()
    void send({ do: 'click', x: Math.round((event.clientX - box.left) * image.naturalWidth / box.width), y: Math.round((event.clientY - box.top) * image.naturalHeight / box.height) })
  }
  const finish = async (step: 'done' | 'skip' | 'forget') => {
    const next = api ? await run(() => api[step]()) : null
    if (next) { setStatus(next); setView(null) }
  }
  const open = async () => {
    const next = api ? await run(() => api.open()) : null
    if (next && api) { setView(next); setStatus(await api.status()) }
  }
  const asked = status?.asked
  const lead = asked?.published ? w('signInPublished', { address: asked.base }) : asked?.why === 'expired' ? w('signInExpired') : w('signInLead')

  return (
    <div className={layout.page} data-sign-in>
      <PageTitle title={w('signInTitle')} lead={asked ? lead : undefined} />
      {problem && <Panel pad><StateMessage kind="error" title={problem} /></Panel>}
      {!asked ? (
        <Panel pad>
          <StateMessage icon="signIn" title={status?.kept ? w('signInKept') : w('signInNone')} sub={w('signInNoneSub')}
            action={status?.kept ? <Button variant="secondary" icon="opDelete" busy={busy} onPress={() => void finish('forget')}>{w('signInForget')}</Button> : undefined} />
        </Panel>
      ) : (
        <Panel pad>
          <div className={css.body}>
            {view?.picture ? (
              <>
                <span className={css.address} dir="ltr">{view.url}</span>
                <img className={css.picture} src={`data:image/jpeg;base64,${view.picture}`} alt={w('signInPicture')} title={w('signInPicture')} onClick={click} data-sign-in-picture />
                <form className={css.keys} onSubmit={(event) => { event.preventDefault(); if (text) void send({ do: 'type', text }).then(() => setText('')) }}>
                  <TextField className={cmd.field} value={text} onChange={setText} aria-label={w('signInText')}>
                    <Label className={cmd.fieldLabel}>{w('signInText')}</Label>
                    <Input className={cmd.input} autoComplete="off" spellCheck={false} data-sign-in-text />
                  </TextField>
                  <Button variant="secondary" type="submit" isDisabled={!text || busy}>{w('signInSend')}</Button>
                  <Button variant="secondary" onPress={() => void send({ do: 'key', key: 'Enter' })}>{w('signInEnter')}</Button>
                  <Button variant="secondary" onPress={() => void send({ do: 'key', key: 'Tab' })}>{w('signInTab')}</Button>
                  <Button variant="ghost" onPress={() => void send({ do: 'key', key: 'Backspace' })}>{w('signInErase')}</Button>
                  <Button variant="ghost" onPress={() => void send({ do: 'scroll', dy: -400 })}>{w('signInUp')}</Button>
                  <Button variant="ghost" onPress={() => void send({ do: 'scroll', dy: 400 })}>{w('signInDown')}</Button>
                  <Button variant="ghost" icon="back" onPress={() => void send({ do: 'back' })}>{w('signInBack')}</Button>
                </form>
              </>
            ) : (
              <div><Button variant="primary" icon="signIn" busy={busy} onPress={() => void open()} data-sign-in-open>{w('signInOpen')}</Button></div>
            )}
            <div className={css.foot}>
              <Button variant="secondary" isDisabled={busy} onPress={() => void finish('skip')} data-sign-in-skip>{w('signInSkip')}</Button>
              <Button variant="primary" icon="check" busy={busy} isDisabled={!view} onPress={() => void finish('done')} data-sign-in-done>{w('signInDone')}</Button>
            </div>
          </div>
        </Panel>
      )}
      {asked && (
        <Section title={w('signInCodes')}>
          <Panel pad>
            {status?.codes?.mail.map((mail) => <pre key={mail.at + mail.subject} className={css.said} dir="ltr">✉️ {mail.subject}{'\n'}{mail.text}</pre>)}
            {status?.codes?.output.length ? <pre className={css.said} dir="ltr" data-sign-in-output>{status.codes.output.slice(-12).join('\n')}</pre>
              : !status?.codes?.mail.length && <StateMessage title={w('signInCodesNone')} />}
          </Panel>
        </Section>
      )}
    </div>
  )
}
