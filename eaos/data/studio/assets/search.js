(self.EAOS_CHUNKS=self.EAOS_CHUNKS||{})["search.js"]=function(require,exports,module){const e=require("./studio.js");function t(t,{replace:n,params:r}={}){let i=e.mi();return e=>i({to:t,params:r,replace:n,search:t=>Object.fromEntries(Object.entries({...t,...e}).filter(([,e])=>e!==void 0&&e!==``))})}Object.defineProperty(exports,"t",{enumerable:!0,get:function(){return t}});
};
