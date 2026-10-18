// The plan (builder B): S-08 the plan, S-09 one step, S-10 waves, and S-54 "What changing it touches" (the impact
// sheet Problems opens). Outlines until ported from the prototype's screens/plan.js (console/PORTING.md).
import { outline, outlineSheet } from 'eaos';

outline({ id: 'S-08', path: '/problems/plan', place: 'problems', title: 'pb.view.plan', features: 'PLN-02, PLN-04, FIX-15, BLD-03' });
outline({ id: 'S-10', path: '/problems/plan/waves', place: 'problems', title: 'un.waves.title', features: 'PLN-06' });
outline({ id: 'S-09', path: '/problems/plan/:step', place: 'problems', title: 'pb.view.plan', features: 'PLN-03, PLN-05, SEL-01' });
outlineSheet('impact', 'pd.touches', 'PRB-14');
