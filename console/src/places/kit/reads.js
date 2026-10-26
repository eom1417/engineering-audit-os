// The answers of EAOS's reading actions a view shows (impact, structure, design_brief): asked once per check and
// inputs (POST /api/runs answers a reading action at once, run.result.answer), kept for the page, asked again after a
// new check. Live only: the read-only copy has no server to ask.
import { client, data, refresh, ActionError } from 'eaos';

const answers = new Map();
const stamp = () => { const m = data.manifest(); return m && m.built ? m.built.digest : ''; };

/** {state: 'ready' | 'loading' | 'failed' | 'offline', answer, error} of `action` with `inputs`; the view redraws
 *  when it arrives. */
export function read(action, inputs) {
  if (!client) return { state: 'offline' };
  const key = `${stamp()}\u0001${action}\u0001${JSON.stringify(inputs || {})}`;
  if (!answers.has(key)) {
    const entry = { state: 'loading' };
    answers.set(key, entry);
    client.start({ action, inputs: inputs || {} }).then(run => {
      const result = run.result || {};
      Object.assign(entry, run.state === 'done' ? { state: 'ready', answer: result.answer } : { state: 'failed', error: run.error || run.state });
    }, e => Object.assign(entry, { state: 'failed', error: e instanceof ActionError ? e.message : String(e) }))
      .then(() => refresh());
  }
  return answers.get(key);
}
