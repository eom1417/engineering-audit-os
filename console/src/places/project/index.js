// The project's pages (builder A): S-46 Branches, S-47 one branch, S-48 Your app, S-49 Assistants and cost, S-50
// Tools, S-51 Settings. Outlines until ported from the prototype's screens/project.js (console/PORTING.md).
import { outline } from 'eaos';

outline({ id: 'S-46', path: '/project/branches', title: 'proj.branches', features: 'PRJ-04, PRJ-05, BRN-01, BRN-02, BRN-03, BRN-05, BRN-09, BRN-11, BRN-12' });
outline({ id: 'S-47', path: '/project/branches/:name', title: 'proj.branches', features: 'BRN-04, BRN-06, BRN-07, BRN-08, BRN-10' });
outline({ id: 'S-48', path: '/project/app', title: 'proj.app', features: 'APP-01, APP-03, SGN-02, SGN-06, SGN-07, DEC-04' });
outline({ id: 'S-49', path: '/project/assistants', title: 'proj.assistants', features: 'AST-01..05, CHK-06' });
outline({ id: 'S-50', path: '/project/tools', title: 'proj.tools', features: 'CHK-05' });
outline({ id: 'S-51', path: '/project/settings', title: 'proj.settings', features: 'SET-03, SET-05, SET-06, SET-07, OFF-05' });
