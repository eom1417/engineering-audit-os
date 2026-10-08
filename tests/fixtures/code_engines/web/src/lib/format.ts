export type Vehicle = { id: number; plate: string };

export function plate(text: string) {
  return text.toUpperCase();
}

export function unusedFormat(text: string) {
  return text.trim();
}
