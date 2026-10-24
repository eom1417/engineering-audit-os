"""REPORT.html's style and behaviour: the inline CSS and the few lines of JS the page and its maps run."""


# ---------------------------------------------------------------- style and behaviour

CSS = r"""
:root{color-scheme:light;--bg:#f6f6f3;--surface:#ffffff;--surface-2:#f0efeb;--ink:#141413;--ink-2:#52514e;--muted:#6f6d67;
--line:#e3e1da;--accent:#2a5bd7;--accent-soft:#e8eefc;--good:#0a8a0a;--good-soft:#e6f4e6;--warn:#b77900;--warn-soft:#fff4dc;
--bad:#c73232;--bad-soft:#fbe9e9;--on-accent:#ffffff;--sev-critical:#d03b3b;--sev-high:#ec835a;--sev-medium:#fab219;--sev-low:#a9a79f;--tile-empty:#e9e8e3;
--shadow:0 1px 2px rgba(20,20,19,.05),0 4px 16px rgba(20,20,19,.05);--radius:14px}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#111110;--surface:#1b1b1a;--surface-2:#242422;--ink:#f4f3ef;--ink-2:#c9c7bf;
--muted:#9a978f;--line:#2f2f2c;--accent:#7ea2ff;--accent-soft:#1f2a45;--good:#3cc23c;--good-soft:#16301a;--warn:#f0b43a;--warn-soft:#352a12;
--bad:#ff7070;--bad-soft:#3a1c1c;--on-accent:#0b1020;--sev-low:#77756e;--tile-empty:#2b2b29;--shadow:none}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 system-ui,-apple-system,"Segoe UI","Noto Sans Arabic",Tahoma,sans-serif}
html[data-lang=ar] .l-en,html[data-lang=en] .l-ar{display:none!important}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top-in{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:14px;padding-bottom:6px}
.kicker{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:22px;margin:0;line-height:1.3}h1 .lit{font-size:20px;background:none;padding:0;color:var(--ink)}
h2{font-size:26px;margin:0 0 4px}h3{font-size:19px;margin:36px 0 12px}h4{font-size:16px;margin:0 0 6px}
.actions{display:flex;gap:8px}.btn{font:inherit;font-size:14px;border:1px solid var(--accent);background:var(--accent);color:var(--on-accent);border-radius:999px;padding:6px 16px;cursor:pointer}
.btn.ghost{background:transparent;color:var(--accent)}.btn:focus-visible,.tabs a:focus-visible{outline:3px solid var(--accent-soft);outline-offset:2px}
.tabs{display:flex;gap:4px;overflow-x:auto}.tabs a{padding:10px 14px;color:var(--ink-2);text-decoration:none;border-bottom:3px solid transparent;font-weight:600;white-space:nowrap}
.tabs a.on{color:var(--accent);border-color:var(--accent)}.tabs a:hover{color:var(--ink)}
main{padding-top:28px;padding-bottom:40px}.js section.report{display:none}.js section.report.on{display:block}
.sec-head{margin-bottom:20px}.muted{color:var(--muted)}.small{font-size:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow)}
.grid{display:grid;gap:16px}.grid.two{grid-template-columns:repeat(auto-fit,minmax(300px,1fr));margin-top:16px}
.grid.three{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}.grid.areas{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.hero{display:grid;grid-template-columns:220px 1fr;gap:28px;align-items:center;padding:26px 28px}
.hero-score{text-align:center}.big{font-size:72px;font-weight:800;line-height:1}.big small{display:block;font-size:14px;font-weight:500;color:var(--muted);margin-top:6px}
.grade-word{display:inline-block;margin-top:10px;padding:4px 14px;border-radius:999px;font-weight:700}
.grade-excellent,.grade-good{color:var(--good)}.grade-fair{color:var(--warn)}.grade-weak,.grade-critical{color:var(--bad)}
.grade-word.grade-excellent,.grade-word.grade-good{background:var(--good-soft)}.grade-word.grade-fair{background:var(--warn-soft)}.grade-word.grade-weak,.grade-word.grade-critical{background:var(--bad-soft)}
.lead{font-size:19px;margin:4px 0 16px}.hero h3{margin:0}
.meter{position:relative;margin:8px 0 4px}.bands{display:flex;gap:2px;height:26px;border-radius:6px;overflow:hidden;font-size:12px}
.band{display:flex;align-items:center;justify-content:center;color:var(--ink-2);background:var(--surface-2)}
.band-critical{box-shadow:inset 0 -4px 0 var(--sev-critical)}.band-weak{box-shadow:inset 0 -4px 0 var(--sev-high)}.band-fair{box-shadow:inset 0 -4px 0 var(--sev-medium)}
.band-good{box-shadow:inset 0 -4px 0 #6cc56c}.band-excellent{box-shadow:inset 0 -4px 0 var(--good)}
.marker{position:absolute;top:-6px;width:4px;height:38px;background:var(--ink);border-radius:2px;transform:translateX(-50%)}
html[dir=rtl] .marker{transform:translateX(50%)}
.note{font-size:14px;color:var(--bad)}
.area{border-top:5px solid var(--line)}.area.light-green{border-top-color:var(--good)}.area.light-amber{border-top-color:var(--sev-medium)}
.area.light-red{border-top-color:var(--sev-critical)}.area-head{display:flex;align-items:center;gap:8px}.area-head h4{margin:0;flex:1}
.light{width:14px;height:14px;border-radius:50%;background:var(--sev-low);flex:none}.light-green .light{background:var(--good)}
.light-amber .light{background:var(--sev-medium)}.light-red .light{background:var(--sev-critical)}
.area-score{font-size:14px;color:var(--muted);margin-top:8px}.area-score .n{font-size:30px;font-weight:800;color:var(--ink);margin-inline-end:4px}
.n{unicode-bidi:isolate;direction:ltr}.formula{display:block;margin-top:4px;font:13px ui-monospace,Menlo,Consolas,monospace;color:var(--ink-2);text-align:left}
.said{unicode-bidi:isolate;font-size:14px;color:var(--ink-2)}.quote{unicode-bidi:plaintext}
.cycle{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--bg)}.cycle-head{font-size:14px;margin-bottom:6px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.loop{color:var(--bad);font-weight:800;font-size:18px}.ring{display:flex;flex-wrap:wrap;gap:6px;direction:ltr}.pair{display:inline-flex;gap:8px;align-items:center}
.light-word{margin:6px 0 2px;font-weight:700;font-size:14px}.light-green .light-word{color:var(--good)}.light-amber .light-word{color:var(--warn)}.light-red .light-word{color:var(--bad)}
.area p{margin:6px 0}
.problems{list-style:none;padding:0;margin:0;display:grid;gap:10px}.problem{display:flex;gap:16px;align-items:flex-start}
.problem p{margin:4px 0}.rank{flex:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent);font-weight:800}
.stat{display:flex;gap:16px;align-items:center}.stat p{margin:0}.stat-n{font-size:40px;font-weight:800;min-width:90px;text-align:center}
.good-bg{background:var(--good-soft);border-color:transparent}.good-bg .stat-n{color:var(--good)}.warn-bg{background:var(--warn-soft);border-color:transparent}.warn-bg .stat-n{color:var(--warn)}
.honest ul{margin:8px 0 0;padding-inline-start:20px}.honest li{margin:4px 0}
.how ol{padding-inline-start:22px}.how li{margin:6px 0}
.tbl{width:100%;border-collapse:collapse;font-size:14px;margin-top:10px}.tbl th,.tbl td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:start;vertical-align:top}
.tbl th{font-weight:700;color:var(--ink-2);background:var(--surface-2)}.tbl td .n{font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}details>summary{cursor:pointer;color:var(--accent);font-weight:600;margin:6px 0}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:700;padding:1px 10px 1px 10px;border-radius:999px;background:var(--surface-2);white-space:nowrap}
.chip i{width:10px;height:10px;border-radius:2px;display:inline-block}
.sev-critical i{background:var(--sev-critical)}.sev-high i{background:var(--sev-high)}.sev-medium i{background:var(--sev-medium)}.sev-low i{background:var(--sev-low)}
.chip.sev-critical{color:var(--bad)}.chip.sev-critical i{border-radius:50%}.chip.sev-high i{transform:rotate(45deg)}
.legend{margin-bottom:16px}.legend-item{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:center;padding:6px 0;border-top:1px solid var(--line)}
.keys{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 10px}
.chart{width:100%;height:auto;display:block}.chart.bars{max-width:900px}.axis-label{font-size:15px;fill:var(--ink)}.value-label{font-size:14px;fill:var(--ink-2)}
.seg.sev-critical{fill:var(--sev-critical)}.seg.sev-high{fill:var(--sev-high)}.seg.sev-medium{fill:var(--sev-medium)}.seg.sev-low{fill:var(--sev-low)}
.seg:hover{opacity:.8}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0;position:sticky;top:112px;z-index:3}
.filters input[type=search],.filters select{font:inherit;font-size:14px;padding:7px 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink)}
.filters input[type=search]{flex:1;min-width:220px}.check{font-size:14px;display:flex;gap:6px;align-items:center}
.area-title{border-bottom:2px solid var(--line);padding-bottom:6px}
.group{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:10px 16px;margin:10px 0}
.group>summary{display:flex;justify-content:space-between;gap:10px;color:var(--ink);font-size:16px}.g-meta{color:var(--muted);font-weight:500;font-size:14px}
.why{margin:0 0 8px;color:var(--ink-2);font-size:14px}.rows{display:grid;gap:8px}
.rows .row:nth-child(n+6){display:none}.rows.all .row:nth-child(n+6){display:block}.more{font:inherit;font-size:14px;background:none;border:0;color:var(--accent);cursor:pointer;padding:4px 0}
.row{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--bg)}.row[hidden]{display:none!important}
.row-head{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:14px}.row-head .lit{margin-inline-start:auto}
.conf{color:var(--ink-2)}.prio{color:var(--ink-2)}.where{font-size:14px;margin:6px 0}.lbl{color:var(--muted)}
.nowto{display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:14px}.nowto b{display:block;font-size:12px;color:var(--muted)}
.row-foot{display:flex;gap:12px;font-size:13px;margin-top:6px}.yes{color:var(--good);font-weight:700}.no{color:var(--warn);font-weight:700}
.lit{font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--surface-2);padding:1px 6px;border-radius:6px;unicode-bidi:isolate;word-break:break-all}
.tech{font-size:13px;color:var(--ink-2);unicode-bidi:isolate;display:inline-block;text-align:left}
.map-grid{grid-template-columns:3fr 2fr;align-items:start}
.tile rect{stroke:var(--surface);stroke-width:0}.tile:hover rect{opacity:.85}.tile-name{font:600 12px ui-monospace,Menlo,Consolas,monospace}
.tile-sub{font-size:12px}.tile-name.dark,.tile-sub.dark{fill:#2a1a10}.tile-name.light,.tile-sub.light{fill:#fff}
.heat-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:13px;color:var(--ink-2)}.heat-key{display:inline-flex;gap:6px;align-items:center}
.heat-key i{width:16px;height:12px;border-radius:3px;display:inline-block}
.layers .layer{fill:var(--accent-soft)}.layer-name{font:600 13px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}.layer-count{font-size:12px;fill:var(--ink-2)}
.diff li{margin:6px 0}.cycles{list-style:none;padding:0;display:grid;gap:8px}.cycle{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.arrow{color:var(--bad);font-weight:800}
.roadmap{list-style:none;padding:0;margin:0;position:relative}.roadmap:before{content:"";position:absolute;inset-inline-start:17px;top:8px;bottom:8px;width:2px;background:var(--line)}
.stone{display:grid;grid-template-columns:36px 1fr;gap:14px;margin-bottom:14px;position:relative}
.dot{width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:var(--surface);border:2px solid var(--line);font-weight:800;color:var(--ink-2);z-index:1}
.stone.done .dot{background:var(--good);border-color:var(--good);color:#fff}.stone.active .dot{border-color:var(--accent);color:var(--accent)}
.stone h4 .lit{font-size:12px;margin-inline-start:6px}
.progress{height:10px;background:var(--surface-2);border-radius:999px;overflow:hidden;margin-top:8px}.progress span{display:block;height:100%;background:var(--good);border-radius:999px}
.decision .count{font-size:13px;color:var(--muted);font-weight:500}.answers{margin:4px 0;padding-inline-start:20px;font-size:14px}.ids{display:flex;flex-wrap:wrap;gap:4px}
.options{font-size:14px}.fails{font-size:14px}.na{color:var(--muted)}
footer{padding-top:10px;padding-bottom:40px}
.gap-card{display:block}.gap-head{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}
.gap-n{font-size:54px;font-weight:800;color:var(--good);line-height:1;min-width:120px;text-align:center}.gap-card .lead{margin:0 0 10px}
.progress.big{height:16px}.progress.thin{height:6px;margin:6px 0}
.tally{list-style:none;padding:0;margin:14px 0 4px;display:flex;flex-wrap:wrap;gap:8px 18px;font-size:14px}.tally li{display:flex;gap:6px;align-items:center}
.tally .n{font-weight:800;font-size:16px}
.chip.st{font-weight:600}.st-good{background:var(--good-soft);color:var(--good)}.st-warn{background:var(--warn-soft);color:var(--warn)}
.st-accent{background:var(--accent-soft);color:var(--accent)}.st-bad{background:var(--bad-soft);color:var(--bad)}.st-plain{background:var(--surface-2);color:var(--ink-2)}
.chart.history{max-width:760px;margin-top:6px}.history .grid{stroke:var(--line);stroke-width:1}.history .tick{font-size:12px;fill:var(--muted)}
.history .line{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round}.history .area{fill:var(--accent);opacity:.08}
.history .dot-pt{fill:var(--accent);stroke:var(--surface);stroke-width:2}.history .end-label{font-size:13px;font-weight:700;fill:var(--ink)}
.allcards>summary{font-size:17px;display:flex;justify-content:space-between;gap:10px}.cfilters{position:static;margin:10px 0;box-shadow:none;border:0;padding:0}
.mgroup{border:1px solid var(--line);border-radius:12px;padding:8px 14px;margin:8px 0;background:var(--bg)}
.mgroup>summary{display:flex;justify-content:space-between;gap:10px;color:var(--ink)}.mgroup[hidden],.tcard[hidden]{display:none!important}
.tcards{display:grid;gap:6px;margin-top:6px}.tcard{border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:4px 12px}
.tcard>summary{color:var(--ink);font-weight:500;font-size:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}.tcard>summary .lit{margin-inline-start:auto}
.tcard>summary .said{flex:1 1 320px;min-width:0;font-size:14px;color:var(--ink)}.tbody{font-size:14px;padding:4px 0 8px}.tbody p{margin:6px 0}.bad-ink{color:var(--bad);font-weight:600}
.graph-scroll{overflow:auto;max-height:78vh;border:1px solid var(--line);border-radius:10px;background:var(--bg);margin-top:10px}
.graph-scroll .chart{max-width:none}.fit .graph-scroll .cgraph{width:100%!important;height:auto}
.graph-tools{display:flex;gap:14px;align-items:center;margin-top:8px;flex-wrap:wrap}
.cgraph .cg-node rect{fill:var(--surface);stroke:var(--line);stroke-width:1.5}.cgraph .cg-node.cyc rect{stroke:var(--bad);stroke-width:2}
.cg-node{cursor:pointer}.cg-node:focus{outline:none}.cg-node:focus rect,.t-node:focus rect{stroke:var(--accent);stroke-width:2.5}
.cg-name{font:600 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.cg-sub{font-size:11px;fill:var(--ink-2)}
.edge{fill:none;stroke:var(--ink-2);opacity:.28}.edge.cyc{stroke:var(--bad);opacity:.5}.edge.wrong{stroke-dasharray:6 4}
.arrow-head{fill:var(--ink-2)}.arrow-head.cyc{fill:var(--bad)}.arrow-head.acc{fill:var(--accent)}
.hl-graph.focus .edge{opacity:.06}.hl-graph.focus .edge.on{opacity:.95}.hl-graph.focus .cg-node,.hl-graph.focus .t-node{opacity:.35}
.hl-graph.focus .cg-node.on,.hl-graph.focus .t-node.on{opacity:1}.hl-graph .on rect{stroke:var(--accent);stroke-width:2.5}
.loops .edge:not(.cyc){display:none}
.key-line{vertical-align:middle}.key-line .edge{opacity:.9;stroke-width:2.5}.key-box{width:16px;height:12px;border-radius:3px;display:inline-block;border:2px solid var(--line)}.key-box.cyc{border-color:var(--bad)}
.node-detail{margin-top:10px;background:var(--surface-2);box-shadow:none}.node-detail h4 .lit{font-size:14px}.link{display:inline-flex;gap:4px;align-items:center;margin:2px 8px 2px 0}
.drill,.graph-wrap{margin-bottom:16px}.pick{display:flex;gap:8px;align-items:center;margin:8px 0;font-weight:600}
.pick select{font:13px ui-monospace,Menlo,Consolas,monospace;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:var(--surface);color:var(--ink);max-width:100%}
.ego-heads{display:grid;grid-template-columns:240fr 140fr 290fr 190fr 240fr;font-size:13px;font-weight:700;color:var(--ink-2);margin-top:8px}
.ego-heads>div:nth-child(2){grid-column:3}.ego-heads>div:nth-child(3){grid-column:5}
.egograph{width:100%;height:auto;margin-top:4px}.e-box rect{fill:var(--surface);stroke:var(--line)}.e-box.cyc rect{stroke:var(--bad);stroke-width:1.5}
.e-box[data-pick]{cursor:pointer}.e-box[data-pick]:hover rect{stroke:var(--accent)}.e-box.quiet{opacity:.55}
.e-l{font:600 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.e-s{font-size:11px;fill:var(--muted)}
.e-link{fill:none;stroke:var(--ink-2);opacity:.28}.e-arc{fill:none;stroke:var(--accent);stroke-width:1.2;opacity:.5}
#dfile{margin-top:14px;border-top:1px solid var(--line);padding-top:6px}
.flowsvg{display:block;margin:0 auto}.f-node rect{fill:var(--surface);stroke:var(--line);stroke-width:1.5}
.f-entry rect{fill:var(--accent);stroke:var(--accent)}.f-entry .f-l,.f-entry .f-s{fill:var(--on-accent)}.f-handler rect{stroke:var(--accent);stroke-width:2.5}
.f-stop rect{fill:var(--bg);stroke:var(--muted);stroke-dasharray:5 4}.f-stop .f-l{fill:var(--muted)}
.f-l{font:600 12.5px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.f-s{font-size:11.5px;fill:var(--ink-2)}
.f-edge{fill:none;stroke:var(--ink-2);stroke-width:1.6;opacity:.6}.f-edge.stop{stroke-dasharray:4 4}
.f-group{fill:none;stroke:var(--accent);stroke-opacity:.35;stroke-dasharray:3 3}.f-gname{font:600 11px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}
.tgraph{min-width:900px}.t-band{fill:var(--surface-2);opacity:.6}.t-layer{font:700 13px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}
.t-node{cursor:pointer}.t-node rect:first-of-type{fill:var(--surface);stroke:var(--line);stroke-width:1.5}.t-node.empty rect:first-of-type{stroke-dasharray:4 3}
.t-name{font:600 12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.t-sub{font-size:11px;fill:var(--ink-2)}
.t-track{fill:var(--surface-2)}.t-fill{fill:var(--good)}.t-edge{opacity:.12}
.mapping{min-width:900px}.m-name,.m-target{font:12px ui-monospace,Menlo,Consolas,monospace;fill:var(--ink)}.m-target{font-weight:700;fill:var(--accent)}
.m-line{fill:none;stroke-width:1.8}.r-keep{stroke:var(--muted);opacity:.7}.r-modify{stroke:var(--accent);opacity:.8}
.r-rebuild{stroke:var(--accent);stroke-width:3;stroke-dasharray:7 4;opacity:.8}.r-remove{stroke:var(--bad);stroke-dasharray:2 4;opacity:.8}
.map-row:hover .m-line{stroke-width:4;opacity:1}
@media (max-width:760px){.gap-head{grid-template-columns:1fr}.ego-heads{display:none}}
@media (max-width:760px){.hero{grid-template-columns:1fr}.map-grid{grid-template-columns:1fr}.nowto{grid-template-columns:1fr}.top-in{flex-direction:column;align-items:flex-start}.filters{position:static}}
@media print{body{background:#fff;font-size:12px}.top{position:static;backdrop-filter:none}.tabs,.actions,.filters,.more{display:none!important}
.js section.report{display:block!important;break-before:page}.js section.report:first-of-type{break-before:auto}
.card,.group{box-shadow:none;break-inside:avoid}}
"""

