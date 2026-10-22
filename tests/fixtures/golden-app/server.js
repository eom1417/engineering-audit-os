// The golden app: one page drawing its screens from the hash (/#/now, /#/tasks), no client router, as EAOS builds.
const http = require('node:http');
const fs = require('node:fs');
const page = fs.readFileSync(__dirname + '/index.html');
http.createServer((req, res) => {
  if (req.url === '/health') return res.end('ok');
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(page);
}).listen(Number(process.env.PORT || 3000), '0.0.0.0');
