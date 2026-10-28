// The discounts of the season, read from their file.
import { readFile } from 'node:fs/promises';

export async function discounts() {
  return JSON.parse(await readFile(new URL('./prices.json', import.meta.url), 'utf8'));
}