JS = r"""
(function(){var d=document.documentElement;d.classList.add('js');
function setLang(l){d.setAttribute('data-lang',l);d.lang=l;d.dir=l==='ar'?'rtl':'ltr';try{localStorage.setItem('eaos-human-lang',l)}catch(e){}
document.querySelectorAll('[data-ph-ar]').forEach(function(e){e.placeholder=e.getAttribute('data-ph-'+l)});
document.querySelectorAll('select option').forEach(function(o){if(!o.dataset.ar){o.dataset.ar=o.textContent}});
document.querySelectorAll('option[data-en]').forEach(function(o){o.textContent=o.getAttribute('data-'+l)});
var names={'':['كل درجات الخطورة','All severities'],critical:['حرجة','Critical'],high:['عالية','High'],medium:['متوسطة','Medium'],low:['منخفضة','Low']};
var areas={'':['كل المجالات','All areas'],security:['الأمان','Security'],structure:['البنية','Structure'],quality:['جودة الكود','Code quality'],performance:['الأداء تحت الضغط','Performance under load'],ux:['شكل الشاشات','How the screens look'],maintainability:['سهولة التطوير والاختبار','Ease of change and testing']};
var i=l==='ar'?0:1;document.querySelectorAll('#fsev option').forEach(function(o){o.textContent=names[o.value][i]});
document.querySelectorAll('#farea option').forEach(function(o){o.textContent=areas[o.value][i]});count()}
function show(id){document.querySelectorAll('section.report').forEach(function(s){s.classList.toggle('on',s.id===id)});
document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.tab===id)})}
var tabs=Array.prototype.map.call(document.querySelectorAll('.tabs a'),function(a){return a.dataset.tab});function route(){var h=location.hash.slice(1);show(tabs.indexOf(h)>=0?h:'summary')}
window.addEventListener('hashchange',function(){route();window.scrollTo(0,0)});
document.querySelectorAll('[data-go]').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();history.replaceState(null,'','#'+a.dataset.go);show(a.dataset.go);window.scrollTo(0,0)})});
document.querySelectorAll('.tabs a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();history.replaceState(null,'','#'+a.dataset.tab);show(a.dataset.tab);window.scrollTo(0,0)})});
document.querySelectorAll('.rows').forEach(function(r){var n=r.children.length;if(n>5){var b=document.createElement('button');b.type='button';b.className='more';
b.innerHTML='<span class="l-ar">عرض الكل</span><span class="l-en">Show all</span>';b.onclick=function(){r.classList.toggle('all')};r.after(b)}});
function count(){var rows=document.querySelectorAll('.row'),q=(document.getElementById('q')||{}).value||'',s=(document.getElementById('fsev')||{}).value||'',
a=(document.getElementById('farea')||{}).value||'',auto=(document.getElementById('fauto')||{}).checked,n=0,active=q||s||a||auto;q=q.toLowerCase();
rows.forEach(function(r){var ok=(!q||r.dataset.search.indexOf(q)>=0)&&(!s||r.dataset.sev===s)&&(!a||r.dataset.area===a)&&(!auto||r.dataset.auto==='1');r.hidden=!ok;if(ok)n++});
document.querySelectorAll('.rows').forEach(function(r){r.classList.toggle('all',!!active);var g=r.closest('.group');if(g)g.hidden=active&&!r.querySelector('.row:not([hidden])')});
document.querySelectorAll('[data-area-block]').forEach(function(h){h.hidden=!!a&&h.dataset.areaBlock!==a});
var out=document.getElementById('shown');if(out){out.textContent=active?(d.lang==='ar'?('المعروض: '+n):('Showing: '+n)):''}}
['q','fsev','farea','fauto'].forEach(function(id){var e=document.getElementById(id);if(e){e.addEventListener('input',count);e.addEventListener('change',count)}});
var saved=null;try{saved=localStorage.getItem('eaos-human-lang')}catch(e){}setLang(saved||d.getAttribute('data-lang')||'ar');
document.getElementById('lang').onclick=function(){setLang(d.getAttribute('data-lang')==='ar'?'en':'ar')};
document.getElementById('print').onclick=function(){window.print()};
window.addEventListener('beforeprint',function(){document.querySelectorAll('section.report').forEach(function(s){s.classList.add('on')})});
window.addEventListener('afterprint',route);route();window.scrollTo(0,0)})();
"""

