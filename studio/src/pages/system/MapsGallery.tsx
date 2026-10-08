// The gallery's fixture of the journeys map and the visible and hidden lens (STUDIO-COMPLETE: a gallery fixture per
// map): a small app built by eaos/studio/journeys.py and hidden.py from tests/test_studio_journeys.py's report
// (fixture.json; tests/fixtures/studio/v2/journeys.json and hidden.json are the same data with their envelope).
import type { Hidden, Journeys } from '../../data/journeys'
import fixture from './fixture.json'
import { HiddenMap } from './hidden/HiddenMap'
import { JourneyMap } from './journeys/JourneyMap'
import { Legend } from './journeys/parts'
import css from './journeys/Journeys.module.css'

export const MAP_FIXTURE = fixture as unknown as { journeys: Journeys; hidden: Hidden }

export function JourneysFixture({ mode, task, hidden }: { mode: 'current' | 'change' | 'target'; task?: boolean; hidden?: boolean }) {
  const j = MAP_FIXTURE.journeys
  return (
    <figure className={css.preview}>
      <JourneyMap journeys={j} mode={mode} variant="full" showHidden={Boolean(hidden)} task={task ? j.tasks.find((t) => t.path.length > 2) : undefined} className={css.fixtureSvg} />
      <figcaption className={css.cap}><Legend mode={mode} showHidden={Boolean(hidden)} /></figcaption>
    </figure>
  )
}

export function HiddenFixture() {
  return <figure className={css.preview}><HiddenMap hidden={MAP_FIXTURE.hidden} variant="full" showHidden className={css.fixtureSvg} /></figure>
}
