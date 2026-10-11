(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})["mermaid.diagram-UMYRVEAY.js"]=function(require,exports,module){const e=require("./mermaid.mermaid-parser.core.js"),t=require("./mermaid.chunk-Y2CYZVJY.js"),n=require("./mermaid.src.js"),r=require("./mermaid.chunk-VPRB5NB3.js"),i=require("./mermaid.chunk-3YJQHVM4.js"),a=require("./mermaid.chunk-JWPE2WC7.js"),o=require("./diagramEngine.js");var s=r.f.packet,c=class{constructor(){this.packet=[],this.setAccTitle=r.U,this.getAccTitle=r.v,this.setDiagramTitle=r.q,this.getDiagramTitle=r.C,this.getAccDescription=r._,this.setAccDescription=r.H}static{t.n(this,`PacketDB`)}getConfig(){let e=i.i({...s,...r.y().packet});return e.showBits&&(e.paddingY+=10),e}getPacket(){return this.packet}pushWord(e){e.length>0&&this.packet.push(e)}clear(){r.a(),this.packet=[]}},l=1e4,u=t.n((e,t)=>{a.t(e,t);let r=-1,i=[],o=1,{bitsPerRow:s}=t.getConfig();for(let{start:a,end:c,bits:u,label:f}of e.blocks){if(a!==void 0&&c!==void 0&&c<a)throw Error(`Packet block ${a} - ${c} is invalid. End must be greater than start.`);if(a??=r+1,a!==r+1)throw Error(`Packet block ${a} - ${c??a} is not contiguous. It should start from ${r+1}.`);if(u===0)throw Error(`Packet block ${a} is invalid. Cannot have a zero bit field.`);for(c??=a+(u??1)-1,u??=c-a+1,r=c,n.m.debug(`Packet block ${a} - ${r} with label ${f}`);i.length<=s+1&&t.getPacket().length<l;){let[e,n]=d({start:a,end:c,bits:u,label:f},o,s);if(i.push(e),e.end+1===o*s&&(t.pushWord(i),i=[],o++),!n)break;({start:a,end:c,bits:u,label:f}=n)}}t.pushWord(i)},`populate`),d=t.n((e,t,n)=>{if(e.start===void 0)throw Error(`start should have been set during first phase`);if(e.end===void 0)throw Error(`end should have been set during first phase`);if(e.start>e.end)throw Error(`Block start ${e.start} is greater than block end ${e.end}.`);if(e.end+1<=t*n)return[e,void 0];let r=t*n-1,i=t*n;return[{start:e.start,end:r,label:e.label,bits:r-e.start},{start:i,end:e.end,label:e.label,bits:e.end-i}]},`getNextFittingBlock`),f={parser:{yy:void 0},parse:t.n(async t=>{let r=await e.n(`packet`,t),i=f.parser?.yy;if(!(i instanceof c))throw Error(`parser.parser?.yy was not a PacketDB. This is due to a bug within Mermaid, please report this issue at `);n.m.debug(r),u(r,i)},`parse`)},p=t.n((e,t,n,i)=>{let a=i.db,s=a.getConfig(),{rowHeight:c,paddingY:l,bitWidth:u,bitsPerRow:d}=s,f=a.getPacket(),p=a.getDiagramTitle(),h=c+l,g=h*(f.length+1)-(p?0:c),_=u*d+2,v=o.o(t);v.attr(`viewBox`,`0 0 ${_} ${g}`),r.c(v,g,_,s.useMaxWidth);for(let[e,t]of f.entries())m(v,t,e,s);v.append(`text`).text(p).attr(`x`,_/2).attr(`y`,g-h/2).attr(`dominant-baseline`,`middle`).attr(`text-anchor`,`middle`).attr(`class`,`packetTitle`)},`draw`),m=t.n((e,t,n,{rowHeight:r,paddingX:i,paddingY:a,bitWidth:o,bitsPerRow:s,showBits:c,bitOrder:l})=>{let u=e.append(`g`),d=n*(r+a)+a,f=l===`descending`;for(let e of t){let t=e.end-e.start+1,n=e.start%s,a=(f?s-n-t:n)*o+1,l=t*o-i;if(u.append(`rect`).attr(`x`,a).attr(`y`,d).attr(`width`,l).attr(`height`,r).attr(`class`,`packetBlock`),u.append(`text`).attr(`x`,a+l/2).attr(`y`,d+r/2).attr(`class`,`packetLabel`).attr(`dominant-baseline`,`middle`).attr(`text-anchor`,`middle`).text(e.label),!c)continue;let[p,m]=f?[e.end,e.start]:[e.start,e.end],h=t===1,g=d-2;u.append(`text`).attr(`x`,a+(h?l/2:0)).attr(`y`,g).attr(`class`,`packetByte start`).attr(`dominant-baseline`,`auto`).attr(`text-anchor`,h?`middle`:`start`).text(p),h||u.append(`text`).attr(`x`,a+l).attr(`y`,g).attr(`class`,`packetByte end`).attr(`dominant-baseline`,`auto`).attr(`text-anchor`,`end`).text(m)}},`drawWord`),h={draw:p},g={byteFontSize:`10px`,startByteColor:`black`,endByteColor:`black`,labelColor:`black`,labelFontSize:`12px`,titleColor:`black`,titleFontSize:`14px`,blockStrokeColor:`black`,blockStrokeWidth:`1`,blockFillColor:`#efefef`},_={parser:f,get db(){return new c},renderer:h,styles:t.n(({packet:e}={})=>{let t=i.i(g,e);return`
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
