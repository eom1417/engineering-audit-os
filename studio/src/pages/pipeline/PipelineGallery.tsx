// #/_gallery/pipeline: the pipeline map's fixture in the gallery (STUDIO-COMPLETE: a gallery fixture per map): the
// map in its three views, the steps, a router's inspector and the gap, on the contract fixture
// (tests/fixtures/studio/v2/pipeline.json, EAOS itself), so the gates check them without a report.
import { useMemo, useState } from 'react'
import { Panel, Section } from '../../components/Panel'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import fixture from './fixture.json'
import { Flowchart } from './Flowchart'
import { GapPanel, StageInspector } from './Inspector'
import { firstPipeline, scopeOf, VIEWS, type PipelineData } from './model'
import { StepList } from './Steps'
import { usePipelineWords, VIEW_WORD } from './words'
import frame from '../paths/paths.module.css'

const DATA = fixture as unknown as PipelineData

export function PipelineGalleryPage() {
  const w = usePipelineWords()
  usePageChrome(w('galleryPipeline'))
  const scope = useMemo(() => scopeOf(DATA, firstPipeline(DATA)!)!, [])
  const router = scope.stages.find((s) => s.kind === 'router')?.id
  const [stage, setStage] = useState<string | undefined>(router)
  return (
    <div className={layout.page}>
      <PageTitle title={w('galleryPipeline')} lead={w('galleryPipelineLead')} />
      {VIEWS.map((view) => (
        <Section key={view} title={`${w('asMap')} · ${w(VIEW_WORD[view])}`}>
          <Panel className={frame.galleryFrame}>
            <Flowchart scope={scope} view={view} down={false} selected={stage} onSelect={setStage} hidden={view === 'current'} label={`${scope.pipeline.title} · ${w(VIEW_WORD[view])}`} />
          </Panel>
        </Section>
      ))}
      <Section title={w('asSteps')}><Panel pad><StepList scope={scope} view="gap" selected={stage} onSelect={setStage} first={8} /></Panel></Section>
      {stage && <Section title={w('inspector')}><Panel pad><StageInspector data={DATA} scope={scope} id={stage} view="gap" onSelect={setStage} onEnter={() => {}} onFollow={() => {}} /></Panel></Section>}
      <Section title={w('gap')}><Panel pad><GapPanel data={DATA} scope={scope} onSelect={setStage} /></Panel></Section>
    </div>
  )
}
