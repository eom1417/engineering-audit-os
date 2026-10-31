// What became of the report's rebuild, which is work that waits its turn (open_report): only a run that ended done
// rebuilt it. Nothing here touches the page, so tests/interfaces/test_report_opening.py runs it under Node.
const TRIES = 60;
const HALF_A_SECOND = 500;
export const OPENED_WORDS = { done: 'un.files.opened', not_rebuilt: 'un.files.not_rebuilt', waiting: 'un.files.may_be_outdated' };

const pauseOf = () => new Promise(done => setTimeout(done, HALF_A_SECOND));

/** 'done', 'not_rebuilt' (it ended failed, stopped or unchanged) or 'waiting' (it had not ended within half a minute). */
export async function rebuildOutcome(client, run, terminal, pause = pauseOf) {
  for (let tries = 0; tries < TRIES; tries++) {
    const { state } = await client.run(run.id);
    if (terminal.includes(state)) return state === 'done' ? 'done' : 'not_rebuilt';
    if (tries < TRIES - 1) await pause();
  }
  return 'waiting';
}
