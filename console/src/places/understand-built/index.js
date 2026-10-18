// Understand, How it is built (builder B): S-24/S-25 components, S-26/S-27 code paths, S-28/S-29 functions, S-30/S-31
// data, S-32 seen and unseen, S-33 infrastructure, S-34 pipelines, S-35 architecture. Outlines until ported from the
// prototype's screens/understand.js (console/PORTING.md).
import { outline, outlineSheet } from 'eaos';

const o = (id, path, title, features) => outline({ id, path, place: 'understand', title, features });
o('S-24', '/understand/components', 'un.v.components', 'SYS-01, SYS-03, SYS-04, SYS-18');
o('S-25', '/understand/components/:id', 'un.v.components', 'SYS-02');
o('S-26', '/understand/paths', 'un.v.paths', 'SYS-07');
o('S-27', '/understand/paths/:id', 'un.v.paths', 'SYS-08');
o('S-28', '/understand/functions', 'un.v.functions', 'SYS-05, SRC-03');
o('S-29', '/understand/functions/:id', 'un.v.functions', 'SYS-06');
o('S-30', '/understand/data', 'un.v.data', 'SYS-09');
o('S-31', '/understand/data/:id', 'un.v.data', 'SYS-10');
o('S-32', '/understand/unseen', 'un.v.unseen', 'SYS-11');
o('S-33', '/understand/infra', 'un.v.infra', 'SYS-13');
o('S-34', '/understand/pipelines', 'un.v.pipelines', 'SYS-14, SYS-15');
o('S-35', '/understand/architecture', 'un.v.architecture', 'SYS-17');
outlineSheet('map', 'un.v.components', 'SYS-01');
outlineSheet('pstage', 'un.v.pipelines', 'SYS-15');
outlineSheet('adopt', 'un.v.architecture', 'SYS-17');
