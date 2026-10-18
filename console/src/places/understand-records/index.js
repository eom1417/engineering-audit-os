// Understand, Records (builder B): S-40 the library, S-41 one document, S-42 report files, S-43 checks over time,
// S-44 one past check, S-45 compare two checks. Outlines until ported from the prototype's screens/understand.js
// (console/PORTING.md).
import { outline, outlineSheet } from 'eaos';

const o = (id, path, title, features) => outline({ id, path, place: 'understand', title, features });
o('S-40', '/understand/library', 'un.v.library', 'LIB-01, LIB-02, LIB-06');
o('S-41', '/understand/library/:doc', 'un.v.library', 'LIB-03, LIB-04, LIB-05');
o('S-42', '/understand/report-files', 'un.v.report-files', 'LIB-07');
o('S-43', '/understand/history', 'un.v.history', 'HIS-01..05');
o('S-45', '/understand/history/compare', 'un.cmp.title', 'HIS-07');
o('S-44', '/understand/history/:check', 'un.v.history', 'HIS-06');
outlineSheet('diagram', 'un.v.library', 'LIB-05');
outlineSheet('file', 'un.v.report-files', 'LIB-07');
