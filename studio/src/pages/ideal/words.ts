// The words of the planned ideal page, Arabic first and English equally finished; a key missing in one language is a
// type error.
import { makeWords } from '../../map/words'

export const IDEAL_WORDS = {
  title: ['هدف القواعد مقابل المثالي المخطَّط', 'Rules target against the planned ideal'],
  short: ['المثالي المخطَّط', 'Planned ideal'],
  open: ['قارن هدف القواعد بالمثالي المخطَّط', 'Compare the rules target with the planned ideal'],
  view: ['العرض', 'View'],
  view_system: ['البنية', 'Structure'],
  view_change: ['التغيير', 'Change'],
  view_journeys: ['الرحلات', 'Journeys'],
  view_paths: ['المسارات', 'Code paths'],
  view_data_paths: ['البيانات', 'Data'],
  view_infra: ['البنية التحتية', 'Infrastructure'],
  view_pipeline: ['خط المعالجة', 'Pipeline'],
  view_plan_order: ['ترتيب الخطة', 'Plan order'],
  planned: ['مخطَّط', 'Planned'],
  rulesOnlyMethod: ['القواعد فقط', 'Rules only'],
  by: ['خطّطه {a} ({m})', 'Planned by {a} ({m})'],
  on: ['في {d}', 'on {d}'],
  share: ['بدليل: {p}٪', 'With evidence: {p}%'],
  elements: ['{n} عنصر', '{n} elements'],
  dropped: ['حُذف {n} بلا دليل', '{n} dropped without evidence'],
  confidence: ['الثقة {p}٪', 'Confidence {p}%'],
  rulesSide: ['هدف القواعد', 'The rules target'],
  plannedSide: ['المثالي المخطَّط', 'The planned ideal'],
  same: ['نفسه', 'Same'],
  changed: ['تغيّر', 'Changed'],
  added: ['جديد', 'Added'],
  rulesOnly: ['في القواعد فقط', 'Rules only'],
  rulesSaid: ['القواعد قالت: {o}', 'The rules said: {o}'],
  cites: ['الدليل', 'Evidence'],
  departures: ['أين خالف التخطيط القواعد ولماذا', 'Where the plan departs from the rules, and why'],
  ruleSays: ['القواعد تقول', 'The rules say'],
  planChose: ['التخطيط اختار', 'The plan chose'],
  because: ['لأن', 'Because'],
  questions: ['أسئلة تنتظر قرارك', 'Questions waiting for you'],
  recommendation: ['التوصية', 'Recommendation'],
  notPlanned: ['هذا العرض على هدف القواعد', 'This view stays on the rules target'],
  nothing: ['لا شيء هنا في هذا الفحص', 'Nothing here in this check'],
  noSection: ['ما فيه مثالي مخطَّط لهذا الفحص', 'This check has no planned ideal'],
  noSectionSub: ['أعد تخطيط المثالي من مركز التحكم بمساعدك، ثم افتح هذه الصفحة.', 'Re-plan the ideal from the command centre with your assistant, then open this page.'],
  op_retain: ['يبقى', 'Keep'],
  op_refactor: ['يُعاد ترتيبه', 'Refactor'],
  op_rebuild: ['يُعاد بناؤه', 'Rebuild'],
  op_merge: ['يُدمج', 'Merge'],
  op_delete: ['يُحذف', 'Delete'],
  op_new: ['جديد', 'New'],
} as const

export type IdealWord = keyof typeof IDEAL_WORDS

/** The planned ideal page's words in the current language. */
export const useIdealWords = makeWords<IdealWord>(IDEAL_WORDS)
