// One line of JSON per event, with the release it came from: what the host's log collector reads.
const RELEASE = process.env.RELEASE || 'dev';

const logger = {
  info: (event, detail = {}) => console.log(JSON.stringify({ level: 'info', event, release: RELEASE, ...detail })),
  error: (event, detail = {}) => console.error(JSON.stringify({ level: 'error', event, release: RELEASE, ...detail })),
};

module.exports = { logger };
