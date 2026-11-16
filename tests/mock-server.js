// Local stand-in for the Google Apps Script web app, running the REAL apps-script/Code.gs.
// node tests/mock-server.js [port]   → page: http://127.0.0.1:PORT/index.html?api=http://127.0.0.1:PORT/api
const http = require('http');
const fs = require('fs');
const path = require('path');
const { createBackend } = require('./gas-mock');

const PORT = +process.argv[2] || 8790;
const ROOT = path.join(__dirname, '..');
let backend = createBackend();
let latency = 700;          // Apps Script is not instant — make the page cope with that
let mode = 'ok';            // ok | down | slow | garbage

const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json' };

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const cors = { 'Access-Control-Allow-Origin': '*' };

  if (url.pathname.startsWith('/__')) {                 // test controls
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      if (url.pathname === '/__reset') { backend = createBackend(); backend.get(); }
      if (url.pathname === '/__mode') mode = url.searchParams.get('m');
      if (url.pathname === '/__latency') latency = +url.searchParams.get('ms');
      if (url.pathname === '/__rows' && req.method === 'POST') { backend.get(); backend.sheet().rows = [backend.sheet().rows[0], ...JSON.parse(body)]; }
      res.writeHead(200, { 'Content-Type': 'application/json', ...cors });
      res.end(JSON.stringify({ rows: backend.sheet() ? backend.sheet().rows : [] }));
    });
    return;
  }

  if (url.pathname === '/api') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      if (mode === 'down') { req.socket.destroy(); return; }
      const wait = mode === 'slow' ? 40000 : latency;
      setTimeout(() => {
        res.writeHead(200, { 'Content-Type': 'application/json', ...cors });
        if (mode === 'garbage') return res.end('<html>Google error page</html>');
        const out = req.method === 'POST' ? backend.post(body) : backend.get();
        res.end(JSON.stringify(out));
      }, wait);
    });
    return;
  }

  const file = path.join(ROOT, decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end('nope'); }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
}).listen(PORT, '127.0.0.1', () => console.log('mock on ' + PORT));
