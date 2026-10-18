// The action contract the console is built against: docs/studio-actions.json itself, bundled at build time (its bytes
// are part of the source fingerprint, scripts/build.mjs). Only the parts the screens read are kept by the build.
import { actions, verbs, lifecycle, snapshot } from '../../../docs/studio-actions.json';

export const ACTIONS = actions;
export const VERBS = verbs;
export const STATE_WORDS = lifecycle.states;
export const SNAPSHOT = snapshot;

const BY_ID = new Map(actions.map(a => [a.id, a]));
export const actionOf = id => BY_ID.get(id);
export const verbOf = id => verbs.find(v => v.id === id);
/** The inputs the person fills in: every input but `project`, which the console fills with the project it serves. */
export const personInputs = action => Object.entries((action.inputs && action.inputs.properties) || {}).filter(([name]) => name !== 'project');
