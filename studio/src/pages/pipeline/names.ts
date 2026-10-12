// Presentation names for EAOS's known registries and runners. Technical names and evidence remain available.
import type { Pipeline, Stage } from './model'
const stages: Record<string, [string, string]> = {
  facts: ['استخراج الحقائق', 'Extract facts'], engines: ['تشغيل أدوات الفحص', 'Run analyzers'], features: ['فهم الخصائص', 'Read features'],
  load: ['قياس الحمل', 'Measure load'], measure: ['قياس المؤشرات', 'Measure indicators'], policy: ['فحص القواعد', 'Check policy'],
  intake: ['فهم الطلب', 'Read request'], lock: ['حماية السلوك', 'Lock behavior'],
  claims: ['تجميع الأدلة', 'Collect evidence'], probe: ['فحص إضافي', 'Run probes'], semantic: ['تحليل بالذكاء', 'AI analysis'],
  plan: ['إعداد الخطة', 'Build plan'],
  target: ['تصميم الهدف', 'Design target'],
  triage: ['فرز البطاقات بالذكاء', 'AI card triage'], ideal: ['تخطيط المثالي بالذكاء', 'AI ideal planning'], order: ['ترتيب الخطة بالذكاء', 'AI plan order'], reports: ['إعداد التقارير', 'Write reports'], verify: ['التحقق من النتائج', 'Verify results'], sustainability: ['فحص الاستدامة', 'Check sustainability'], transform: ['تخطيط التغيير', 'Plan changes'], journeys: ['رحلات المستخدم', 'User journeys'], architecture: ['خريطة البنية', 'Architecture map'], readiness: ['الجاهزية تحت الضغط', 'Readiness under pressure'],
  RUNNERS: ['توزيع المراحل', 'Route stages'],
  setup: ['تشغيل البرنامج', 'Run the app'], record: ['تسجيل السلوك', 'Record behavior'],
  crawl: ['مسح الصفحات', 'Crawl pages'], screens: ['صور الشاشات', 'Screen pictures'], baseline: ['السرعة تحت الضغط', 'Speed under load'],
  proposals: ['اقتراحات الأدوات', 'Tool proposals'], visual: ['المراجع البصري بالذكاء', 'AI visual review'],
  cards: ['البطاقات المؤكدة', 'Confirmed cards'], pipeline_gaps: ['فجوات المسارات بالذكاء', 'AI pipeline gaps'], reconcile: ['المستهدف النهائي', 'Final target'],
  steps: ['ترتيب الخطة', 'Plan order'],
}
export function stageTitle(stage: Stage, lang: string): string {
  const name = stages[stage.label]
  return stage.entry.path?.startsWith('eaos/') && name ? name[lang === 'ar' ? 0 : 1] : stage.label
}
export function pipelineTitle(pipeline: Pipeline, lang: string): string {
  const path = pipeline.entry.path ?? ''
  const title: [string, string] | undefined = path === 'eaos/pipeline/run.py' || pipeline.id.includes('eaos/pipeline/stages.py') ? ['الفحص الرئيسي', 'Main audit']
    : pipeline.id.includes('eaos/facts/run.py') ? ['استخراج الحقائق', 'Fact extraction']
    : pipeline.id.includes('eaos/studio/nodes/') ? ['عُقد الذكاء وقراراتها', 'AI nodes and decisions']
    : pipeline.id.includes('eaos/guided.py') ? ['الجلسة الموجّهة', 'Guided session']
    : pipeline.id.includes('eaos/runtime/pipeline.py') ? ['الفحص الذي يقوده النموذج', 'Model-led audit'] : undefined
  return title ? title[lang === 'ar' ? 0 : 1] : pipeline.title
}
