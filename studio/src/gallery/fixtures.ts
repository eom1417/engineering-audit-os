// Sample data for the gallery: shaped like contract v1, in Arabic with the Latin runs a real report has.
import type { Card, Decision, Fact, Plan } from '../data/types'

export const decisionTwo: Decision = {
  id: 'investigations', state: 'waiting', answer: null, tool: 'findings', plan: 'fix',
  question: '52 بطاقة تحتاج تحققًا قبل أي تغيير. هل يتولاها المساعد؟',
  recommendation: 'نعم: يتحقق المساعد من كل بطاقة بدليلها ويعرض عليك ما يحتاج قرارك فقط.',
  options: [{ id: 'yes', label: 'نعم' }, { id: 'later', label: 'لاحقًا' }],
  blocks: Array.from({ length: 52 }, (_, i) => `TASK-${String(i + 1).padStart(3, '0')}`),
}

export const decisionMany: Decision = {
  id: 'target-architecture', state: 'waiting', answer: null, tool: null, plan: null,
  question: 'هل تعتمد البنية المستهدفة؟',
  recommendation: 'راجع قرارات البنية في القصة، ثم اعتمدها أو اطلب تعديلها.',
  options: [
    { id: 'ADR-001', label: 'Move 3 files of `src` into `pages` and break 1 forbidden import.' },
    { id: 'ADR-002', label: 'Rebuild `src/components` as `features`, behind the behaviour lock.' },
    { id: 'later', label: 'لاحقًا' },
  ],
  blocks: ['S06'],
}

export const decisionAnswered: Decision = { ...decisionTwo, id: 'answered', state: 'answered', answer: 'نعم، يتولاها المساعد.' }

const card = (over: Partial<Card>): Card => ({
  id: 'TASK-001', key: 'TASK-001', title: 'Flow FLOW-003 (page /) stops at 10 unresolvable calls', kind: 'trace_gap', category: 'maintainability',
  severity: 'low', state: 'open', fixable: false, needs_decision: true, milestone: 'M02', paths: ['src/App.tsx'], evidence: ['FACT-5a6158ac73683c1e'],
  scope: 'place', confidence: 1, ...over,
})

export const cards: Card[] = [
  card({}),
  card({ id: 'TASK-018', title: 'unused class `src/lib/types.FaultCode`: no reference outside its definition', severity: 'medium', needs_decision: false, fixable: true, paths: ['src/lib/types.ts'] }),
  card({ id: 'TASK-091', title: 'Hard-coded secret in the API client', severity: 'high', paths: ['src/components/maintenance/workorder/forms/WorkOrderAttachmentsUploader.tsx'] }),
  card({ id: 'TASK-120', title: 'ثغرة معروفة في `axios@0.21.1`', severity: 'critical', needs_decision: false, fixable: true, paths: ['package.json'] }),
]

export const facts: Fact[] = [
  { id: 'FACT-87fb7484bf9160e4', kind: 'broken_code', engine: 'tsc', path: 'src/pages/unused/ServiceHistory.tsx', line: 7, sites: [],
    summary: 'src/pages/unused/ServiceHistory.tsx imports `./ServiceAnalytics`, which does not exist in the project: the module fails to load' },
  { id: 'FACT-5a6158ac73683c1e', kind: 'trace_gap', engine: null, path: null, line: null, sites: [], summary: 'المسار FLOW-003 يتوقف عند 10 استدعاءات لا تُحل.' },
]

export const code = `import { ServiceAnalytics } from './ServiceAnalytics'   // the module does not exist
export function ServiceHistory() {
  return <ServiceAnalytics range="30d" vehicles={allVehiclesInTheFleetIncludingArchivedOnes} />
}`

export const plan = (done: number): Plan => ({
  id: 'fix', kind: 'fix', state: done ? 'active' : 'registered', progress: { value: done / 217, src: 'ledger' },
  steps: [147, 10, 42, 9, 1, 2, 6].map((n, i) => ({
    id: `M0${i + 1}`, state: 'todo', gate: '', title: '',
    tasks: Array.from({ length: n }, (_, k) => ({ id: `T${i}-${k}`, state: k < done * n / 217 * 3 ? 'done' : 'todo', title: '' })),
  })),
})