MAP_JS = r"""
(function(){var d=document.documentElement,lang=d.getAttribute('data-lang')||'ar';
document.querySelectorAll('option[data-en]').forEach(function(o){o.textContent=o.getAttribute('data-'+lang)});
document.querySelectorAll('[data-ph-ar]').forEach(function(e){e.placeholder=e.getAttribute('data-ph-'+lang)});
function E(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function B(ar,en){return '<span class="l-ar" lang="ar">'+ar+'</span><span class="l-en" lang="en">'+en+'</span>'}
function J(id){var e=document.getElementById(id);if(!e)return null;try{return JSON.parse(e.textContent)}catch(x){return null}}
function base(p){return String(p).split('/').pop()}
function cut(s,n){s=String(s);return s.length>n?'…'+s.slice(s.length-n+1):s}
function N(v,m){return '<span class="n" data-meaning="'+E(m)+'">'+E(v)+'</span>'}
function sel(v){return '[data-node="'+String(v).replace(/["\\]/g,'\\$&')+'"]'}
function wire(root){(root||document).querySelectorAll('.hl-graph').forEach(function(svg){if(svg.dataset.wired)return;svg.dataset.wired='1';
var wrap=svg.closest('.graph-wrap'),pinned=null;
function mark(id,on){svg.classList.toggle('focus',!!on);svg.querySelectorAll('.on').forEach(function(e){e.classList.remove('on')});if(!on)return;
svg.querySelectorAll(sel(id)).forEach(function(e){e.classList.add('on')});
svg.querySelectorAll('[data-from]').forEach(function(e){if(e.dataset.from===id||e.dataset.to===id){e.classList.add('on');
svg.querySelectorAll(sel(e.dataset.from===id?e.dataset.to:e.dataset.from)).forEach(function(n){n.classList.add('on')})}})}
svg.querySelectorAll('[data-node]').forEach(function(n){var id=n.dataset.node;
n.addEventListener('mouseenter',function(){if(!pinned)mark(id,true)});n.addEventListener('mouseleave',function(){if(!pinned)mark(id,false)});
function pick(){pinned=pinned===id?null:id;mark(pinned||id,!!pinned);if(n.dataset.pick){n.dispatchEvent(new CustomEvent('pick',{bubbles:true}));return}
if(wrap)wrap.querySelectorAll('.node-detail').forEach(function(x){x.hidden=x.dataset.for!==pinned})}
n.addEventListener('click',pick);n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}})})})}
document.querySelectorAll('.only-loops').forEach(function(c){c.addEventListener('change',function(){c.closest('.graph-wrap').classList.toggle('loops',c.checked)})});
document.querySelectorAll('.fit-btn').forEach(function(b){b.addEventListener('click',function(){b.closest('.graph-wrap').classList.toggle('fit')})});
// a three-column picture: what points in, the subject's own items (with arcs between them), what they point to
function ego(o,rtl){var W=1100,rh=30,bh=24,cols=[[0,240],[380,290],[860,240]],gut=16;
var n=Math.max(o.mid.length,o.left.length,o.right.length,1),H=n*rh+12,out=[];
function X(c){var x=cols[c][0],w=cols[c][1];return rtl?W-x-w:x}
function Y(list,i){var step=(H-12)/Math.max(list.length,1);return 6+i*step+(step-bh)/2}
function yMid(i){return 6+i*rh+(rh-bh)/2}
function link(c1,y1,c2,y2,cls,w){var a=X(c1),b=X(c2),wa=cols[c1][1],wb=cols[c2][1],sx,ex;if(a<b){sx=a+wa;ex=b}else{sx=a;ex=b+wb}
var mx=(sx+ex)/2;return '<path class="'+cls+'" style="stroke-width:'+w.toFixed(1)+'" d="M'+sx+','+(y1+bh/2)+' C'+mx+','+(y1+bh/2)+' '+mx+','+(y2+bh/2)+' '+ex+','+(y2+bh/2)+'"/>'}
function sw(k){return 1+Math.log2(Math.max(k||1,1))}
o.lm.forEach(function(l){out.push(link(0,Y(o.left,l[0]),1,yMid(l[1]),'e-link',sw(l[2])))});
o.mr.forEach(function(l){out.push(link(1,yMid(l[0]),2,Y(o.right,l[1]),'e-link',sw(l[2])))});
var edge=rtl?X(1):X(1)+cols[1][1],dir=rtl?-1:1;
o.mm.forEach(function(l){var y1=yMid(l[0])+bh/2,y2=yMid(l[1])+bh/2,bulge=Math.min(150,gut+Math.abs(y2-y1)*0.3)*dir;
out.push('<path class="e-arc" d="M'+edge+','+y1+' C'+(edge+bulge)+','+y1+' '+(edge+bulge)+','+y2+' '+edge+','+y2+'" marker-end="url(#ego-arr)"/>')});
function box(c,y,it,i){var x=X(c),w=cols[c][1],tx=rtl?x+w-8:x+8,anchor=rtl?'end':'start',room=Math.floor((w-16)/7);
return '<g class="e-box'+(it.cls?' '+it.cls:'')+'"'+(it.pick!=null?' data-pick="'+it.pick+'" tabindex="0"':'')+'><title>'+E(it.title||it.label)+'</title><rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+bh+'" rx="6"/>'+
'<text x="'+tx+'" y="'+(y+16)+'" text-anchor="'+anchor+'" direction="ltr"><tspan class="e-l">'+E(cut(it.label,room-(it.sub?Math.min(14,it.sub.length+2):0)))+'</tspan>'+(it.sub?'<tspan class="e-s"> '+E(cut(it.sub,14))+'</tspan>':'')+'</text></g>'}
o.left.forEach(function(it,i){out.push(box(0,Y(o.left,i),it,i))});o.mid.forEach(function(it,i){out.push(box(1,yMid(i),it,i))});o.right.forEach(function(it,i){out.push(box(2,Y(o.right,i),it,i))});
return '<svg viewBox="0 0 '+W+' '+H+'" class="chart egograph" direction="ltr" role="img" aria-label="'+E(o.label)+'"><defs><marker id="ego-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="arrow-head acc"/></marker></defs>'+out.join('')+'</svg>'}
function heads(a,b,c){return '<div class="ego-heads"><div>'+a+'</div><div>'+b+'</div><div>'+c+'</div></div>'}
function both(o){return '<div class="l-ar">'+ego(o,true)+'</div><div class="l-en">'+ego(o,false)+'</div>'}
var D=J('eaos-drill');
if(D){var rev=D.files.map(function(){return[]});D.imports.forEach(function(list,f){list.forEach(function(g){rev[g].push(f)})});
var fnOut={},fnIn={};D.calls.forEach(function(c,i){(fnOut[c[0]]=fnOut[c[0]]||[]).push(i);(fnIn[c[2]]=fnIn[c[2]]||[]).push(i)});
function comp(ci){var C=D.comps[ci],mine={},view=document.getElementById('dview');C.files.forEach(function(f){mine[f]=1});
var left=C.used_by.slice().sort(function(a,b){return b[1]-a[1]}).slice(0,12),right=C.uses.slice().sort(function(a,b){return b[1]-a[1]}).slice(0,12);
var li={},ri={};left.forEach(function(p,i){li[p[0]]=i});right.forEach(function(p,i){ri[p[0]]=i});
var files=C.files.slice().sort(function(a,b){return (rev[b].length+D.imports[b].length)-(rev[a].length+D.imports[a].length)}).slice(0,30),mi={};files.forEach(function(f,i){mi[f]=i});
var lm={},mr={},mm=[];files.forEach(function(f,i){rev[f].forEach(function(g){var o=D.owner[g];if(o!==ci&&o in li){var k=li[o]+':'+i;lm[k]=(lm[k]||0)+1}});
D.imports[f].forEach(function(g){var o=D.owner[g];if(o===ci){if(g in mi)mm.push([i,mi[g]])}else if(o in ri){var k=i+':'+ri[o];mr[k]=(mr[k]||0)+1}})});
function pairs(m){return Object.keys(m).map(function(k){var p=k.split(':');return[+p[0],+p[1],m[k]]})}
var root=C.name.replace(/\/?$/,'/');
var o={label:C.name,left:left.map(function(p){return{label:D.comps[p[0]].name,title:D.comps[p[0]].name+' → '+C.name+': '+p[1]}}),
right:right.map(function(p){return{label:D.comps[p[0]].name,title:C.name+' → '+D.comps[p[0]].name+': '+p[1]}}),
mid:files.map(function(f){var p=D.files[f];return{label:p.indexOf(root)===0?p.slice(root.length):p,title:p,pick:f,cls:D.cycle[f]?'cyc':''}}),lm:pairs(lm),mr:pairs(mr),mm:mm};
var inside=C.counts.inside,more=C.counts.more,coh=C.cohesion==null?B('لا يستورد شيئًا','it imports nothing'):B(N(C.cohesion+'%','share of its imports that stay inside it')+' من استيراداته تبقى داخله',N(C.cohesion+'%','share of its imports that stay inside it')+' of its imports stay inside it');
view.innerHTML='<p class="small"><code class="lit" dir="ltr" data-literal="1">'+E(C.name)+'</code> — '+B('الملفات: '+N(C.filecount,'files in this part')+' · استيرادات داخلية مرسومة: '+N(inside,'imports between its files drawn'),N(C.filecount,'files in this part')+' files · '+N(inside,'imports between its files drawn')+' imports between them drawn')+' · '+coh+
(more>0?' · '+B('عُرض أكثر '+N(C.counts.shown,'files shown')+' ملفًا ارتباطًا','showing the '+N(C.counts.shown,'files shown')+' most connected files'):'')+'</p>'+
heads(B('أجزاء تستخدمه','Parts that use it')+' '+N(C.counts.used_by,'parts that use it'),B('ملفاته — اضغط على ملف','Its files — click a file'),B('أجزاء يستخدمها','Parts it uses')+' '+N(C.counts.uses,'parts it uses'))+both(o);
view.querySelectorAll('[data-pick]').forEach(function(g){function go(){file(+g.dataset.pick)}g.addEventListener('click',go);g.addEventListener('keydown',function(e){if(e.key==='Enter'){go()}})});
if(files.length)file(files[0]);else document.getElementById('dfile').innerHTML=''}
function file(f){var view=document.getElementById('dfile'),own=D.functions[f]||[],touched={};
(fnOut[f]||[]).forEach(function(i){touched[D.calls[i][1]]=(touched[D.calls[i][1]]||0)+1});(fnIn[f]||[]).forEach(function(i){touched[D.calls[i][3]]=(touched[D.calls[i][3]]||0)+1});
var names=own.slice().sort(function(a,b){return (touched[b]||0)-(touched[a]||0)}).slice(0,30),mi={};names.forEach(function(n,i){mi[n]=i});
var L={},R={},lm={},mr={},mm=[];
(fnOut[f]||[]).forEach(function(i){var c=D.calls[i];if(!(c[1] in mi))return;if(c[2]===f){if(c[3] in mi)mm.push([mi[c[1]],mi[c[3]]]);return}
var k=c[2]+'|'+c[3];if(!(k in R))R[k]={label:c[3],sub:base(D.files[c[2]]),title:c[3]+' — '+D.files[c[2]],n:0};R[k].n+=c[4];var q=mi[c[1]]+'|'+k;mr[q]=(mr[q]||0)+c[4]});
(fnIn[f]||[]).forEach(function(i){var c=D.calls[i];if(c[0]===f||!(c[3] in mi))return;var k=c[0]+'|'+c[1];if(!(k in L))L[k]={label:c[1],sub:base(D.files[c[0]]),title:c[1]+' — '+D.files[c[0]],n:0};L[k].n+=c[4];var q=k+'|'+mi[c[3]];lm[q]=(lm[q]||0)+c[4]});
function top(M){return Object.keys(M).sort(function(a,b){return M[b].n-M[a].n}).slice(0,14)}
var lk=top(L),rk=top(R),li={},ri={};lk.forEach(function(k,i){li[k]=i});rk.forEach(function(k,i){ri[k]=i});
var LM=[],MR=[];Object.keys(lm).forEach(function(q){var p=q.split('|'),k=p[0]+'|'+p[1];if(k in li)LM.push([li[k],+p[2],lm[q]])});
Object.keys(mr).forEach(function(q){var p=q.split('|'),k=p[1]+'|'+p[2];if(k in ri)MR.push([+p[0],ri[k],mr[q]])});
var head='<h4><code class="lit" dir="ltr" data-literal="1">'+E(D.files[f])+'</code></h4>';
if(!own.length){view.innerHTML=head+'<p class="muted small">'+B('لم نجد دوال مسمّاة في هذا الملف.','No named function was found in this file.')+'</p>';return}
var o={label:D.files[f],left:lk.map(function(k){return L[k]}),right:rk.map(function(k){return R[k]}),mid:names.map(function(n){return{label:n,cls:touched[n]?'':'quiet'}}),lm:LM,mr:MR,mm:mm};
view.innerHTML=head+'<p class="small">'+B('الدوال: '+N(D.file_counts[f].own,'named functions in this file')+' · تستدعيها دوال من ملفات أخرى: '+N(D.file_counts[f].left,'functions elsewhere that call this file')+' · تستدعي هي: '+N(D.file_counts[f].right,'functions elsewhere this file calls'),
N(D.file_counts[f].own,'named functions in this file')+' functions · called by '+N(D.file_counts[f].left,'functions elsewhere that call this file')+' functions elsewhere · they call '+N(D.file_counts[f].right,'functions elsewhere this file calls')+' elsewhere')+'</p>'+
heads(B('من يستدعيها','Who calls them'),B('دوال هذا الملف (الأقواس: استدعاءات بينها)','This file’s functions (arcs: calls between them)'),B('ما تستدعيه','What they call'))+both(o)}
var dc=document.getElementById('dcomp');if(dc&&D.comps.length){dc.addEventListener('change',function(){comp(+dc.value)});comp(+dc.value||0)}}
var F=J('eaos-flows');
function flow(fl,rtl){var bw=F.box[0],bh=F.box[1],W=fl.width,H=fl.height,pos={},out=[];
fl.nodes.forEach(function(n){pos[n.id]={x:rtl?W-n.x-bw:n.x,y:n.y,n:n}});
var run=[];fl.nodes.concat([{y:-1}]).forEach(function(n){var last=run[run.length-1];if(last&&(n.y!==last.y||n.sub!==last.sub||n.kind==='stop'||n.kind==='entry')){if(run.length>1&&last.sub){var xs=run.map(function(r){return pos[r.id].x}),x0=Math.min.apply(0,xs),x1=Math.max.apply(0,xs)+bw;
out.push('<rect class="f-group" x="'+(x0-6)+'" y="'+(last.y-20)+'" width="'+(x1-x0+12)+'" height="'+(bh+26)+'" rx="8"/><text class="f-gname" x="'+(rtl?x1:x0)+'" y="'+(last.y-7)+'" text-anchor="'+(rtl?'end':'start')+'" direction="ltr">'+E(base(last.sub))+'</text>')}run=[]}if(n.y>=0&&n.kind==='fn')run.push(n)});
fl.edges.forEach(function(e){var a=pos[e[0]],b=pos[e[1]];if(!a||!b)return;var sx=a.x+bw/2,sy=a.y+bh,ex=b.x+bw/2,ey=b.y,d;
if(ey>sy)d='M'+sx+','+sy+' C'+sx+','+(sy+26)+' '+ex+','+(ey-26)+' '+ex+','+ey;else{var side=rtl?-1:1,ox=a.x+(rtl?0:bw),tx=b.x+(rtl?0:bw);d='M'+ox+','+(a.y+bh/2)+' C'+(ox+60*side)+','+(a.y+bh/2)+' '+(tx+60*side)+','+(b.y+bh/2)+' '+tx+','+(b.y+bh/2)}
out.push('<path class="f-edge'+(b.n.kind==='stop'?' stop':'')+'" d="'+d+'" marker-end="url(#f-arr)"/>')});
function line(t,y,cls,words){var tx=rtl?x0+bw-10:x0+10,an=rtl&&!words?'end':'start',dir=rtl&&words?'rtl':'ltr';
return '<text x="'+tx+'" y="'+y+'" text-anchor="'+an+'" direction="'+dir+'" class="'+cls+'">'+E(t)+'</text>'}var x0;
fl.nodes.forEach(function(n){var p=pos[n.id],y=p.y,t1=n.label,t2,words=true;x0=p.x;
if(n.kind==='entry'){t1=(n.sub||'')+' '+(n.label||'');t2=rtl?'الرابط الذي تبدأ منه':'where it starts'}
else if(n.kind==='stop'){t2=rtl?'يتوقف التتبع هنا'+(n.more?' (و'+n.more+' غيرها)':''):'the trace stops here'+(n.more?' (and '+n.more+' more)':'')}
else{t2=n.library?(rtl?base(n.sub)+' · ومكتبات: '+n.library:base(n.sub)+' · and '+n.library+' library calls'):base(n.sub);words=rtl&&!!n.library}
out.push('<g class="f-node f-'+n.kind+'"><title>'+E(n.label+(n.sub?' — '+n.sub:''))+'</title><rect x="'+x0+'" y="'+y+'" width="'+bw+'" height="'+bh+'" rx="'+(n.kind==='entry'?bh/2:8)+'"/>'+
line(cut(t1,30),y+20,'f-l',false)+line(cut(t2,38),y+38,'f-s',n.kind!=='fn'||words)+'</g>')});
return '<svg viewBox="0 0 '+W+' '+H+'" class="chart flowsvg" direction="ltr" role="img" aria-label="'+E(fl.route+' '+fl.handler)+'"><defs><marker id="f-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="arrow-head"/></marker></defs>'+out.join('')+'</svg>'}
function showFlow(i){var fl=F.flows[i],v=document.getElementById('fview');if(!fl||!v)return;
var what=fl.surface==='page'?B('صفحة','A page'):B('نقطة دخول','An entry point');
v.innerHTML='<p class="small">'+what+' <code class="lit" dir="ltr" data-literal="1">'+E((fl.method?fl.method+' ':'')+(fl.route||'?'))+'</code> → <code class="lit" dir="ltr" data-literal="1">'+E(fl.handler)+'</code> '+
B('في','in')+' <code class="lit" dir="ltr" data-literal="1">'+E(fl.path)+'</code> · '+B('الاستدعاءات المتتبعة: '+N(fl.steps,'calls traced from this page')+' · يتوقف التتبع عند '+N(fl.stops,'calls the trace cannot follow')+' منها',N(fl.steps,'calls traced from this page')+' calls traced · the trace stops at '+N(fl.stops,'calls the trace cannot follow')+' of them')+'</p>'+
'<div class="graph-scroll"><div class="l-ar">'+flow(fl,true)+'</div><div class="l-en">'+flow(fl,false)+'</div></div>'}
var df=document.getElementById('dflow');if(F&&df&&F.flows.length){df.addEventListener('change',function(){showFlow(+df.value)});showFlow(+df.value||0)}
function cards(){var s=(document.getElementById('cstate')||{}).value||'',q=((document.getElementById('cq')||{}).value||'').toLowerCase(),n=0,active=s||q;
document.querySelectorAll('.tcard').forEach(function(c){var ok=(!s||c.dataset.state===s||(s==='new'&&c.dataset.new==='1'))&&(!q||c.dataset.search.indexOf(q)>=0);c.hidden=!ok;if(ok)n++});
document.querySelectorAll('.mgroup').forEach(function(g){var any=g.querySelector('.tcard:not([hidden])');g.hidden=!!active&&!any;if(active&&any)g.open=true});
var out=document.getElementById('cshown');if(out)out.textContent=active?(d.getAttribute('data-lang')==='ar'?('المعروض: '+n):('Showing: '+n)):''}
['cstate','cq'].forEach(function(id){var e=document.getElementById(id);if(e){e.addEventListener('input',cards);e.addEventListener('change',cards)}});
wire(document)})();
"""

