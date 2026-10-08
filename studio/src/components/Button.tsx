// Buttons on React Aria (press, hover, focus-visible and pressed states for mouse, touch and keyboard alike), and
// the request button: the Studio's one kind of action, a sentence copied for the assistant with its tool's name.
import type { ReactNode } from 'react'
import { Button as AriaButton, type ButtonProps } from 'react-aria-components'
import { usePrefs } from '../i18n/prefs'
import { Icon, type IconName } from './Icon'
import { useToast } from './Toast'
import css from './Button.module.css'

export type Variant = 'primary' | 'secondary' | 'ghost'

export function buttonClass(variant: Variant = 'secondary', opts: { block?: boolean; large?: boolean } = {}): string {
  return [css.btn, css[variant], opts.block && css.block, opts.large && css.large].filter(Boolean).join(' ')
}

export function Button({ variant = 'secondary', block, large, busy, icon, children, className, ...rest }:
  Omit<ButtonProps, 'children' | 'className'> & { variant?: Variant; block?: boolean; large?: boolean; busy?: boolean; icon?: IconName; children: ReactNode; className?: string }) {
  return (
    <AriaButton {...rest} isPending={busy} className={[buttonClass(variant, { block, large }), busy && css.busy, className].filter(Boolean).join(' ')}>
      {busy ? <span className={css.spinner} aria-hidden="true" /> : icon ? <Icon name={icon} /> : null}
      {children}
    </AriaButton>
  )
}

export function IconButton({ icon, label, small, className, ...rest }:
  Omit<ButtonProps, 'children' | 'className'> & { icon: IconName; label: string; small?: boolean; className?: string }) {
  return (
    <AriaButton {...rest} aria-label={label} className={[css.iconBtn, small && css.small, className].filter(Boolean).join(' ')}>
      <Icon name={icon} />
    </AriaButton>
  )
}

/** The tool's name in a mono tag, as on every request button */
export function ToolTag({ tool }: { tool: string }) {
  return <span className={css.tool}><bdi dir="ltr">{tool}</bdi></span>
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // file:// pages and older browsers: the selection fallback
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    let ok = false
    try { ok = document.execCommand('copy') } catch { ok = false }
    area.remove()
    return ok
  }
}

/** Copies a request for the assistant; the Studio itself never records or changes anything (DESIGN.md §1.6). */
export function CopyRequestButton({ request, tool, label, variant = 'secondary', block, copiedMessage }:
  { request: string; tool?: string | null; label?: string; variant?: Variant; block?: boolean; copiedMessage?: string }) {
  const { t } = usePrefs()
  const toast = useToast()
  return (
    <Button variant={variant} block={block} icon="copy"
      onPress={async () => toast((await copyText(request)) ? (copiedMessage ?? t('copied')) : t('copyFailed'))}>
      {label ?? t('copyRequest')}
      {tool ? <ToolTag tool={tool} /> : null}
    </Button>
  )
}
