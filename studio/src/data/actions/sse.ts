// A Server-Sent Events reader over fetch: EventSource cannot send the launch token as a header. Frames are split on
// blank lines (CRLF, CR or LF), comments (": ping") are skipped, and a frame split across chunks waits for the rest.

export interface Frame { id?: string; event: string; data: string }

export function parseFrame(block: string): Frame | null {
  const out: Frame = { event: 'message', data: '' }
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const at = line.indexOf(':')
    const field = at < 0 ? line : line.slice(0, at)
    const value = at < 0 ? '' : line.slice(at + 1).replace(/^ /, '')
    if (field === 'id') out.id = value
    else if (field === 'event') out.event = value
    else if (field === 'data') data.push(value)
  }
  out.data = data.join('\n')
  return data.length || out.id !== undefined ? out : null
}

/** Feeds text chunks in, gets whole frames out. */
export function frameSplitter(onFrame: (frame: Frame) => void) {
  let buffer = ''
  return (chunk: string) => {
    buffer += chunk
    const held = buffer.endsWith('\r') ? '\r' : '' // a \r\n split across two chunks
    let text = (held ? buffer.slice(0, -1) : buffer).replace(/\r\n?/g, '\n')
    let end: number
    while ((end = text.indexOf('\n\n')) >= 0) {
      const frame = parseFrame(text.slice(0, end))
      text = text.slice(end + 2)
      if (frame) onFrame(frame)
    }
    buffer = text + held
  }
}