CSS += r"""
.sm-wrap .sm-title{margin:0 0 6px}.sm-tools{position:static;margin:10px 0 6px}
.sm-scroll{max-height:82vh;position:relative}.sm-heads{display:grid;position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);
font-size:13px;font-weight:700;color:var(--ink-2);padding:6px 0;min-width:1000px}.sm-heads>div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.smap{min-width:1000px}.smap .sm-node{cursor:pointer}.smap .sm-node rect{fill:var(--surface);stroke:var(--line);stroke-width:1.2}
.smap .sm-node:focus{outline:none}.smap .sm-node:focus rect,.smap .sm-node:hover rect{stroke:var(--accent);stroke-width:2}
.sm-l{font:600 11px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--ink)}.sm-s{font:11px ui-monospace,Menlo,Consolas,monospace;fill:var(--muted)}
.sm-tag{font:700 10px ui-monospace,Menlo,Consolas,monospace}.t-get{fill:var(--good)}.t-post{fill:var(--accent)}.t-put{fill:var(--warn)}.t-del{fill:var(--bad)}.t-any{fill:var(--muted)}
.n-page rect{stroke:var(--accent)!important;stroke-opacity:.55}.n-page.untraced{opacity:.55}.n-caller rect{fill:var(--surface-2)!important;stroke-dasharray:3 2}
.n-api.unknown rect{stroke:var(--muted)!important;stroke-dasharray:4 3}.n-api.guessed rect{stroke:var(--warn)!important}
.n-handler rect{fill:var(--accent-soft)!important;stroke:transparent}.n-handler.idle{opacity:.6}.n-module rect{fill:var(--surface-2)!important}
.n-table rect{fill:var(--good-soft)!important;stroke:transparent}.n-service rect{fill:var(--warn-soft)!important;stroke:transparent}
.n-service .sm-l{font-family:system-ui,-apple-system,"Segoe UI","Noto Sans Arabic",Tahoma,sans-serif}
.sm-band{fill:var(--surface-2);opacity:.75}.sm-band-l{font:700 10.5px ui-monospace,Menlo,Consolas,monospace;fill:var(--accent)}
.sm-sub-head{font-size:12px;font-weight:700;fill:var(--ink-2)}
.sm-edge{fill:none;stroke:var(--ink-2);opacity:.22}.sm-edge.k-use{opacity:.07}.sm-edge.k-data{opacity:.12}.sm-edge.k-uses{stroke:var(--accent);stroke-dasharray:2 3;opacity:.3}.sm-edge.k-data{stroke:var(--good)}
.sm-edge.k-guess{stroke-dasharray:4 3}.key-line .sm-edge{opacity:.9;stroke-width:2.2}
.smap.focus .sm-node{opacity:.18}.smap.focus .sm-node.on{opacity:1}.smap.focus .sm-node.on rect{stroke:var(--accent)!important;stroke-width:2;stroke-opacity:1}
.smap.focus .sm-edge{opacity:.03}.smap.focus .sm-edge.on{opacity:.9;stroke:var(--accent);stroke-width:1.8}.smap.focus .sm-edge.on.k-data{stroke:var(--good)}
.smap.focus .sm-node.hit rect{stroke:var(--warn)!important;stroke-width:2.5}
.key-box.sm-unknown{border-style:dashed;border-color:var(--muted)}
.sm-detail{margin-top:12px}.sm-detail h4 .lit{font-size:14px}.sm-group{margin:6px 0;font-size:13px}.sm-group b{margin-inline-end:6px}
.sm-chip{font:12px ui-monospace,Menlo,Consolas,monospace;border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:1px 9px;margin:2px;cursor:pointer;color:var(--ink);direction:ltr}
.sm-chip:hover{border-color:var(--accent);color:var(--accent)}.sm-table td{font-size:13px;max-width:240px}.sm-table .lit{word-break:normal;overflow-wrap:anywhere;display:inline-block;max-width:100%;margin:1px 0;font-size:12px}.sm-table td:first-child,.sm-table td:nth-child(2){white-space:nowrap}.sm-table tr[hidden]{display:none}
.errors{border-color:var(--bad);background:var(--bad-soft);margin-top:14px}.errors h4{color:var(--bad)}.errors ul{margin:4px 0 0;padding-inline-start:20px}
.stamp{margin-top:2px}.stamp .lit{font-size:12px}.stamp-foot{margin-top:6px}
.wl{display:grid;grid-template-columns:minmax(260px,1fr) 1.5fr;gap:18px;align-items:start}.wl-status{background:var(--accent-soft);border:0;box-shadow:none}
.wl-status h4{margin-bottom:4px}.wl-now{margin:6px 0;padding-inline-start:18px}.wl-now li{margin:3px 0}.wl-body h4{margin:0 0 10px}
.timeline{list-style:none;padding:0;margin:0 0 12px;position:relative}.timeline:before{content:"";position:absolute;inset-inline-start:6px;top:6px;bottom:6px;width:2px;background:var(--line)}
.wl-step{display:grid;grid-template-columns:14px 1fr;gap:12px;margin:0 0 12px;font-size:14px}.wl-dot{width:14px;height:14px;border-radius:50%;background:var(--surface);border:3px solid var(--accent);margin-top:5px;position:relative;z-index:1}
.wl-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.chip.who{background:var(--accent);color:var(--on-accent);font:600 12px system-ui,sans-serif}
.wl-notes{list-style:none;padding:0;margin:0}.wl-notes li{border-inline-start:3px solid var(--warn);padding:6px 10px;margin:6px 0;background:var(--bg);border-radius:6px;font-size:14px}
@media (max-width:760px){.wl{grid-template-columns:1fr}}
"""

