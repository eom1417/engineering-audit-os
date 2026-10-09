// The words of the EAOS-quality page, Arabic first and English equally finished. A key missing in one language is a type
// error. Detector and indicator names come from the data, already in the report's language.
import { useWordTable } from '../../map/words'

export const QUALITY_WORDS = {
  quality: ['جودة EAOS', 'EAOS quality'],
  lead: ['إلى أي حد تثق بما يقوله EAOS عن هذا المشروع: دقة كل كاشف على حالات معلَّمة، وما أظهره هنا وما حجبه، وما لم يُقس بعد.',
    'How far you can trust what EAOS says about this project: each detector’s precision on labelled cases, what it showed here and what it held back, and what is not measured yet.'],
  shownHere: ['ظهرت لك', 'Shown to you'],
  shownSub: ['من {n} كاشفًا يتجاوز حد الدقة', 'from {n} detectors at the bar'],
  heldBack: ['حُجبت', 'Held back'],
  heldSub: ['من {n} كاشفًا دون الحد', 'from {n} detectors under the bar'],
  labelledSet: ['الحالات المعلَّمة', 'Labelled cases'],
  labelledSub: ['على {n} مشاريع', 'on {n} projects'],
  thisProjectLabelled: ['هذا المشروع منها', 'this project is one of them'],
  notMeasuredYet: ['لم يُقس بعد', 'Not measured yet'],
  notMeasuredSub: ['حالات معروضة بصدق، لا أرقام مختلقة', 'shown honestly, never invented'],
  // detectors
  detectorsHere: ['الكواشف التي عملت على هذا المشروع', 'The detectors that worked on this project'],
  detectorsLead: ['يُظهر EAOS نتائج الكاشف فقط إن بلغت دقته {p}٪ واستدعاؤه {r}٪ على {j} حالات محكومة على الأقل؛ وإلا حجبها وذكر السبب.',
    'EAOS shows a detector’s findings only when its precision reaches {p}% and its recall {r}% on at least {j} judged cases; otherwise it holds them back and says why.'],
  otherDetectors: ['كواشف لم تجد شيئًا هنا', 'Detectors that found nothing here'],
  status_meets_bar: ['يتجاوز الحد: نتائجه ظاهرة', 'At the bar: its findings are shown'],
  status_below_bar: ['دون الحد: نتائجه محجوبة', 'Under the bar: its findings are held back'],
  status_not_measured: ['لم يُقس بعد: نتائجه محجوبة', 'Not measured yet: its findings are held back'],
  precision: ['الدقة', 'Precision'],
  recall: ['الاستدعاء', 'Recall'],
  precisionHelp: ['من كل ما أبلغ عنه وحُكم عليه، كم كان صحيحًا', 'Of what it reported and was judged, how much was right'],
  recallHelp: ['من المشاكل المعروفة، كم وجد', 'Of the known problems, how many it found'],
  judgedN: ['على {n} حالة محكومة', 'on {n} judged cases'],
  tooFew: ['حالات قليلة ({n} من {b})', 'too few cases ({n} of {b})'],
  noCases: ['لا حالات معلَّمة له بعد', 'no labelled cases for it yet'],
  hereShown: ['{n} ظاهرة', '{n} shown'],
  hereWithheld: ['{n} محجوبة', '{n} held back'],
  hereFacts: ['{n} حقيقة بيانات', '{n} data facts'],
  onThisProject: ['على هذا المشروع: {tp} صحيحة و{fp} خاطئة من المحكوم عليها', 'On this project: {tp} right and {fp} wrong of those judged'],
  // coverage
  coverage: ['ما قاسه EAOS لهذا التقرير', 'What EAOS measured for this report'],
  coverageLead: ['كل قسم من بيانات الاستوديو: مقيس، أو جزئي، أو لم يُقس بعد مع سببه والخطوة التي ستقيسه.', 'Every section of the Studio’s data: measured, partial, or not measured yet with its reason and the step that will measure it.'],
  coverageCounts: ['{m} مقيس · {p} جزئي · {n} لم يُقس', '{m} measured · {p} partial · {n} not measured'],
  state_measured: ['مقيس', 'Measured'],
  state_empty: ['مقيس، ولا شيء', 'Measured, nothing found'],
  state_partial: ['جزئي', 'Partial'],
  state_not_measured: ['لم يُقس بعد', 'Not measured yet'],
  state_failed: ['تعذّر', 'Failed'],
  noCoverage: ['هذا التقرير لا يحمل جدول التغطية', 'This report carries no coverage table'],
  // indicators
  indicators: ['مؤشرات خطة EAOS للتحليل', 'The plan’s indicators for the analysis'],
  indicatorsLead: ['كيف يقيس EAOS نفسه على مشاريع العيّنة؛ المؤشر غير المقيس يُحسب صفرًا ولا يُخفى.', 'How EAOS measures itself on its sample projects; an unmeasured indicator counts as zero and is never hidden.'],
  measuredOf: ['{m} من {n} مقيس', '{m} of {n} measured'],
  target: ['الهدف ', 'target '],
  recorded: ['يُسجَّل يدويًا', 'recorded by hand'],
  asOf: ['قيست على مشاريع العيّنة؛ تُشحن مع هذا الإصدار من EAOS.', 'Measured on the sample projects; shipped with this version of EAOS.'],
  noQuality: ['جودة التحليل لم تُصدَّر لهذا التقرير', 'The analysis quality is not exported for this report'],
  // the Studio's data sections, as the coverage table names them
  sec_meta: ['وصف المشروع', 'About the project'], sec_head: ['رأس التقرير', 'Report header'], sec_health: ['الصحة', 'Health'],
  sec_cards: ['بطاقات المشاكل', 'Problem cards'], sec_evidence: ['الأدلة', 'Evidence'], sec_story: ['القصة', 'The story'],
  sec_docs: ['الوثائق', 'Documents'], sec_plans: ['الخطط', 'Plans'], sec_decisions: ['القرارات', 'Decisions'],
  sec_media: ['الصور والرسوم', 'Images and diagrams'], sec_functions: ['مستكشف الدوال', 'Function explorer'],
  sec_screens: ['معرض الشاشات', 'Screens gallery'], sec_gaps: ['سجل الفجوات', 'Gap register'], sec_operations: ['العمليات', 'Operations'],
  sec_history: ['التاريخ', 'History'], sec_quality: ['جودة EAOS', 'EAOS quality'], sec_maps: ['الخرائط الكاملة', 'Full maps'],
  sec_paths: ['مسارات الكود', 'Code paths'], sec_journeys: ['رحلات المستخدم', 'User journeys'], sec_hidden: ['الظاهر والخفي', 'Visible and hidden'],
  sec_data_paths: ['مسارات البيانات', 'Data paths'], sec_infra: ['البنية التحتية', 'Infrastructure'], sec_pipeline: ['خط المعالجة', 'Pipeline'],
  sec_system: ['خريطة النظام', 'System map'], sec_library: ['نصوص المكتبة', 'Library texts'],
} as const

export type QualityWord = keyof typeof QUALITY_WORDS

export function useQualityWords() {
  return useWordTable(QUALITY_WORDS)
}
