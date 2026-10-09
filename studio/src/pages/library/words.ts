// The words of the Library and the document reader, Arabic first and English equally finished. A key missing in one
// language is a type error. A document's own text and title are shown as the report wrote them.
import { useWordTable } from '../../map/words'

export const LIBRARY_WORDS = {
  library: ['المكتبة', 'Library'],
  documents: ['الوثائق', 'Documents'],
  lead: ['كل ما كتبه EAOS عن هذا المشروع، بترتيب القراءة الذي يقترحه التقرير.', 'Everything EAOS wrote about this project, in the reading order the report suggests.'],
  counts: ['{d} وثيقة · {i} صورة ورسم', '{d} documents · {i} images and diagrams'],
  searchDocs: ['ابحث في الوثائق وعناوينها', 'Search the documents and their headings'],
  searchPlaceholder: ['اسم وثيقة أو عنوان داخلها…', 'A document or a heading inside it…'],
  allGroups: ['الكل', 'All'],
  groupFilter: ['المجموعة', 'Group'],
  group_start: ['ابدأ هنا', 'Start here'],
  group_story: ['القصة: اليوم والهدف والفجوة', 'The story: today, the target, the gap'],
  group_plan: ['خطة التنفيذ', 'The execution plan'],
  group_PLAN: ['مهام الخطة', 'Plan tasks'],
  group_adr: ['قرارات البنية', 'Architecture decisions'],
  group_technical: ['الملاحق التقنية', 'Technical appendices'],
  group_handover: ['حزمة التسليم', 'Handover kit'],
  readFirst: ['اقرأ أولًا', 'Read first'],
  readFirstLead: ['الوثائق الأساسية بالترتيب الذي يقترحه فهرس التقرير.', "The main documents, in the order the report's index suggests."],
  minRead: ['{n} د', '{n} min'],
  minReadAria: ['{n} دقيقة قراءة', '{n} minutes to read'],
  results: ['{n} نتيجة', '{n} results'],
  noMatch: ['لا وثيقة تطابق هذا البحث. جرّب كلمة أقصر.', 'No document matches. Try a shorter word.'],
  inSection: ['في القسم:', 'In:'],
  images: ['الصور والرسوم', 'Images and diagrams'],
  noDocs: ['لم يكتب هذا الفحص وثائق بعد', 'This check wrote no documents yet'],
  noDocsSub: ['تظهر الوثائق هنا بعد أن يكتب EAOS تقريره عن المشروع.', 'The documents appear here once EAOS writes its report on the project.'],
  // reader
  contents: ['المحتويات', 'Contents'],
  onThisPage: ['في هذه الوثيقة', 'On this page'],
  next: ['التالي في ترتيب القراءة', 'Next in reading order'],
  previous: ['السابق', 'Previous'],
  inGroup: ['ضمن: {g}', 'In: {g}'],
  reportPath: ['في مجلد التقرير', 'In the report folder'],
  loadingText: ['أحمّل نص الوثيقة…', 'Loading the text…'],
  textMissing: ['نص هذه الوثيقة ليس في بيانات الاستوديو', 'The text of this document is not in the Studio data'],
  textMissingSub: ['تجدها في مجلد التقرير. يحمل الاستوديو نصوص الوثائق ابتداءً من هذا الإصدار من EAOS: افحص المشروع من جديد ليصل النص.',
    'It is in the report folder. The Studio carries the documents’ text from this version of EAOS on: check the project again to bring it here.'],
  truncated: ['الوثيقة طويلة: يظهر هنا أول {n} حرف، ونصها كاملًا في مجلد التقرير.', 'A long document: the first {n} characters are shown here; the whole text is in the report folder.'],
  notFound: ['لا وثيقة بهذا الاسم في التقرير', 'No document by that name in the report'],
  notFoundSub: ['ربما كُتب الرابط لفحص أقدم. ارجع إلى المكتبة لترى وثائق هذا الفحص.', 'The link may come from an older check. Go back to the Library to see the documents of this one.'],
  backToLibrary: ['ارجع إلى المكتبة', 'Back to the Library'],
  tableN: ['جدول {n}', 'Table {n}'],
  codeN: ['كود {n}', 'Code {n}'],
  diagramSource: ['مصدر رسم Mermaid', 'Mermaid diagram source'],
  diagramNote: ['يرسم الاستوديو بنية المشروع بنفسه من الحقائق نفسها؛ هنا مصدر الرسم كما كتبه التقرير.', "The Studio draws the project's structure itself from the same facts; here is the diagram source as the report wrote it."],
  // images
  image: ['صورة', 'Image'],
  kind_diagram: ['رسم', 'Diagram'],
  kind_screen: ['صورة', 'Image'],
  kind_chart: ['مخطط', 'Chart'],
  openMap: ['افتح الرسم في الاستوديو', 'Open the drawing in the Studio'],
  mapToday: ['خريطة النظام اليوم', 'The system map today'],
  mapTarget: ['البنية المستهدفة على الخريطة', 'The target on the map'],
  mapJourneys: ['خريطة الصفحات والرحلات', 'The pages and journeys map'],
  imageMissing: ['محتوى هذه الصورة ليس في بيانات الاستوديو', 'The content of this image is not in the Studio data'],
  imageTooLarge: ['الصورة أكبر من أن تُحمل في الاستوديو ({n} كيلوبايت)؛ تجدها في مجلد التقرير.', 'The image is too large to carry in the Studio ({n} kB); it is in the report folder.'],
  imageNotFound: ['لا صورة بهذا الاسم في التقرير', 'No image by that name in the report'],
  noImages: ['لا صور ولا رسوم في هذا الفحص', 'No images or diagrams in this check'],
  lines: ['{n} سطرًا', '{n} lines'],
} as const

export type LibraryWord = keyof typeof LIBRARY_WORDS

export function useLibraryWords() {
  return useWordTable(LIBRARY_WORDS)
}

/** A document group's words: the known groups by name, any other by its folder. */
export function groupWord(w: ReturnType<typeof useLibraryWords>, group: string): string {
  const key = `group_${group}` as LibraryWord
  return key in LIBRARY_WORDS ? w(key) : group
}
