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
export function configured() {
  const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
  return { config, playwright: playwrightFrom(config.modules.playwright) };
}
