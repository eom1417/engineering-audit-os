(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})["mermaid.diagram-UMYRVEAY.js"]=function(require,exports,module){const e=require("./mermaid.chunk-Y2CYZVJY.js"),t=require("./mermaid.src.js"),n=require("./mermaid.chunk-VPRB5NB3.js"),r=require("./mermaid.chunk-3YJQHVM4.js"),i=require("./diagramEngine.js"),a=require("./mermaid.mermaid-parser.core.js"),o=require("./mermaid.chunk-JWPE2WC7.js");var s=n.f.packet,c=class{constructor(){this.packet=[],this.setAccTitle=n.U,this.getAccTitle=n.v,this.setDiagramTitle=n.q,this.getDiagramTitle=n.C,this.getAccDescription=n._,this.setAccDescription=n.H}static{e.n(this,`PacketDB`)}getConfig(){let e=r.i({...s,...n.y().packet});return e.showBits&&(e.paddingY+=10),e}getPacket(){return this.packet}pushWord(e){e.length>0&&this.packet.push(e)}clear(){n.a(),this.packet=[]}},l=1e4,u=e.n((e,n)=>{o.t(e,n);let r=-1,i=[],a=1,{bitsPerRow:s}=n.getConfig();for(let{start:o,end:c,bits:u,label:f}of e.blocks){if(o!==void 0&&c!==void 0&&c<o)throw Error(`Packet block ${o} - ${c} is invalid. End must be greater than start.`);if(o??=r+1,o!==r+1)throw Error(`Packet block ${o} - ${c??o} is not contiguous. It should start from ${r+1}.`);if(u===0)throw Error(`Packet block ${o} is invalid. Cannot have a zero bit field.`);for(c??=o+(u??1)-1,u??=c-o+1,r=c,t.m.debug(`Packet block ${o} - ${r} with label ${f}`);i.length<=s+1&&n.getPacket().length<l;){let[e,t]=d({start:o,end:c,bits:u,label:f},a,s);if(i.push(e),e.end+1===a*s&&(n.pushWord(i),i=[],a++),!t)break;({start:o,end:c,bits:u,label:f}=t)}}n.pushWord(i)},`populate`),d=e.n((e,t,n)=>{if(e.start===void 0)throw Error(`start should have been set during first phase`);if(e.end===void 0)throw Error(`end should have been set during first phase`);if(e.start>e.end)throw Error(`Block start ${e.start} is greater than block end ${e.end}.`);if(e.end+1<=t*n)return[e,void 0];let r=t*n-1,i=t*n;return[{start:e.start,end:r,label:e.label,bits:r-e.start},{start:i,end:e.end,label:e.label,bits:e.end-i}]},`getNextFittingBlock`),f={parser:{yy:void 0},parse:e.n(async e=>{let n=await a.n(`packet`,e),r=f.parser?.yy;if(!(r instanceof c))throw Error(`parser.parser?.yy was not a PacketDB. This is due to a bug within Mermaid, please report this issue at `);t.m.debug(n),u(n,r)},`parse`)},p=e.n((e,t,r,a)=>{let o=a.db,s=o.getConfig(),{rowHeight:c,paddingY:l,bitWidth:u,bitsPerRow:d}=s,f=o.getPacket(),p=o.getDiagramTitle(),h=c+l,g=h*(f.length+1)-(p?0:c),_=u*d+2,v=i.o(t);v.attr(`viewBox`,`0 0 ${_} ${g}`),n.c(v,g,_,s.useMaxWidth);for(let[e,t]of f.entries())m(v,t,e,s);v.append(`text`).text(p).attr(`x`,_/2).attr(`y`,g-h/2).attr(`dominant-baseline`,`middle`).attr(`text-anchor`,`middle`).attr(`class`,`packetTitle`)},`draw`),m=e.n((e,t,n,{rowHeight:r,paddingX:i,paddingY:a,bitWidth:o,bitsPerRow:s,showBits:c,bitOrder:l})=>{let u=e.append(`g`),d=n*(r+a)+a,f=l===`descending`;for(let e of t){let t=e.end-e.start+1,n=e.start%s,a=(f?s-n-t:n)*o+1,l=t*o-i;if(u.append(`rect`).attr(`x`,a).attr(`y`,d).attr(`width`,l).attr(`height`,r).attr(`class`,`packetBlock`),u.append(`text`).attr(`x`,a+l/2).attr(`y`,d+r/2).attr(`class`,`packetLabel`).attr(`dominant-baseline`,`middle`).attr(`text-anchor`,`middle`).text(e.label),!c)continue;let[p,m]=f?[e.end,e.start]:[e.start,e.end],h=t===1,g=d-2;u.append(`text`).attr(`x`,a+(h?l/2:0)).attr(`y`,g).attr(`class`,`packetByte start`).attr(`dominant-baseline`,`auto`).attr(`text-anchor`,h?`middle`:`start`).text(p),h||u.append(`text`).attr(`x`,a+l).attr(`y`,g).attr(`class`,`packetByte end`).attr(`dominant-baseline`,`auto`).attr(`text-anchor`,`end`).text(m)}},`drawWord`),h={draw:p},g={byteFontSize:`10px`,startByteColor:`black`,endByteColor:`black`,labelColor:`black`,labelFontSize:`12px`,titleColor:`black`,titleFontSize:`14px`,blockStrokeColor:`black`,blockStrokeWidth:`1`,blockFillColor:`#efefef`},_={parser:f,get db(){return new c},renderer:h,styles:e.n(({packet:e}={})=>{let t=r.i(g,e);return`
	.packetByte {
		font-size: ${t.byteFontSize};
	}
	.packetByte.start {
		fill: ${t.startByteColor};
	}
	.packetByte.end {
		fill: ${t.endByteColor};
	}
	.packetLabel {
		fill: ${t.labelColor};
		font-size: ${t.labelFontSize};
	}
	.packetTitle {
		fill: ${t.titleColor};
		font-size: ${t.titleFontSize};
	}
	.packetBlock {
		stroke: ${t.blockStrokeColor};
		stroke-width: ${t.blockStrokeWidth};
		fill: ${t.blockFillColor};
	}
	`},`styles`)};exports.diagram=_;
};
