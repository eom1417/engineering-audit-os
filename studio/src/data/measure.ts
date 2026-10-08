// A number the Studio shows, with the file and field (or the formula) it comes from; null when it was not measured.
export interface Measure { value: number | null; src: string; unit?: string }
