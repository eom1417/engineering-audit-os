/** A number the Studio shows: its value and where it comes from. Not measured is null, never 0. */
export interface Measure { value: number | null; src: string; unit?: string }
