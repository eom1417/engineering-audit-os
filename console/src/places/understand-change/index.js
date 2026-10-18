// Understand, Change and target (builder B): S-18 the story, S-19/S-20 gaps, S-21 operations, S-22 the ideal target,
// S-23 how EAOS decided. Outlines until ported from the prototype's screens/understand.js (console/PORTING.md).
import { outline, outlineSheet } from 'eaos';

const o = (id, path, title, features) => outline({ id, path, place: 'understand', title, features });
o('S-18', '/understand/story', 'un.v.story', 'PLN-01, PLN-10, PLN-13');
o('S-19', '/understand/gaps', 'un.v.gaps', 'PLN-07');
o('S-20', '/understand/gaps/:id', 'un.v.gaps', 'PLN-08');
o('S-21', '/understand/operations', 'un.v.operations', 'PLN-09');
o('S-22', '/understand/ideal', 'un.v.ideal', 'PLN-11, PLN-12, PLN-13');
o('S-23', '/understand/ai-decisions', 'un.v.ai-decisions', 'SYS-16');
outlineSheet('op', 'un.v.operations', 'PLN-09');
outlineSheet('replan', 'un.v.ideal', 'PLN-12');
outlineSheet('node', 'un.v.ai-decisions', 'SYS-16');
outlineSheet('runnodes', 'un.v.ai-decisions', 'SYS-16');
