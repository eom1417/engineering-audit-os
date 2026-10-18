// S-04 Sign in to your app (builder A): SGN-03, SGN-04, SGN-05, SGN-07. An outline until ported from the prototype's
// screens/waiting.js (its second half) on /api/sign-in (console/PORTING.md).
import { outline, outlineSheet } from 'eaos';

outline({ id: 'S-04', path: '/waiting/sign-in', place: 'waiting', title: 'ac.si.title', features: 'SGN-03, SGN-04, SGN-05, SGN-07' });
outlineSheet('signin-skip', 'ac.si.skip.title', 'SGN-05');
