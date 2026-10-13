// What every SVG map of the Studio shares: text cut to the room of its box.

/** "…/tail" of a long identifier for a fixed-width box: it keeps its end (the full value goes in the title). */
export function fit(text: string, room: number): string {
  return text.length <= room ? text : '…' + text.slice(-(room - 1))
}
