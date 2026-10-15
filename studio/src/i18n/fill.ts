// The one function that writes a sentence's numbers, for the catalog (prefs t) and every page's word table.

/** A sentence with its {name} placeholders filled (numbers through `format`), and each {name:singular|plural} word
 * agreeing with the number `name`: Arabic counts three to ten with the plural ("7 مشاكل"), every other count with the
 * singular ("11 مشكلة"). A placeholder without a value is left out. */
export function fill(text: string, vars: Record<string, string | number> | undefined, format: (n: number) => string): string {
  return text.replace(/\{(\w+)(?::([^|}]*)\|([^}]*))?\}/g, (_, name: string, one: string | undefined, few: string) => {
    const value = vars?.[name]
    if (one !== undefined) return typeof value === 'number' && value % 100 >= 3 && value % 100 <= 10 ? few : one
    return value === undefined ? '' : typeof value === 'number' ? format(value) : value
  })
}
