// The words of the maps (System, the Home land card, Change), Arabic first and English equally finished. Kept apart
// from i18n/catalog.ts so the maps travel as one module; a key missing in one language is a type error.
import { usePrefs } from '../i18n/prefs'
import type { Operation } from '../data/system'

export const MAP_WORDS = {
  systemMap: ['خريطة النظام', 'System map'],
  mapToday: ['اليوم', 'Today'],
  mapTarget: ['الهدف', 'Target'],
  mapChange: ['التغيير', 'Change'],
  mapView: ['ماذا تعرض الخريطة', 'What the map shows'],
  showAs: ['طريقة العرض', 'Show as'],
  asMap: ['خريطة', 'Map'],
  asList: ['قائمة', 'List'],
  regionsCount: ['{r} مناطق · {c} مكوّنًا · {e} علاقة استيراد', '{r} regions · {c} components · {e} import links'],
  targetCount: ['{r} طبقات · {c} مكوّنًا · {e} علاقة', '{r} layers · {c} components · {e} links'],
  focusComponent: ['ركّز على مكوّن…', 'Focus a component…'],
  findComponent: ['ابحث عن مكوّن', 'Find a component'],
  zoom: ['التكبير', 'Zoom'],
  zoomIn: ['تكبير', 'Zoom in'],
  zoomOut: ['تصغير', 'Zoom out'],
  zoomFit: ['ملاءمة الخريطة', 'Fit the map'],
  exploreMap: ['افتح الخريطة كاملة', 'Explore the full map'],
  closeMap: ['أغلق الخريطة', 'Close the map'],
  seeDetails: ['اعرض تفاصيله', 'See its details'],
  mapAria: ['خريطة المشروع اليوم: {c} مكوّنًا في {r} مناطق و{e} علاقة استيراد', 'The project today: {c} components in {r} regions and {e} import links'],
  mapAriaTarget: ['البنية المستهدفة: {c} مكوّنًا في {r} طبقات و{e} علاقة', 'The target architecture: {c} components in {r} layers and {e} links'],
  nodeAria: ['{id}، {files} ملفات، {n} مشكلة، {op}', '{id}, {files} files, {n} findings, {op}'],
  nodeAriaTarget: ['{id}، {files} ملفات، {op}، من {s} مكوّنات اليوم', '{id}, {files} files, {op}, from {s} components of today'],
  regionSub: ['{c} مكوّنات · {f} ملفًا', '{c} folders · {f} files'],
  regionSubTarget: ['{c} مكوّنات · {f} ملفًا', '{c} components · {f} files'],
  legendOps: ['اللون: العملية المخططة', 'Colour: planned operation'],
  legendFindings: ['اللون: عدد المشاكل', 'Colour: number of findings'],
  findingsWord: ['مشاكل', 'Findings'],
  sizeIsFiles: ['الحجم = الملفات', 'Size = files'],
  lineIsImports: ['سُمك الخط = الاستيرادات', 'Line weight = imports'],
  opRetain: ['يبقى', 'Keep'],
  opModify: ['يُعدَّل', 'Modify'],
  opRebuild: ['يُعاد بناؤه', 'Rebuild'],
  opDelete: ['يُحذف', 'Delete'],
  opMerge: ['يُدمج', 'Merge'],
  opIntroduce: ['يُضاف', 'Introduce'],
  component: ['مكوّن', 'Component'],
  targetComponent: ['مكوّن في البنية المستهدفة', 'Target component'],
  goesTo: ['يذهب إلى', 'Goes to'],
  mergedWith: ['يُدمج مع {n} مكوّنات أخرى', 'merged with {n} other components'],
  responsibility: ['مسؤوليته', 'Its responsibility'],
  files: ['الملفات', 'Files'],
  usedBy: ['يستورده', 'Used by'],
  uses: ['يستورد', 'Uses'],
  findings: ['المشاكل', 'Findings'],
  bySeverity: ['المشاكل بحسب الشدة', 'Findings by severity'],
  neighbourhood: ['الجوار', 'Neighbourhood'],
  egoHint: ['الرقم = عدد الاستيرادات · اضغط مكوّنًا للتركيز عليه', 'Number = imports · tap a component to focus it'],
  importsN: ['{n} استيراد', '{n} imports'],
  plannedDecision: ['القرار المخطط', 'Planned decision'],
  why: ['السبب', 'Why'],
  comesFrom: ['يأتي من', 'Comes from'],
  comesFromNone: ['لا شيء اليوم: مكوّن جديد', 'Nothing today: a new component'],
  carried: ['مشاكل تنتقل إليه', 'Findings carried'],
  openItsFindings: ['افتح مشاكله ({n})', 'Open its findings ({n})'],
  showOnTarget: ['اعرضه في الهدف', 'Show it in the target'],
  itsPaths: ['مسارات الكود التي تمرّ به', 'Code paths through it'],
  showOnToday: ['اعرضه في خريطة اليوم', 'Show it on today’s map'],
  chooseOnMap: ['اختر مكوّنًا على الخريطة لترى جواره ومشاكله وقراره.', 'Choose a component on the map to see its neighbours, findings and decision.'],
  allComponents: ['كل المكوّنات', 'All components'],
  bySeverityWeight: ['مرتبة بوزن الشدة', 'by severity weight'],
  land: ['أرض المشروع', 'Land of the project'],
  landUnit: ['{e} علاقة استيراد بين المكوّنات', '{e} import links between components'],
  landSub: ['{c} مكوّنًا في {r} مناطق', '{c} components in {r} regions'],
  region: ['المنطقة', 'Region'],
  componentsShort: ['مكوّنات', 'Comp.'],
  filesShort: ['ملفات', 'Files'],
  findingsShort: ['مشاكل', 'Findings'],
  openMap: ['افتح الخريطة', 'Open the map'],
  journey: ['من اليوم إلى الهدف', 'From today to the target'],
  inComponents: ['بالمكوّنات', 'in components'],
  componentsInCode: ['مكوّنًا في الكود', 'components in the code'],
  componentsChange: ['مكوّنًا يتغيّر', 'components change'],
  componentsInTarget: ['مكوّنًا في البنية المستهدفة', 'components in the target'],
  stayAsIs: ['تبقى كما هي', 'stay as they are'],
  targetProposed: ['مقترح، بانتظار اعتماده', 'Proposed, waiting for approval'],
  targetApproved: ['معتمد', 'Approved'],
  introducedN: ['{n} جديد', '{n} new'],
  mergesN: ['{n} يجمع أكثر من مكوّن', '{n} merge several'],
  twoMaps: ['اليوم والهدف جنبًا إلى جنب', 'Today and the target side by side'],
  twoMapsHint: ['اختر مكوّنًا في إحدى الخريطتين: يظهر ما يقابله في الأخرى.', 'Choose a component on either map: its counterpart lights up on the other.'],
  gapList: ['ما يتغيّر، مكوّنًا مكوّنًا', 'What changes, component by component'],
  gapCount: ['{n} مكوّنًا يتغيّر', '{n} components change'],
  notMeasured: ['لم يُقس', 'not measured'],
  noMap: ['لا توجد خريطة في هذا التقرير', 'This report has no map'],
  noMapSub: ['الخريطة تُبنى من نتائج الفحص (البنية المستهدفة والاستيرادات). أعد الفحص بنسخة EAOS أحدث لتظهر.', 'The map is built from the scan’s structure and imports. Check the project again with a newer EAOS to see it.'],
  capped: ['تعرض الخريطة أكبر {n} مكوّنًا.', 'The map shows the largest {n} components.'],
  more: ['و{n} أخرى', 'and {n} more'],
  showAll: ['اعرض كل العمليات', 'Show every operation'],
} satisfies Record<string, readonly [string, string]>

export type MapWord = keyof typeof MAP_WORDS

export const OP_WORD: Record<Operation, MapWord> = {
  retain: 'opRetain', modify: 'opModify', rebuild: 'opRebuild', delete: 'opDelete', merge: 'opMerge', introduce: 'opIntroduce',
}

/** A table of words in the current language, with {name} placeholders filled in (numbers in the page's digits). */
export function useWordTable<K extends string>(table: Record<K, readonly [string, string]>) {
  const { lang, num } = usePrefs()
  const index = lang === 'ar' ? 0 : 1
  return (key: K, vars?: Record<string, string | number>) =>
    table[key][index].replace(/\{(\w+)\}/g, (_, name: string) => {
      const value = vars?.[name]
      return value === undefined ? '' : typeof value === 'number' ? num(value) : value
    })
}

/** The maps' words in the current language. */
export function useMapWords() {
  return useWordTable(MAP_WORDS)
}
