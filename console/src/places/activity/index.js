// Activity (builder A): S-11 Activity, S-14 All runs, S-15 one run, S-12 the check preview, S-13 More work and every
// action, S-16 one stage. Outlines until ported from the prototype's screens/activity.js (console/PORTING.md).
import { outline, outlineSheet } from 'eaos';

outline({ id: 'S-11', path: '/activity', place: 'activity', title: 'nav.activity', features: 'RUN-01, RUN-02, RUN-08, CHK-07, CHK-08, CHK-12, ACT-01' });
outline({ id: 'S-14', path: '/activity/runs', place: 'activity', title: 'ac.runs.title', features: 'RUN-03, SRC-03' });
outline({ id: 'S-15', path: '/activity/run/:id', place: 'activity', title: 'nav.activity', features: 'RUN-04..12, CHK-07, CHK-08, CHK-11, FIX-07, FIX-10, FIX-16, SCR-04, CHT-05, AST-03, BLD-03, BLD-04' });
outlineSheet('check', 'nav.activity', 'CHK-01..06, SGN-01, SGN-02, SGN-08, DEC-05');
outlineSheet('launcher', 'st.opt.title', 'PRJ-08, RUN-13, APP-01..03, BLD-01..03, FIX-14, FIX-16');
outlineSheet('action', 'st.opt.title', 'RUN-13, FIX-14, FIX-16, APP-01..03');
outlineSheet('stage', 'nav.activity', 'CHK-09');
outlineSheet('redo', 'nav.activity', 'CHK-10');
outlineSheet('stop', 'nav.activity', 'RUN-08');
