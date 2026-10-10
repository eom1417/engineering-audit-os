// Presentation names for EAOS's known registries and runners. Technical names and evidence remain available.
import type { Pipeline, Stage } from './model'
const stages: Record<string, [string, string]> = {
  facts: ['استخراج الحقائق', 'Extract facts'], engines: ['تشغيل أدوات الفحص', 'Run analyzers'], features: ['فهم الخصائص', 'Read features'],
  load: ['قياس الحمل', 'Measure load'], measure: ['قياس المؤشرات', 'Measure indicators'], policy: ['فحص القواعد', 'Check policy'],
  verify: ['التحقق من النتائج', 'Verify results'], intake: ['فهم الطلب', 'Read request'], lock: ['حماية السلوك', 'Lock behavior'],
  claims: ['تجميع الأدلة', 'Collect evidence'], probe: ['فحص إضافي', 'Run probes'], semantic: ['تحليل بالذكاء', 'AI analysis'],
  sustainability: ['فحص الاستدامة', 'Check sustainability'], plan: ['إعداد الخطة', 'Build plan'], transform: ['تخطيط التغيير', 'Plan changes'],
  executive: ['ملخص تنفيذي', 'Executive summary'], execution_guide: ['دليل التنفيذ', 'Execution guide'], target: ['تصميم الهدف', 'Design target'],
  compose: ['تجميع المخرجات', 'Compose outputs'], ideal: ['تخطيط المثالي بالذكاء', 'AI ideal planning'], reports: ['إعداد التقارير', 'Write reports'], bundles: ['تجهيز الحزم', 'Build bundles'],
  emit: ['إخراج الملفات', 'Emit artifacts'], site: ['بناء العرض', 'Build report site'], validate: ['فحص المخرجات', 'Validate outputs'],
  pdf: ['تصدير PDF', 'Export PDF'], quality: ['قياس الجودة', 'Check quality'], RUNNERS: ['توزيع المراحل', 'Route stages'],
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
