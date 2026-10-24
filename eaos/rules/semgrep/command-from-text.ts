const { exec, execSync, execFile } = require('node:child_process');
const child_process = require('child_process');

function check(host: string, name: string) {
  // ruleid: eaos.security.command-from-text-js
  exec('ping -c 1 ' + host, () => {});
  // ruleid: eaos.security.command-from-text-js
  execSync(`git log --author=${name}`);
  // ruleid: eaos.security.command-from-text-js
  child_process.exec('ls ' + host);
  // ok: eaos.security.command-from-text-js
  execFile('ping', ['-c', '1', host], () => {});
  // ok: eaos.security.command-from-text-js
  exec('npm run build', () => {});
  // ok: eaos.security.command-from-text-js
  /^(\d+)-/.exec('order-' + name);
}
