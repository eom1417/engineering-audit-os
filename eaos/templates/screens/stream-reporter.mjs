// Copied by EAOS into the lock folder (eaos/behavior_lock.py): a Playwright reporter that writes one JSON line per
// test as it begins and ends, to the file named by its `outputFile` option (EAOS_LOCK_STREAM), so the live map shows
// each screen as it is recorded instead of waiting for the run's JSON report. It uses the documented reporter API
// (onBegin, onTestBegin, onTestEnd, onEnd) and never fails the run: a line it cannot write is left out.
//
//   {"event":"plan","files":{"playwright/home.spec.ts":2}}            the spec files and how many tests each holds
//   {"event":"test.begin","file":"playwright/home.spec.ts","title":"..."}
//   {"event":"test.end","file":"...","title":"...","status":"passed","duration":812,"error":"","shots":["home.spec.ts/home.png"]}
//   {"event":"end","status":"passed"}
//
// `file` is relative to the config's folder; `shots` are the screen snapshots of that spec file, relative to the
// snapshot folder (`__screenshots__`, the config's snapshotPathTemplate).
import fs from 'node:fs';
import path from 'node:path';

export default class StreamReporter {
  constructor(options = {}) {
    this.file = options.outputFile || process.env.EAOS_LOCK_STREAM || '';
    this.root = process.cwd();
  }

  write(row) {
    if (!this.file) return;
    try { fs.appendFileSync(this.file, JSON.stringify({ at: Date.now(), ...row }) + '\n'); } catch { /* never fail the run */ }
  }

  name(test) {
    return path.relative(this.root, test.location.file).split(path.sep).join('/');
  }

  shots(test) {
    try {
      const testDir = test.parent.project().testDir;
      const snapshots = path.join(testDir, '..', '__screenshots__');
      const folder = path.join(snapshots, path.relative(testDir, test.location.file));
      return fs.readdirSync(folder).filter((name) => name.endsWith('.png')).sort().slice(0, 5)
        .map((name) => path.relative(snapshots, path.join(folder, name)).split(path.sep).join('/'));
    } catch {
      return [];
    }
  }

  onBegin(config, suite) {
    this.root = config.configFile ? path.dirname(config.configFile) : config.rootDir;
    const files = {};
    for (const test of suite.allTests()) files[this.name(test)] = (files[this.name(test)] || 0) + 1;
    this.write({ event: 'plan', files });
  }

  onTestBegin(test) {
    this.write({ event: 'test.begin', file: this.name(test), title: test.title });
  }

  onTestEnd(test, result) {
    this.write({ event: 'test.end', file: this.name(test), title: test.title, status: result.status,
                 duration: result.duration, error: ((result.error && result.error.message) || '').replace(/\u001b\[[0-9;]*m/g, '').slice(0, 300),
                 shots: this.shots(test) });
  }

  onEnd(result) {
    this.write({ event: 'end', status: result.status });
  }

  printsToStdio() {
    return false;
  }
}
