// Direct control first (NS46.T19 governance): a page's action opens the command centre's preview, which runs it in the
// live Studio and, in a snapshot, says how to open the live Studio with copying the request only as a labelled
// fallback. A page never offers copying as its only action for something the command centre can do.
import { Button, CopyRequestButton, type Variant } from '../components/Button'
import type { IconName } from '../components/Icon'
import { actionOf } from '../data/actions/contract'
import { useCommandMaybe, type CommandRequest } from './command'

export function DirectAction({ request, label, variant = 'primary', block, icon = 'play', copy }:
  { request: CommandRequest; label: string; variant?: Variant; block?: boolean; icon?: IconName; copy?: { request: string; tool?: string | null } }) {
  const command = useCommandMaybe()
  const known = request.verb || (request.action && actionOf(request.action))
  if (!command || !known) return copy ? <CopyRequestButton request={copy.request} tool={copy.tool} variant={variant} block={block} /> : null
  return <Button variant={variant} block={block} icon={icon} onPress={() => command.open(request)} data-direct={request.verb ?? request.action}>{label}</Button>
}
