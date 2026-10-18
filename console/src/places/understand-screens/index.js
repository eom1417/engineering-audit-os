// Understand, Screens (builder B): S-36 reviewed pages, S-37 every screen, S-38 one screen, S-39 user journeys.
// Outlines until ported from the prototype's screens/understand.js (console/PORTING.md).
import { outline } from 'eaos';

const o = (id, path, title, features) => outline({ id, path, place: 'understand', title, features });
o('S-36', '/understand/screens', 'un.v.screens', 'SCR-01');
o('S-37', '/understand/screens/all', 'un.v.screens-all', 'SCR-02');
o('S-38', '/understand/screens/:id', 'un.v.screens-all', 'SCR-03, LIB-06');
o('S-39', '/understand/journeys', 'un.v.journeys', 'SYS-12');
