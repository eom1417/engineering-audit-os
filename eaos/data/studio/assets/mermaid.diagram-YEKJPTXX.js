(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})["mermaid.diagram-YEKJPTXX.js"]=function(require,exports,module){const e=require("./mermaid.chunk-Y2CYZVJY.js"),t=require("./mermaid.src.js"),n=require("./mermaid.chunk-VPRB5NB3.js"),r=require("./mermaid.chunk-3YJQHVM4.js"),i=require("./diagramEngine.js"),a=require("./mermaid.mermaid-parser.core.js"),o=require("./mermaid.chunk-JWPE2WC7.js");var s={showLegend:!0,ticks:5,max:null,min:0,graticule:`circle`},c=32,l={axes:[],curves:[],options:s},u=structuredClone(l),d=n.f.radar,f=e.n(()=>r.i({...d,...n.y().radar}),`getConfig`),p=e.n(()=>u.axes,`getAxes`),m=e.n(()=>u.curves,`getCurves`),h=e.n(()=>u.options,`getOptions`),g=e.n(e=>{u.axes=e.map(e=>({name:e.name,label:e.label??e.name}))},`setAxes`),_=e.n(e=>{u.curves=e.map(e=>({name:e.name,label:e.label??e.name,entries:v(e.entries)}))},`setCurves`),v=e.n(e=>{if(e[0].axis==null)return e.map(e=>e.value);let t=p();if(t.length===0)throw Error(`Axes must be populated before curves for reference entries`);return t.map(t=>{let n=e.find(e=>e.axis?.$refText===t.name);if(n===void 0)throw Error(`Missing entry for axis `+t.label);return n.value})},`computeCurveEntries`),y={getAxes:p,getCurves:m,getOptions:h,setAxes:g,setCurves:_,setOptions:e.n(e=>{let n=e.reduce((e,t)=>(e[t.name]=t,e),{});u.options={showLegend:n.showLegend?.value??s.showLegend,ticks:n.ticks?.value??s.ticks,max:n.max?.value??s.max,min:n.min?.value??s.min,graticule:n.graticule?.value??s.graticule},u.options.ticks>c&&(t.m.warn(`Radar diagram ticks (${u.options.ticks}) exceeds maximum allowed (${c}). Using ${c} instead.`),u.options.ticks=c)},`setOptions`),getConfig:f,clear:e.n(()=>{n.a(),u=structuredClone(l)},`clear`),setAccTitle:n.U,getAccTitle:n.v,setDiagramTitle:n.q,getDiagramTitle:n.C,getAccDescription:n._,setAccDescription:n.H},b=e.n(e=>{o.t(e,y);let{axes:t,curves:n,options:r}=e;y.setAxes(t),y.setCurves(n),y.setOptions(r)},`populate`),x={parse:e.n(async e=>{let n=await a.n(`radar`,e);t.m.debug(n),b(n)},`parse`)},S=e.n((e,t,n,r)=>{let a=r.db,o=a.getAxes(),s=a.getCurves(),c=a.getOptions(),l=a.getConfig(),u=a.getDiagramTitle(),d=C(i.o(t),l),f=c.max??Math.max(...s.map(e=>Math.max(...e.entries))),p=c.min,m=Math.min(l.width,l.height)/2;w(d,o,m,c.ticks,c.graticule),T(d,o,m,l),E(d,o,s,p,f,c.graticule,l),k(d,s,c.showLegend,l),d.append(`text`).attr(`class`,`radarTitle`).text(u).attr(`x`,0).attr(`y`,-l.height/2-l.marginTop)},`draw`),C=e.n((e,t)=>{let r=t.width+t.marginLeft+t.marginRight,i=t.height+t.marginTop+t.marginBottom,a={x:t.marginLeft+t.width/2,y:t.marginTop+t.height/2};return n.c(e,i,r,t.useMaxWidth??!0),e.attr(`viewBox`,`0 0 ${r} ${i}`).attr(`overflow`,`visible`),e.append(`g`).attr(`transform`,`translate(${a.x}, ${a.y})`)},`drawFrame`),w=e.n((e,t,n,r,i)=>{if(i===`circle`)for(let t=0;t<r;t++){let i=n*(t+1)/r;e.append(`circle`).attr(`r`,i).attr(`class`,`radarGraticule`)}else if(i===`polygon`){let i=t.length;for(let a=0;a<r;a++){let o=n*(a+1)/r,s=t.map((e,t)=>{let n=2*t*Math.PI/i-Math.PI/2;return`${o*Math.cos(n)},${o*Math.sin(n)}`}).join(` `);e.append(`polygon`).attr(`points`,s).attr(`class`,`radarGraticule`)}}},`drawGraticule`),T=e.n((e,t,n,r)=>{let i=t.length;for(let a=0;a<i;a++){let o=t[a].label,s=2*a*Math.PI/i-Math.PI/2,c=Math.cos(s),l=Math.sin(s);e.append(`line`).attr(`x1`,0).attr(`y1`,0).attr(`x2`,n*r.axisScaleFactor*c).attr(`y2`,n*r.axisScaleFactor*l).attr(`class`,`radarAxisLine`);let u=c>.01?`start`:c<-.01?`end`:`middle`,d=l>.01?`hanging`:l<-.01?`auto`:`central`;e.append(`text`).text(o).attr(`x`,n*r.axisLabelFactor*c+4*c).attr(`y`,n*r.axisLabelFactor*l+4*l).attr(`text-anchor`,u).attr(`dominant-baseline`,d).attr(`class`,`radarAxisLabel`)}},`drawAxes`);function E(e,t,n,r,i,a,o){let s=t.length,c=Math.min(o.width,o.height)/2;n.forEach((t,n)=>{if(t.entries.length!==s)return;let l=t.entries.map((e,t)=>{let n=2*Math.PI*t/s-Math.PI/2,a=D(e,r,i,c);return{x:a*Math.cos(n),y:a*Math.sin(n)}});a===`circle`?e.append(`path`).attr(`d`,O(l,o.curveTension)).attr(`class`,`radarCurve-${n}`):a===`polygon`&&e.append(`polygon`).attr(`points`,l.map(e=>`${e.x},${e.y}`).join(` `)).attr(`class`,`radarCurve-${n}`)})}e.n(E,`drawCurves`);function D(e,t,n,r){return r*(Math.min(Math.max(e,t),n)-t)/(n-t)}e.n(D,`relativeRadius`);function O(e,t){let n=e.length,r=`M${e[0].x},${e[0].y}`;for(let i=0;i<n;i++){let a=e[(i-1+n)%n],o=e[i],s=e[(i+1)%n],c=e[(i+2)%n],l={x:o.x+(s.x-a.x)*t,y:o.y+(s.y-a.y)*t},u={x:s.x-(c.x-o.x)*t,y:s.y-(c.y-o.y)*t};r+=` C${l.x},${l.y} ${u.x},${u.y} ${s.x},${s.y}`}return`${r} Z`}e.n(O,`closedRoundCurve`);function k(e,t,n,r){if(!n)return;let i=(r.width/2+r.marginRight)*3/4,a=-(r.height/2+r.marginTop)*3/4;t.forEach((t,n)=>{let r=e.append(`g`).attr(`transform`,`translate(${i}, ${a+n*20})`);r.append(`rect`).attr(`width`,12).attr(`height`,12).attr(`class`,`radarLegendBox-${n}`),r.append(`text`).attr(`x`,16).attr(`y`,0).attr(`class`,`radarLegendText`).text(t.label)})}e.n(k,`drawLegend`);var A={draw:S},j=e.n((e,t)=>{let n=``;for(let r=0;r<e.THEME_COLOR_LIMIT;r++){let i=e[`cScale${r}`];n+=`
		.radarCurve-${r} {
			color: ${i};
			fill: ${i};
			fill-opacity: ${t.curveOpacity};
			stroke: ${i};
			stroke-width: ${t.curveStrokeWidth};
		}
		.radarLegendBox-${r} {
			fill: ${i};
			fill-opacity: ${t.curveOpacity};
			stroke: ${i};
		}
		`}return n},`genIndexStyles`),M=e.n(e=>{let t=n.E(),i=n.y(),a=r.i(t,i.themeVariables);return{themeVariables:a,radarOptions:r.i(a.radar,e)}},`buildRadarStyleOptions`),N={parser:x,db:y,renderer:A,styles:e.n(({radar:e}={})=>{let{themeVariables:t,radarOptions:n}=M(e);return`
	.radarTitle {
		font-size: ${t.fontSize};
		color: ${t.titleColor};
		dominant-baseline: hanging;
		text-anchor: middle;
	}
	.radarAxisLine {
		stroke: ${n.axisColor};
		stroke-width: ${n.axisStrokeWidth};
	}
	.radarAxisLabel {
		font-size: ${n.axisLabelFontSize}px;
		color: ${n.axisColor};
	}
	.radarGraticule {
		fill: ${n.graticuleColor};
		fill-opacity: ${n.graticuleOpacity};
		stroke: ${n.graticuleColor};
		stroke-width: ${n.graticuleStrokeWidth};
	}
	.radarLegendText {
		text-anchor: start;
		font-size: ${n.legendFontSize}px;
		dominant-baseline: hanging;
	}
	${j(t,n)}
	`},`styles`)};exports.diagram=N;
};
