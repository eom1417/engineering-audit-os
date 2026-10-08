// The sentences the Studio copies for the assistant. The Studio never acts: every action is one of these, with the
// EAOS tool that does it (docs/STUDIO.md, Standards: governance).
import type { Lang } from '../i18n/prefs'

export function nextRequest(action: string, tool: string | null, project: string, lang: Lang): string {
  if (lang === 'ar') return `${action} في ${project}${tool ? ` بأداة ${tool} من EAOS` : ''}.`
  return `In ${project}: ${action}${tool ? ` (EAOS tool ${tool})` : ''}.`
}
