// Server-sent events read with fetch (EventSource cannot send the launch token as a header). Frames are split on
// blank lines (CRLF, CR or LF), comments (": ping") are skipped and a frame split across chunks waits for the rest.
// A dropped stream reconnects with Last-Event-ID, so the server replays exactly what was missed (or says `reset`).
import { token } from './source.js';

export function parseFrame(block) {
  const out = { event: 'message', data: '' };
  const data = [];
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue;
    const at = line.indexOf(':');
    const field = at < 0 ? line : line.slice(0, at);
    const value = at < 0 ? '' : line.slice(at + 1).replace(/^ /, '');
    if (field === 'id') out.id = value;
    else if (field === 'event') out.event = value;
    else if (field === 'data') data.push(value);
  }
  out.data = data.join('\n');
  return data.length || out.id !== undefined ? out : null;
}

/** Feeds text chunks in, gets whole frames out. */
export function frameSplitter(onFrame) {
  let buffer = '';
  return chunk => {
    buffer += chunk;
    const held = buffer.endsWith('\r') ? '\r' : '';
    let text = (held ? buffer.slice(0, -1) : buffer).replace(/\r\n?/g, '\n');
    let end;
    while ((end = text.indexOf('\n\n')) >= 0) {
      const frame = parseFrame(text.slice(0, end));
      text = text.slice(end + 2);
      if (frame) onFrame(frame);
    }
    buffer = text + held;
  };
}

const wait = ms => new Promise(done => setTimeout(done, ms));

/**
 * Follows the stream at `path` until the returned function is called, or `onFrame` returns 'end'.
 * `last`: the id to resume after (Last-Event-ID). `onStatus`: connecting | open | reconnecting | refused | closed.
 * `onBeat`: anything arrived, an event or the server's keep-alive.
 */
export function follow(path, { last = null, onFrame, onStatus = () => {}, onBeat = () => {} }) {
  let stopped = false, ended = false, controller = null;
  async function run() {
    let delay = 500;
    while (!stopped && !ended) {
      controller = new AbortController();
      try {
        const headers = { 'X-EAOS-Token': token, Accept: 'text/event-stream' };
        if (last) headers['Last-Event-ID'] = String(last);
        const answer = await fetch(path, { headers, cache: 'no-store', credentials: 'same-origin', signal: controller.signal });
        if (answer.status === 401 || answer.status === 404) { onStatus(answer.status === 401 ? 'refused' : 'closed'); return; }
        if (!answer.ok || !answer.body) throw new Error(`stream: ${answer.status}`);
        onStatus('open');
        delay = 500;
        const reader = answer.body.pipeThrough(new TextDecoderStream()).getReader();
        const feed = frameSplitter(frame => {
          if (frame.id) last = frame.id;
          if (onFrame(frame) === 'end') ended = true;
        });
        for (;;) {
          const { value, done } = await reader.read();
          if (done || ended) break;
          onBeat();
          feed(value);
        }
      } catch (e) {
        if (stopped) return;
      }
      if (stopped || ended) break;
      onStatus('reconnecting');
      await wait(delay);
      delay = Math.min(delay * 2, 8000);
    }
    if (!stopped) onStatus('closed');
  }
  onStatus('connecting');
  run();
  return () => { stopped = true; if (controller) controller.abort(); };
}
