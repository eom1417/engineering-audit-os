(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})["mermaid.pieDiagram-CAPJLFHJ.js"]=function(require,exports,module){const e=require("./mermaid.chunk-Y2CYZVJY.js"),t=require("./mermaid.src.js"),n=require("./mermaid.chunk-VPRB5NB3.js"),r=require("./mermaid.ordinal.js"),i=require("./mermaid.path.js"),a=require("./mermaid.dist.js"),o=require("./mermaid.arc.js"),s=require("./mermaid.array.js"),c=require("./mermaid.chunk-3YJQHVM4.js"),l=require("./diagramEngine.js"),u=require("./mermaid.mermaid-parser.core.js"),d=require("./mermaid.chunk-JWPE2WC7.js");function f(e,t){return t<e?-1:t>e?1:t>=e?0:NaN}function p(e){return e}function m(){var e=p,t=f,n=null,r=i.n(0),o=i.n(a.m),c=i.n(0);function l(i){var l,u=(i=s.t(i)).length,d,f,p=0,m=Array(u),h=Array(u),g=+r.apply(this,arguments),_=Math.min(a.m,Math.max(-a.m,o.apply(this,arguments)-g)),v,y=Math.min(Math.abs(_)/u,c.apply(this,arguments)),b=y*(_<0?-1:1),x;for(l=0;l<u;++l)(x=h[m[l]=l]=+e(i[l],l,i))>0&&(p+=x);for(t==null?n!=null&&m.sort(function(e,t){return n(i[e],i[t])}):m.sort(function(e,n){return t(h[e],h[n])}),l=0,f=p?(_-u*b)/p:0;l<u;++l,g=v)d=m[l],x=h[d],v=g+(x>0?x*f:0)+b,h[d]={data:i[d],index:l,value:x,startAngle:g,endAngle:v,padAngle:y};return h}return l.value=function(t){return arguments.length?(e=typeof t==`function`?t:i.n(+t),l):e},l.sortValues=function(e){return arguments.length?(t=e,n=null,l):t},l.sort=function(e){return arguments.length?(n=e,t=null,l):n},l.startAngle=function(e){return arguments.length?(r=typeof e==`function`?e:i.n(+e),l):r},l.endAngle=function(e){return arguments.length?(o=typeof e==`function`?e:i.n(+e),l):o},l.padAngle=function(e){return arguments.length?(c=typeof e==`function`?e:i.n(+e),l):c},l}var h=n.f.pie,g={sections:new Map,showData:!1,config:h},_=g.sections,v=g.showData,y=structuredClone(h),b={getConfig:e.n(()=>structuredClone(y),`getConfig`),clear:e.n(()=>{_=new Map,v=g.showData,n.a()},`clear`),setDiagramTitle:n.q,getDiagramTitle:n.C,setAccTitle:n.U,getAccTitle:n.v,setAccDescription:n.H,getAccDescription:n._,addSection:e.n(({label:e,value:n})=>{if(n<0)throw Error(`"${e}" has invalid value: ${n}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);_.has(e)||(_.set(e,n),t.m.debug(`added new section: ${e}, with value: ${n}`))},`addSection`),getSections:e.n(()=>_,`getSections`),setShowData:e.n(e=>{v=e},`setShowData`),getShowData:e.n(()=>v,`getShowData`)},x=e.n((e,t)=>{d.t(e,t),t.setShowData(e.showData),e.sections.map(t.addSection)},`populateDb`),S={parse:e.n(async e=>{let n=await u.n(`pie`,e);t.m.debug(n),x(n,b)},`parse`)},C=e.n(e=>`
  .pieCircle{
    stroke: ${e.pieStrokeColor};
    stroke-width : ${e.pieStrokeWidth};
    opacity : ${e.pieOpacity};
  }
  .pieCircle.highlighted{
    scale: 1.05;
    opacity: 1;
  }
  .pieCircle.highlightedOnHover:hover{
    transition-duration: 250ms;
    scale: 1.05;
    opacity: 1;
  }
  .pieOuterCircle{
    stroke: ${e.pieOuterStrokeColor};
    stroke-width: ${e.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${e.pieTitleTextSize};
    fill: ${e.pieTitleTextColor};
    font-family: ${e.fontFamily};
  }
  .slice {
    font-family: ${e.fontFamily};
    fill: ${e.pieSectionTextColor};
    font-size:${e.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${e.pieLegendTextColor};
    font-family: ${e.fontFamily};
    font-size: ${e.pieLegendTextSize};
  }
`,`getStyles`),w=e.n(e=>{let t=[...e.values()].reduce((e,t)=>e+t,0),n=[...e.entries()].map(([e,t])=>({label:e,value:t})).filter(e=>e.value/t*100>=1);return m().value(e=>e.value).sort(null)(n)},`createPieArcs`),T={parser:S,db:b,renderer:{draw:e.n((e,i,a,s)=>{t.m.debug(`rendering pie chart
`+e);let u=s.db,d=n.b(),f=c.i(u.getConfig(),d.pie),p=l.o(i),m=p.append(`g`);m.attr(`transform`,`translate(225,225)`);let{themeVariables:h}=d,[g]=c.m(h.pieOuterStrokeWidth);g??=2;let _=f.legendPosition,v=f.textPosition,y=f.donutHole>0&&f.donutHole<=.9?f.donutHole:0,b=o.t().innerRadius(y*185).outerRadius(185),x=o.t().innerRadius(185*v).outerRadius(185*v),S=m.append(`g`);S.append(`circle`).attr(`cx`,0).attr(`cy`,0).attr(`r`,185+g/2).attr(`class`,`pieOuterCircle`);let C=u.getSections(),T=w(C),E=[h.pie1,h.pie2,h.pie3,h.pie4,h.pie5,h.pie6,h.pie7,h.pie8,h.pie9,h.pie10,h.pie11,h.pie12],D=0;C.forEach(e=>{D+=e});let O=T.filter(e=>(e.data.value/D*100).toFixed(0)!==`0`),k=r.t(E).domain([...C.keys()]);S.selectAll(`mySlices`).data(O).enter().append(`path`).attr(`d`,b).attr(`fill`,e=>k(e.data.label)).attr(`class`,e=>{let t=`pieCircle`;return f.highlightSlice===`hover`?t+=` highlightedOnHover`:f.highlightSlice===e.data.label&&(t+=` highlighted`),t}),S.selectAll(`mySlices`).data(O).enter().append(`text`).text(e=>(e.data.value/D*100).toFixed(0)+`%`).attr(`transform`,e=>`translate(`+x.centroid(e)+`)`).style(`text-anchor`,`middle`).attr(`class`,`slice`);let A=m.append(`text`).text(u.getDiagramTitle()).attr(`x`,0).attr(`y`,-200).attr(`class`,`pieTitleText`),j=[...C.entries()].map(([e,t])=>({label:e,value:t})),M=m.selectAll(`.legend`).data(j).enter().append(`g`).attr(`class`,`legend`);M.append(`rect`).attr(`width`,18).attr(`height`,18).style(`fill`,e=>k(e.label)).style(`stroke`,e=>k(e.label)),M.append(`text`).attr(`x`,22).attr(`y`,14).text(e=>u.getShowData()?`${e.label} [${e.value}]`:e.label);let N=Math.max(...M.selectAll(`text`).nodes().map(e=>e?.getBoundingClientRect().width??0)),P=450,F=490,I=j.length*22;switch(_){case`center`:M.attr(`transform`,(e,t)=>{let n=22*j.length/2,r=-N/2-22,i=t*22-n;return`translate(`+r+`,`+i+`)`});break;case`top`:P+=I,M.attr(`transform`,(e,t)=>`translate(${-N/2-22}, ${t*22-185})`),S.attr(`transform`,()=>`translate(0, ${I+22})`);break;case`bottom`:P+=I,M.attr(`transform`,(e,t)=>{let n=-N/2-22,r=t*22- -207;return`translate(`+n+`,`+r+`)`});break;case`left`:F+=22+N,M.attr(`transform`,(e,t)=>{let n=22*j.length/2;return`translate(-207,`+(t*22-n)+`)`}),S.attr(`transform`,()=>`translate(${N+18+4}, 0)`);break;default:F+=22+N,M.attr(`transform`,(e,t)=>{let n=22*j.length/2;return`translate(216,`+(t*22-n)+`)`})}let L=A.node()?.getBoundingClientRect().width??0,R=225-L/2,z=225+L/2,B=Math.min(0,R),V=Math.max(F,z)-B;p.attr(`viewBox`,`${B} 0 ${V} ${P}`),n.c(p,P,V,f.useMaxWidth)},`draw`)},styles:C};exports.diagram=T;
};
