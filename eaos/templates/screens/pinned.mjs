// The tools EAOS pinned, loaded from the folder it installed each in (ES modules ignore NODE_PATH), never the project's.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

export const fromFolder = (folder) => createRequire(join(folder, 'eaos-resolve.js'));

// The pinned Playwright: its own package, else the one @playwright/test brings.
export function playwrightFrom(folder) {
  const require = fromFolder(folder);
  try { return require('playwright'); } catch { return require('@playwright/test'); }
}

// A helper's config (the JSON file named by its first argument) and the pinned Playwright it names.
/** A JSON file of the run, read and parsed. */
export const readJson = file => JSON.parse(readFileSync(file, 'utf8'));

export function configured() {
  const config = readJson(process.argv[2]);
  return { config, playwright: playwrightFrom(config.modules.playwright) };
}
