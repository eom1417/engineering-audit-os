const e="/api";function n(r){return fetch(e+"/"+r,{credentials:"same-origin"}).then(o=>o.json())}export{n as load};