SYSTEM_JS = r"""
(function(){var el=document.getElementById('eaos-system');if(!el)return;var D;try{D=JSON.parse(el.textContent)}catch(x){return}
var svgs=[].slice.call(document.querySelectorAll('svg.smap')),panel=document.getElementById('smd'),hint=panel?panel.innerHTML:'',pinned=null,base=null,hits=null;
function E(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function B(ar,en){return '<span class="l-ar" lang="ar">'+ar+'</span><span class="l-en" lang="en">'+en+'</span>'}
function N(v,m){return '<span class="n" data-meaning="'+E(m)+'">'+E(v)+'</span>'}
function L(s){return '<code class="lit" dir="ltr" data-literal="1">'+E(s)+'</code>'}
function rel(id){return new Set(D.rel[id]||[id])}
function mark(set){svgs.forEach(function(svg){svg.classList.toggle('focus',!!set);
svg.querySelectorAll('.sm-node').forEach(function(n){n.classList.toggle('on',!!set&&set.has(n.dataset.node));n.classList.toggle('hit',!!hits&&hits.has(n.dataset.node))});
svg.querySelectorAll('.sm-edge').forEach(function(e){e.classList.toggle('on',!!set&&set.has(e.dataset.from)&&set.has(e.dataset.to))})})}
var KIND={P:['صفحة','Page'],C:['كود مشترك يستدعي الخادم','Shared code that calls the server'],A:['نقطة API','API'],H:['ملف في الخادم','Server file'],M:['جزء','Part'],T:['جدول','Table'],S:['خدمة أو تخزين','Service or storage']};
var GROUP={P:['الصفحات','Pages'],C:['كود مشترك','Shared code'],A:['نقاط API','APIs'],H:['ملفات الخادم','Server files'],M:['الأجزاء','Parts'],T:['الجداول','Tables'],S:['الخدمات','Services']};
function name(id){var o=D.info[id]||{},k=id.charAt(0);if(k==='P')return o.route+' · '+o.component;if(k==="A")return o.key||id.slice(2);if(k==='H'||k==='C')return o.short||o.path||id.slice(2);if(k==='M')return o.short||o.name;return o.name||id.slice(2)}
function chip(id){return '<button type="button" class="sm-chip" data-to="'+E(id)+'">'+E(name(id))+'</button>'}
function p(x){return '<p class="small">'+x+'</p>'}
function detail(id){if(!panel)return;if(!id){panel.innerHTML=hint;return}
var o=D.info[id]||{},k=id.charAt(0),lines=[],r=D.rel[id]||[];
if(k==='P'){lines.push(B('ملف المكوّن:','Component file:')+' '+L(o.file));
if(!o.traced)lines.push(B('لم نجد ملف مكوّنها، فلم نتتبع ما تستدعيه.','Its component file was not found, so what it calls is not traced.'));
lines.push(B('تستدعي من ملفاتها: '+N(o.counts.calls,'APIs called from this page’s own files')+' · تصل إلى كود مشترك يستدعي الخادم: '+N(o.counts.shared,'shared files this page reaches'),
N(o.counts.calls,'APIs called from this page’s own files')+' APIs called from its own files · '+N(o.counts.shared,'shared files this page reaches')+' shared files that call the server'))}
if(k==='C'){lines.push(B('تصل إليه صفحات: '+N(o.counts.pages,'pages that reach this file')+' · يستدعي: '+N(o.counts.calls,'APIs this file calls'),N(o.counts.pages,'pages that reach this file')+' pages reach it · it calls '+N(o.counts.calls,'APIs this file calls')+' APIs'))}
if(k==='A'){lines.push(B('يستدعيها من الملفات:','Called in the files:')+' '+(o.callers.length?o.callers.map(L).join(' '):B('لا أحد وجدناه','none we found')));
if(o.handlers.length){lines.push(B('يجيبها في الخادم:','Answered on the server by:')+' '+o.handlers.map(function(h){return L(h.path)+(h.function?' '+L(h.function):'')}).join(' ')+(o.exact?'':' '+B('(من اسم الملف فقط؛ تحقق منه)','(from the file name only; check it)')))}
else lines.push(B('لم نجد في الخادم ما يجيبها: قد يأتي جوابها من خادم آخر، أو من مسار يُبنى وقت التشغيل.','No server code was found that answers it: the answer may come from another server, or from a route built at run time.'));
if(o.features&&o.features.length)lines.push(B('الميزة:','Feature:')+' '+o.features.map(L).join(' '))}
if(k==='H'&&!o.apis.length)lines.push(B('لم نجد في الكود من يستدعيه: قد يُستدعى من خارج البرنامج (رابط، أو webhook، أو مهمة مجدولة).','No call to it was found in the code: it may be called from outside the program (a link, a webhook, a scheduled job).'));
if(k==='T'&&o.files)lines.push(B('معرّف في:','Defined in:')+' '+o.files.map(L).join(' ')+' · '+B('لا نفرّق هنا بين القراءة والكتابة.','reading and writing are not told apart here.'));
var groups='';'PCAHMTS'.split('').forEach(function(g){var list=r.filter(function(x){return x.charAt(0)===g&&x!==id});if(!list.length)return;
groups+='<div class="sm-group"><b>'+B(GROUP[g][0],GROUP[g][1])+' '+N(o.counts.groups[g],'related items of this kind')+'</b>'+list.slice(0,40).map(chip).join('')+(list.length>40?' '+B('و'+N(o.counts.more[g],'more items')+' غيرها','and '+N(o.counts.more[g],'more items')+' more'):'')+'</div>'});
panel.innerHTML='<h4>'+B(KIND[k][0],KIND[k][1])+' '+L(name(id))+'</h4>'+lines.map(p).join('')+groups;
panel.querySelectorAll('.sm-chip').forEach(function(b){b.addEventListener('click',function(){select(b.dataset.to,true)})})}
function select(id,scroll){pinned=id;mark(id?rel(id):base);detail(id);if(scroll&&id){svgs.forEach(function(svg){if(!svg.getBoundingClientRect().width)return;
var n=svg.querySelector('[data-node="'+String(id).replace(/["\\]/g,'\\$&')+'"]');if(n&&n.scrollIntoView)n.scrollIntoView({block:'nearest',inline:'nearest'})})}}
svgs.forEach(function(svg){svg.querySelectorAll('.sm-node').forEach(function(n){var id=n.dataset.node;
n.addEventListener('mouseenter',function(){if(!pinned)mark(rel(id))});n.addEventListener('mouseleave',function(){if(!pinned)mark(base)});
function pick(){select(pinned===id?null:id)}n.addEventListener('click',pick);n.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}})})});
var q=document.getElementById('smq'),f=document.getElementById('smf'),out=document.getElementById('smshown'),lang=function(){return document.documentElement.getAttribute('data-lang')};
function filter(){var text=(q&&q.value||'').trim().toLowerCase(),feature=f&&f.value||'',set=null,count=0;hits=null;
if(feature){set=new Set();(D.features[feature]||[]).forEach(function(id){rel(id).forEach(function(x){set.add(x)})});count=D.feature_counts[feature]||0}
if(text){hits=new Set();(svgs[0]?svgs[0].querySelectorAll('.sm-node'):[]).forEach(function(n){if(n.dataset.search.indexOf(text)>=0)hits.add(n.dataset.node)});
if(!set){set=new Set(hits);if(hits.size<=5)hits.forEach(function(h){rel(h).forEach(function(x){set.add(x)})})}count=hits.size}
document.querySelectorAll('.sm-table tbody tr').forEach(function(row){row.hidden=!!text&&row.dataset.search.indexOf(text)<0});
base=set;pinned=null;mark(base);detail(null);if(out)out.textContent=(text||feature)?(lang()==='ar'?('المطابق: '+count):('Matching: '+count)):''}
if(q)q.addEventListener('input',filter);if(f)f.addEventListener('change',filter);
var c=document.getElementById('smclear');if(c)c.addEventListener('click',function(){if(q)q.value='';if(f)f.value='';filter()})})();
"""
