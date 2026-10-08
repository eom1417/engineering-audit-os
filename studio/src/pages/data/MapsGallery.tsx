// The gallery's fixture of the data paths map and the infrastructure lens (STUDIO-COMPLETE: a gallery fixture per map):
// a small shop exported by eaos/studio/data_paths.py and infra.py from tests/test_studio_data_map.py's report
// (fixture.json; tests/fixtures/studio/v2/data_paths.json and infra.json hold the same data with their envelope).
import { useState } from 'react'
import type { DataPaths, Infra } from '../../data/dataMap'
import { InfraMap } from '../infra/InfraMap'
import type { Mode } from './model'
import { DataLegend, DataMap } from './DataMap'
import fixture from './fixture.json'
import { Chain, gapSteps, TierStrip } from './parts'
import css from './Data.module.css'

const FIXTURE = fixture as unknown as { data_paths: DataPaths; infra: Infra }

export function DataFixture({ mode }: { mode: Mode }) {
  const [focus, setFocus] = useState<string | undefined>('table:stock')
  const dp = FIXTURE.data_paths
  return (
    <figure className={css.fixture}>
      <DataMap dp={dp} mode={mode} focus={focus} reads onFocus={(id) => setFocus(id === focus ? undefined : id)} className={css.fitSvg} />
      <figcaption><DataLegend mode={mode} inline /></figcaption>
    </figure>
  )
}

export function DataChainFixture() {
  const dp = FIXTURE.data_paths
  const path = dp.paths.find((p) => p.steps.handler.state === 'known') ?? dp.paths[0]
  return (
    <div className={css.fixtureCol}>
      <TierStrip dp={dp} />
      <Chain path={path} endpoint={dp.endpoints.find((e) => e.id === path.endpoint)} steps={gapSteps(dp)} />
    </div>
  )
}

export function InfraFixture({ mode }: { mode: Mode }) {
  const [focus, setFocus] = useState<string | undefined>()
  return <figure className={css.fixture}><InfraMap infra={FIXTURE.infra} mode={mode} focus={focus} onFocus={setFocus} className={css.fitSvg} /></figure>
}
