// #/_gallery/paths: the code paths' fixture in the gallery (STUDIO-COMPLETE: a gallery fixture per map). Every view of
// the diagram, the overview, the sequence, the steps, a gap's inspector and the plan timeline, on the contract
// fixture (tests/fixtures/studio/v2/paths.json), so the gates check them without a report.
import { useMemo, useState } from 'react'
import { Panel, Section } from '../../components/Panel'
import { usePrefs } from '../../i18n/prefs'
import { usePageChrome } from '../../shell/chrome'
import { layout, PageTitle } from '../../shell/Layout'
import { drawOverview, drawPath } from './draw'
import { PATHS_FIXTURE } from './fixture'
import { NodeInspector } from './Inspector'
import { Lanes } from './Lanes'
import { indexOf, PATH_MODES } from './model'
import { SequenceDiagram, StepList } from './Sequence'
import { Grid, TaskRows } from './TimelinePage'
import { MODE_WORD, usePathWords } from './words'
import css from './paths.module.css'

export function PathsGalleryPage() {
  const w = usePathWords()
  const { t } = usePrefs()
  usePageChrome(w('galleryPaths'))
  const data = PATHS_FIXTURE
  const index = useMemo(() => indexOf(data), [data])
  const path = data.paths[0]
  const [node, setNode] = useState<string | undefined>('G:endpoint:POST /api/audit')
  const overview = drawOverview(data, 'change', w)
  const timeline = data.timeline!
  return (
    <div className={layout.page}>
      <PageTitle title={w('galleryPaths')} lead={w('galleryPathsLead')} />
      {PATH_MODES.map((mode) => {
        const drawn = drawPath(data, index, path, mode, w, false)
        return (
          <Section key={mode} title={`${w('asDiagram')} · ${w(MODE_WORD[mode])}`}>
            <Panel className={css.galleryFrame}>
              <Lanes columns={path.columns} nodes={drawn.nodes} edges={drawn.edges} mode={mode} selected={node} onSelect={setNode}
                label={w('diagramAria', { t: path.title, n: path.columns.flat().length, l: 7, g: path.gaps })} />
            </Panel>
          </Section>
        )
      })}
      <Section title={w('overview')}>
        <Panel className={css.galleryFrame}>
          <Lanes columns={data.overview.columns} nodes={overview.nodes} edges={overview.edges} mode="change" onSelect={() => {}} label={w('overviewAria', { n: data.overview.clusters.length })} />
        </Panel>
      </Section>
      <Section title={w('asSequence')}><Panel><SequenceDiagram data={data} index={index} path={path} selected={node} onSelect={setNode} /></Panel></Section>
      <Section title={w('asSteps')}><Panel pad><StepList data={data} index={index} path={path} selected={node} onSelect={setNode} /></Panel></Section>
      {node && <Section title={t('inspector')}><Panel pad><NodeInspector data={data} index={index} id={node} path={path} /></Panel></Section>}
      <Section title={w('planTimeline')}>
        <Grid timeline={timeline} step="M01" wave={2} onPick={() => {}} />
        <Panel pad><TaskRows tasks={timeline.tasks} /></Panel>
      </Section>
    </div>
  )
}
