(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})["mermaid.journeyDiagram-COXZFDF6.js"]=function(require,exports,module){const e=require("./mermaid.chunk-Y2CYZVJY.js"),t=require("./mermaid.src.js"),n=require("./mermaid.chunk-VPRB5NB3.js"),r=require("./mermaid.arc.js"),i=require("./mermaid.chunk-5VM5RSS4.js"),a=require("./mermaid.chunk-7TKQ45FW.js");var o=(function(){var t=e.n(function(e,t,n,r){for(n||={},r=e.length;r--;n[e[r]]=t);return n},`o`),n=[6,8,10,11,12,14,16,17,18],r=[1,9],i=[1,10],a=[1,11],o=[1,12],s=[1,13],c=[1,14],l={trace:e.n(function(){},`trace`),yy:{},symbols_:{error:2,start:3,journey:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NEWLINE:10,title:11,acc_title:12,acc_title_value:13,acc_descr:14,acc_descr_value:15,acc_descr_multiline_value:16,section:17,taskName:18,taskData:19,$accept:0,$end:1},terminals_:{2:`error`,4:`journey`,6:`EOF`,8:`SPACE`,10:`NEWLINE`,11:`title`,12:`acc_title`,13:`acc_title_value`,14:`acc_descr`,15:`acc_descr_value`,16:`acc_descr_multiline_value`,17:`section`,18:`taskName`,19:`taskData`},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,2]],performAction:e.n(function(e,t,n,r,i,a,o){var s=a.length-1;switch(i){case 1:return a[s-1];case 2:this.$=[];break;case 3:a[s-1].push(a[s]),this.$=a[s-1];break;case 4:case 5:this.$=a[s];break;case 6:case 7:this.$=[];break;case 8:r.setDiagramTitle(a[s].substr(6)),this.$=a[s].substr(6);break;case 9:this.$=a[s].trim(),r.setAccTitle(this.$);break;case 10:case 11:this.$=a[s].trim(),r.setAccDescription(this.$);break;case 12:r.addSection(a[s].substr(8)),this.$=a[s].substr(8);break;case 13:r.addTask(a[s-1],a[s]),this.$=`task`}},`anonymous`),table:[{3:1,4:[1,2]},{1:[3]},t(n,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:r,12:i,14:a,16:o,17:s,18:c},t(n,[2,7],{1:[2,1]}),t(n,[2,3]),{9:15,11:r,12:i,14:a,16:o,17:s,18:c},t(n,[2,5]),t(n,[2,6]),t(n,[2,8]),{13:[1,16]},{15:[1,17]},t(n,[2,11]),t(n,[2,12]),{19:[1,18]},t(n,[2,4]),t(n,[2,9]),t(n,[2,10]),t(n,[2,13])],defaultActions:{},parseError:e.n(function(e,t){if(t.recoverable)this.trace(e);else{var n=Error(e);throw n.hash=t,n}},`parseError`),parse:e.n(function(t){var n=this,r=[0],i=[],a=[null],o=[],s=this.table,c=``,l=0,u=0,d=0,f=2,p=1,m=o.slice.call(arguments,1),h=Object.create(this.lexer),g={yy:{}};for(var _ in this.yy)Object.prototype.hasOwnProperty.call(this.yy,_)&&(g.yy[_]=this.yy[_]);h.setInput(t,g.yy),g.yy.lexer=h,g.yy.parser=this,h.yylloc===void 0&&(h.yylloc={});var v=h.yylloc;o.push(v);var y=h.options&&h.options.ranges;this.parseError=typeof g.yy.parseError==`function`?g.yy.parseError:Object.getPrototypeOf(this).parseError;function b(e){r.length-=2*e,a.length-=e,o.length-=e}e.n(b,`popStack`);function x(){var e=i.pop()||h.lex()||p;return typeof e!=`number`&&(e instanceof Array&&(i=e,e=i.pop()),e=n.symbols_[e]||e),e}e.n(x,`lex`);for(var S,C,w,T,E,D={},O,k,A,j;;){if(w=r[r.length-1],this.defaultActions[w]?T=this.defaultActions[w]:(S??=x(),T=s[w]&&s[w][S]),T===void 0||!T.length||!T[0]){var M=``;for(O in j=[],s[w])this.terminals_[O]&&O>f&&j.push(`'`+this.terminals_[O]+`'`);M=h.showPosition?`Parse error on line `+(l+1)+`:
`+h.showPosition()+`
Expecting `+j.join(`, `)+`, got '`+(this.terminals_[S]||S)+`'`:`Parse error on line `+(l+1)+`: Unexpected `+(S==p?`end of input`:`'`+(this.terminals_[S]||S)+`'`),this.parseError(M,{text:h.match,token:this.terminals_[S]||S,line:h.yylineno,loc:v,expected:j})}if(T[0]instanceof Array&&T.length>1)throw Error(`Parse Error: multiple actions possible at state: `+w+`, token: `+S);switch(T[0]){case 1:r.push(S),a.push(h.yytext),o.push(h.yylloc),r.push(T[1]),S=null,C?(S=C,C=null):(u=h.yyleng,c=h.yytext,l=h.yylineno,v=h.yylloc,d>0&&d--);break;case 2:if(k=this.productions_[T[1]][1],D.$=a[a.length-k],D._$={first_line:o[o.length-(k||1)].first_line,last_line:o[o.length-1].last_line,first_column:o[o.length-(k||1)].first_column,last_column:o[o.length-1].last_column},y&&(D._$.range=[o[o.length-(k||1)].range[0],o[o.length-1].range[1]]),E=this.performAction.apply(D,[c,u,l,g.yy,T[1],a,o].concat(m)),E!==void 0)return E;k&&(r=r.slice(0,-1*k*2),a=a.slice(0,-1*k),o=o.slice(0,-1*k)),r.push(this.productions_[T[1]][0]),a.push(D.$),o.push(D._$),A=s[r[r.length-2]][r[r.length-1]],r.push(A);break;case 3:return!0}}return!0},`parse`)};l.lexer=(function(){return{EOF:1,parseError:e.n(function(e,t){if(this.yy.parser)this.yy.parser.parseError(e,t);else throw Error(e)},`parseError`),setInput:e.n(function(e,t){return this.yy=t||this.yy||{},this._input=e,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match=``,this.conditionStack=[`INITIAL`],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},`setInput`),input:e.n(function(){var e=this._input[0];return this.yytext+=e,this.yyleng++,this.offset++,this.match+=e,this.matched+=e,e.match(/(?:\r\n?|\n).*/g)?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),e},`input`),unput:e.n(function(e){var t=e.length,n=e.split(/(?:\r\n?|\n)/g);this._input=e+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-t),this.offset-=t;var r=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),n.length-1&&(this.yylineno-=n.length-1);var i=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:n?(n.length===r.length?this.yylloc.first_column:0)+r[r.length-n.length].length-n[0].length:this.yylloc.first_column-t},this.options.ranges&&(this.yylloc.range=[i[0],i[0]+this.yyleng-t]),this.yyleng=this.yytext.length,this},`unput`),more:e.n(function(){return this._more=!0,this},`more`),reject:e.n(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError(`Lexical error on line `+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:``,token:null,line:this.yylineno});return this},`reject`),less:e.n(function(e){this.unput(this.match.slice(e))},`less`),pastInput:e.n(function(){var e=this.matched.substr(0,this.matched.length-this.match.length);return(e.length>20?`...`:``)+e.substr(-20).replace(/\n/g,``)},`pastInput`),upcomingInput:e.n(function(){var e=this.match;return e.length<20&&(e+=this._input.substr(0,20-e.length)),(e.substr(0,20)+(e.length>20?`...`:``)).replace(/\n/g,``)},`upcomingInput`),showPosition:e.n(function(){var e=this.pastInput(),t=Array(e.length+1).join(`-`);return e+this.upcomingInput()+`
`+t+`^`},`showPosition`),test_match:e.n(function(e,t){var n,r,i;if(this.options.backtrack_lexer&&(i={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(i.yylloc.range=this.yylloc.range.slice(0))),r=e[0].match(/(?:\r\n?|\n).*/g),r&&(this.yylineno+=r.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:r?r[r.length-1].length-r[r.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+e[0].length},this.yytext+=e[0],this.match+=e[0],this.matches=e,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(e[0].length),this.matched+=e[0],n=this.performAction.call(this,this.yy,this,t,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),n)return n;if(this._backtrack){for(var a in i)this[a]=i[a];return!1}return!1},`test_match`),next:e.n(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var e,t,n,r;this._more||(this.yytext=``,this.match=``);for(var i=this._currentRules(),a=0;a<i.length;a++)if(n=this._input.match(this.rules[i[a]]),n&&(!t||n[0].length>t[0].length)){if(t=n,r=a,this.options.backtrack_lexer){if(e=this.test_match(n,i[a]),e!==!1)return e;if(this._backtrack){t=!1;continue}return!1}if(!this.options.flex)break}return t?(e=this.test_match(t,i[r]),e!==!1&&e):this._input===``?this.EOF:this.parseError(`Lexical error on line `+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:``,token:null,line:this.yylineno})},`next`),lex:e.n(function(){return this.next()||this.lex()},`lex`),begin:e.n(function(e){this.conditionStack.push(e)},`begin`),popState:e.n(function(){return this.conditionStack.length-1>0?this.conditionStack.pop():this.conditionStack[0]},`popState`),_currentRules:e.n(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},`_currentRules`),topState:e.n(function(e){return e=this.conditionStack.length-1-Math.abs(e||0),e>=0?this.conditionStack[e]:`INITIAL`},`topState`),pushState:e.n(function(e){this.begin(e)},`pushState`),stateStackSize:e.n(function(){return this.conditionStack.length},`stateStackSize`),options:{"case-insensitive":!0},performAction:e.n(function(e,t,n,r){switch(n){case 0:break;case 1:break;case 2:return 10;case 3:break;case 4:break;case 5:return 4;case 6:return 11;case 7:return this.begin(`acc_title`),12;case 8:return this.popState(),`acc_title_value`;case 9:return this.begin(`acc_descr`),14;case 10:return this.popState(),`acc_descr_value`;case 11:this.begin(`acc_descr_multiline`);break;case 12:this.popState();break;case 13:return`acc_descr_multiline_value`;case 14:return 17;case 15:return 18;case 16:return 19;case 17:return`:`;case 18:return 6;case 19:return`INVALID`}},`anonymous`),rules:[/^(?:%(?!\{)[^\n]*)/i,/^(?:[^\}]%%[^\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:#[^\n]*)/i,/^(?:journey\b)/i,/^(?:title\s[^#\n;]+)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:section\s[^#:\n;]+)/i,/^(?:[^#:\n;]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[12,13],inclusive:!1},acc_descr:{rules:[10],inclusive:!1},acc_title:{rules:[8],inclusive:!1},INITIAL:{rules:[0,1,2,3,4,5,6,7,9,11,14,15,16,17,18,19],inclusive:!0}}}})();function u(){this.yy={}}return e.n(u,`Parser`),u.prototype=l,l.Parser=u,new u})();o.parser=o;var s=o,c=``,l=[],u=[],d=[],f=e.n(function(){l.length=0,u.length=0,c=``,d.length=0,n.a()},`clear`),p=e.n(function(e){c=e,l.push(e)},`addSection`),m=e.n(function(){return l},`getSections`),h=e.n(function(){let e=y(),t=0;for(;!e&&t<100;)e=y(),t++;return u.push(...d),u},`getTasks`),g=e.n(function(){let e=[];return u.forEach(t=>{t.people&&e.push(...t.people)}),[...new Set(e)].sort()},`updateActors`),_=e.n(function(e,t){let n=t.substr(1).split(`:`),r=0,i=[];n.length===1?(r=Number(n[0]),i=[]):(r=Number(n[0]),i=n[1].split(`,`));let a=i.map(e=>e.trim()),o={section:c,type:c,people:a,task:e,score:r};d.push(o)},`addTask`),v=e.n(function(e){let t={section:c,type:c,description:e,task:e,classes:[]};u.push(t)},`addTaskOrg`),y=e.n(function(){let t=e.n(function(e){return d[e].processed},`compileTask`),n=!0;for(let[e,r]of d.entries())t(e),n&&=r.processed;return n},`compileTasks`),b={getConfig:e.n(()=>n.b().journey,`getConfig`),clear:f,setDiagramTitle:n.q,getDiagramTitle:n.C,setAccTitle:n.U,getAccTitle:n.v,setAccDescription:n.H,getAccDescription:n._,addSection:p,getSections:m,getTasks:h,addTask:_,addTaskOrg:v,getActors:e.n(function(){return g()},`getActors`)},x=e.n(e=>`.label {
    font-family: ${e.fontFamily};
    color: ${e.textColor};
  }
  .mouth {
    stroke: #666;
  }

  line {
    stroke: ${e.textColor}
  }

  .legend {
    fill: ${e.textColor};
    font-family: ${e.fontFamily};
  }

  .label text {
    fill: #333;
  }
  .label {
    color: ${e.textColor}
  }

  .face {
    ${e.faceColor?`fill: ${e.faceColor}`:`fill: #FFF8DC`};
    stroke: #999;
  }

  .node rect,
  .node circle,
  .node ellipse,
  .node polygon,
  .node path {
    fill: ${e.mainBkg};
    stroke: ${e.nodeBorder};
    stroke-width: 1px;
  }

  .node .label {
    text-align: center;
  }
  .node.clickable {
    cursor: pointer;
  }

  .arrowheadPath {
    fill: ${e.arrowheadColor};
  }

  .edgePaths .path {
    stroke: ${e.lineColor};
    stroke-width: 1.5px;
  }

  .flowchart-link {
    stroke: ${e.lineColor};
    fill: none;
  }

  .edgeLabel {
    background-color: ${e.edgeLabelBackground};
    rect {
      opacity: 0.5;
    }
    text-align: center;
  }

  .cluster rect {
  }

  .cluster text {
    fill: ${e.titleColor};
  }

  div.mermaidTooltip {
    position: absolute;
    text-align: center;
    max-width: 200px;
    padding: 2px;
    font-family: ${e.fontFamily};
    font-size: 12px;
    background: ${e.tertiaryColor};
    border: 1px solid ${e.border2};
    border-radius: 2px;
    pointer-events: none;
    z-index: 100;
  }

  .task-type-0, .section-type-0  {
    ${e.fillType0?`fill: ${e.fillType0}`:``};
  }
  .task-type-1, .section-type-1  {
    ${e.fillType0?`fill: ${e.fillType1}`:``};
  }
  .task-type-2, .section-type-2  {
    ${e.fillType0?`fill: ${e.fillType2}`:``};
  }
  .task-type-3, .section-type-3  {
    ${e.fillType0?`fill: ${e.fillType3}`:``};
  }
  .task-type-4, .section-type-4  {
    ${e.fillType0?`fill: ${e.fillType4}`:``};
  }
  .task-type-5, .section-type-5  {
    ${e.fillType0?`fill: ${e.fillType5}`:``};
  }
  .task-type-6, .section-type-6  {
    ${e.fillType0?`fill: ${e.fillType6}`:``};
  }
  .task-type-7, .section-type-7  {
    ${e.fillType0?`fill: ${e.fillType7}`:``};
  }

  .actor-0 {
    ${e.actor0?`fill: ${e.actor0}`:``};
  }
  .actor-1 {
    ${e.actor1?`fill: ${e.actor1}`:``};
  }
  .actor-2 {
    ${e.actor2?`fill: ${e.actor2}`:``};
  }
  .actor-3 {
    ${e.actor3?`fill: ${e.actor3}`:``};
  }
  .actor-4 {
    ${e.actor4?`fill: ${e.actor4}`:``};
  }
  .actor-5 {
    ${e.actor5?`fill: ${e.actor5}`:``};
  }
  ${i.t()}
`,`getStyles`),S=e.n(function(e,t){return a.a(e,t)},`drawRect`),C=e.n(function(t,n){let i=t.append(`circle`).attr(`cx`,n.cx).attr(`cy`,n.cy).attr(`class`,`face`).attr(`r`,15).attr(`stroke-width`,2).attr(`overflow`,`visible`),a=t.append(`g`);a.append(`circle`).attr(`cx`,n.cx-5).attr(`cy`,n.cy-5).attr(`r`,1.5).attr(`stroke-width`,2).attr(`fill`,`#666`).attr(`stroke`,`#666`),a.append(`circle`).attr(`cx`,n.cx+5).attr(`cy`,n.cy-5).attr(`r`,1.5).attr(`stroke-width`,2).attr(`fill`,`#666`).attr(`stroke`,`#666`);function o(e){let t=r.t().startAngle(Math.PI/2).endAngle(Math.PI/2*3).innerRadius(15/2).outerRadius(15/2.2);e.append(`path`).attr(`class`,`mouth`).attr(`d`,t).attr(`transform`,`translate(`+n.cx+`,`+(n.cy+2)+`)`)}e.n(o,`smile`);function s(e){let t=r.t().startAngle(3*Math.PI/2).endAngle(Math.PI/2*5).innerRadius(15/2).outerRadius(15/2.2);e.append(`path`).attr(`class`,`mouth`).attr(`d`,t).attr(`transform`,`translate(`+n.cx+`,`+(n.cy+7)+`)`)}e.n(s,`sad`);function c(e){e.append(`line`).attr(`class`,`mouth`).attr(`stroke`,2).attr(`x1`,n.cx-5).attr(`y1`,n.cy+7).attr(`x2`,n.cx+5).attr(`y2`,n.cy+7).attr(`class`,`mouth`).attr(`stroke-width`,`1px`).attr(`stroke`,`#666`)}return e.n(c,`ambivalent`),n.score>3?o(a):n.score<3?s(a):c(a),i},`drawFace`),w=e.n(function(e,t){let n=e.append(`circle`);return n.attr(`cx`,t.cx),n.attr(`cy`,t.cy),n.attr(`class`,`actor-`+t.pos),n.attr(`fill`,t.fill),n.attr(`stroke`,t.stroke),n.attr(`r`,t.r),n.class!==void 0&&n.attr(`class`,n.class),t.title!==void 0&&n.append(`title`).text(t.title),n},`drawCircle`),T=e.n(function(e,t){return a.o(e,t)},`drawText`),E=e.n(function(t,n){function r(e,t,n,r,i){return e+`,`+t+` `+(e+n)+`,`+t+` `+(e+n)+`,`+(t+r-i)+` `+(e+n-i*1.2)+`,`+(t+r)+` `+e+`,`+(t+r)}e.n(r,`genPoints`);let i=t.append(`polygon`);i.attr(`points`,r(n.x,n.y,50,20,7)),i.attr(`class`,`labelBox`),n.y+=n.labelMargin,n.x+=.5*n.labelMargin,T(t,n)},`drawLabel`),D=e.n(function(e,t,n){let r=e.append(`g`),i=a.s();i.x=t.x,i.y=t.y,i.fill=t.fill,i.width=n.width*t.taskCount+n.diagramMarginX*(t.taskCount-1),i.height=n.height,i.class=`journey-section section-type-`+t.num,i.rx=3,i.ry=3,S(r,i),j(n)(t.text,r,i.x,i.y,i.width,i.height,{class:`journey-section section-type-`+t.num},n,t.colour)},`drawSection`),O=-1,k=e.n(function(e,t,n,r){let i=t.x+n.width/2,o=e.append(`g`);O++,o.append(`line`).attr(`id`,r+`-task`+O).attr(`x1`,i).attr(`y1`,t.y).attr(`x2`,i).attr(`y2`,450).attr(`class`,`task-line`).attr(`stroke-width`,`1px`).attr(`stroke-dasharray`,`4 2`).attr(`stroke`,`#666`),C(o,{cx:i,cy:300+(5-t.score)*30,score:t.score});let s=a.s();s.x=t.x,s.y=t.y,s.fill=t.fill,s.width=n.width,s.height=n.height,s.class=`task task-type-`+t.num,s.rx=3,s.ry=3,S(o,s);let c=t.x+14;t.people.forEach(e=>{let n=t.actors[e].color,r={cx:c,cy:t.y,r:7,fill:n,stroke:`#000`,title:e,pos:t.actors[e].position};w(o,r),c+=10}),j(n)(t.task,o,s.x,s.y,s.width,s.height,{class:`task`},n,t.colour)},`drawTask`),A=e.n(function(e,t){a.n(e,t)},`drawBackgroundRect`),j=(function(){function t(e,t,n,r,a,o,s,c){i(t.append(`text`).attr(`x`,n+a/2).attr(`y`,r+o/2+5).style(`font-color`,c).style(`text-anchor`,`middle`).text(e),s)}e.n(t,`byText`);function n(e,t,n,r,a,o,s,c,l){let{taskFontSize:u,taskFontFamily:d}=c,f=e.split(/<br\s*\/?>/gi);for(let e=0;e<f.length;e++){let c=e*u-u*(f.length-1)/2,p=t.append(`text`).attr(`x`,n+a/2).attr(`y`,r).attr(`fill`,l).style(`text-anchor`,`middle`).style(`font-size`,u).style(`font-family`,d);p.append(`tspan`).attr(`x`,n+a/2).attr(`dy`,c).text(f[e]),p.attr(`y`,r+o/2).attr(`dominant-baseline`,`central`).attr(`alignment-baseline`,`central`),i(p,s)}}e.n(n,`byTspan`);function r(e,t,r,a,o,s,c,l){let u=t.append(`switch`),d=u.append(`foreignObject`).attr(`x`,r).attr(`y`,a).attr(`width`,o).attr(`height`,s).attr(`position`,`fixed`).append(`xhtml:div`).style(`display`,`table`).style(`height`,`100%`).style(`width`,`100%`);d.append(`div`).attr(`class`,`label`).style(`display`,`table-cell`).style(`text-align`,`center`).style(`vertical-align`,`middle`).text(e),n(e,u,r,a,o,s,c,l),i(d,c)}e.n(r,`byFo`);function i(e,t){for(let n in t)n in t&&e.attr(n,t[n])}return e.n(i,`_setTextAttrs`),function(e){return e.textPlacement===`fo`?r:e.textPlacement===`old`?t:n}})(),M={drawRect:S,drawCircle:w,drawSection:D,drawText:T,drawLabel:E,drawTask:k,drawBackgroundRect:A,initGraphics:e.n(function(e,t){O=-1,e.append(`defs`).append(`marker`).attr(`id`,t+`-arrowhead`).attr(`refX`,5).attr(`refY`,2).attr(`markerWidth`,6).attr(`markerHeight`,4).attr(`orient`,`auto`).append(`path`).attr(`d`,`M 0,0 V 4 L6,2 Z`)},`initGraphics`)},N=e.n(function(e){Object.keys(e).forEach(function(t){L[t]=e[t]})},`setConf`),P={},F=0;function I(e){let t=n.b().journey,r=t.maxLabelWidth;F=0;let i=60;Object.keys(P).forEach(n=>{let a=P[n].color,o={cx:20,cy:i,r:7,fill:a,stroke:`#000`,pos:P[n].position};M.drawCircle(e,o);let s=e.append(`text`).attr(`visibility`,`hidden`).text(n),c=s.node().getBoundingClientRect().width;s.remove();let l=[];if(c<=r)l=[n];else{let t=n.split(` `),i=``;s=e.append(`text`).attr(`visibility`,`hidden`),t.forEach(e=>{let t=i?`${i} ${e}`:e;if(s.text(t),s.node().getBoundingClientRect().width>r){if(i&&l.push(i),i=e,s.text(e),s.node().getBoundingClientRect().width>r){let t=``;for(let n of e)t+=n,s.text(t+`-`),s.node().getBoundingClientRect().width>r&&(l.push(t.slice(0,-1)+`-`),t=n);i=t}}else i=t}),i&&l.push(i),s.remove()}l.forEach((n,r)=>{let a={x:40,y:i+7+r*20,fill:`#666`,text:n,textMargin:t.boxTextMargin??5},o=M.drawText(e,a).node().getBoundingClientRect().width;o>F&&o>t.leftMargin-o&&(F=o)}),i+=Math.max(20,l.length*20)})}e.n(I,`drawActorLegend`);var L=n.b().journey,R=0,z=e.n(function(e,r,i,a){let o=n.b(),s=o.journey.titleColor,c=o.journey.titleFontSize,l=o.journey.titleFontFamily,u=o.securityLevel,d;u===`sandbox`&&(d=t.p(`#i`+r));let f=u===`sandbox`?t.p(d.nodes()[0].contentDocument.body):t.p(`body`);B.init();let p=f.select(`#`+r);M.initGraphics(p,r);let m=a.db.getTasks(),h=a.db.getDiagramTitle(),g=a.db.getActors();for(let e in P)delete P[e];let _=0;g.forEach(e=>{P[e]={color:L.actorColours[_%L.actorColours.length],position:_},_++}),I(p),R=L.leftMargin+F,B.insert(0,0,R,Object.keys(P).length*50),U(p,m,0,r);let v=B.getBounds();h&&p.append(`text`).text(h).attr(`x`,R).attr(`font-size`,c).attr(`font-weight`,`bold`).attr(`y`,25).attr(`fill`,s).attr(`font-family`,l);let y=v.stopy-v.starty+2*L.diagramMarginY,b=R+v.stopx+2*L.diagramMarginX;n.c(p,y,b,L.useMaxWidth),p.append(`line`).attr(`x1`,R).attr(`y1`,L.height*4).attr(`x2`,b-R-4).attr(`y2`,L.height*4).attr(`stroke-width`,4).attr(`stroke`,`black`).attr(`marker-end`,`url(#`+r+`-arrowhead)`);let x=h?70:0;p.attr(`viewBox`,`${v.startx} -25 ${b} ${y+x}`),p.attr(`preserveAspectRatio`,`xMinYMin meet`),p.attr(`height`,y+x+25)},`draw`),B={data:{startx:void 0,stopx:void 0,starty:void 0,stopy:void 0},verticalPos:0,sequenceItems:[],init:e.n(function(){this.sequenceItems=[],this.data={startx:void 0,stopx:void 0,starty:void 0,stopy:void 0},this.verticalPos=0},`init`),updateVal:e.n(function(e,t,n,r){e[t]=e[t]===void 0?n:r(n,e[t])},`updateVal`),updateBounds:e.n(function(t,r,i,a){let o=n.b().journey,s=this,c=0;function l(n){return e.n(function(e){c++;let l=s.sequenceItems.length-c+1;s.updateVal(e,`starty`,r-l*o.boxMargin,Math.min),s.updateVal(e,`stopy`,a+l*o.boxMargin,Math.max),s.updateVal(B.data,`startx`,t-l*o.boxMargin,Math.min),s.updateVal(B.data,`stopx`,i+l*o.boxMargin,Math.max),n!==`activation`&&(s.updateVal(e,`startx`,t-l*o.boxMargin,Math.min),s.updateVal(e,`stopx`,i+l*o.boxMargin,Math.max),s.updateVal(B.data,`starty`,r-l*o.boxMargin,Math.min),s.updateVal(B.data,`stopy`,a+l*o.boxMargin,Math.max))},`updateItemBounds`)}e.n(l,`updateFn`),this.sequenceItems.forEach(l())},`updateBounds`),insert:e.n(function(e,t,n,r){let i=Math.min(e,n),a=Math.max(e,n),o=Math.min(t,r),s=Math.max(t,r);this.updateVal(B.data,`startx`,i,Math.min),this.updateVal(B.data,`starty`,o,Math.min),this.updateVal(B.data,`stopx`,a,Math.max),this.updateVal(B.data,`stopy`,s,Math.max),this.updateBounds(i,o,a,s)},`insert`),bumpVerticalPos:e.n(function(e){this.verticalPos+=e,this.data.stopy=this.verticalPos},`bumpVerticalPos`),getVerticalPos:e.n(function(){return this.verticalPos},`getVerticalPos`),getBounds:e.n(function(){return this.data},`getBounds`)},V=L.sectionFills,H=L.sectionColours,U=e.n(function(e,t,r,i){let a=n.b().journey,o=``,s=r+(a.height*2+a.diagramMarginY),c=0,l=`#CCC`,u=`black`,d=0;for(let[n,r]of t.entries()){if(o!==r.section){l=V[c%V.length],d=c%V.length,u=H[c%H.length];let i=0,s=r.section;for(let e=n;e<t.length&&t[e].section==s;e++)i+=1;let f={x:n*a.taskMargin+n*a.width+R,y:50,text:r.section,fill:l,num:d,colour:u,taskCount:i};M.drawSection(e,f,a),o=r.section,c++}let f=r.people.reduce((e,t)=>(P[t]&&(e[t]=P[t]),e),{});r.x=n*a.taskMargin+n*a.width+R,r.y=s,r.width=a.diagramMarginX,r.height=a.diagramMarginY,r.colour=u,r.fill=l,r.num=d,r.actors=f,M.drawTask(e,r,a,i),B.insert(r.x,r.y,r.x+r.width+a.taskMargin,450)}},`drawTasks`),W={setConf:N,draw:z},G={parser:s,db:b,renderer:W,styles:x,init:e.n(e=>{W.setConf(e.journey),b.clear()},`init`)};exports.diagram=G;
};
