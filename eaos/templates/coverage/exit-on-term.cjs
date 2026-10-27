// Loaded by Node before an app EAOS starts with coverage on (NODE_OPTIONS=--require, eaos/live/testing/ran.py): a SIGTERM
// ends the process through process.exit, so Node writes the V8 coverage of what ran; it writes none for a process a
// signal ends.
process.once('SIGTERM', () => process.exit(0));
