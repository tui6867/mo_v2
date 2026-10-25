// Loopback-only, read-only bridge to local deployment artifacts. Never reads env,
// private configuration, Auth sessions or credentials. Stops after ten minutes.
import http from 'node:http';
import { readFile } from 'node:fs/promises';
const allowed = new Map([
  ['/bundle', new URL('../.mcp-deploy/bundle.json', import.meta.url)],
  ['/migration', new URL('../../supabase/migrations/20261025052211_cloud_mail_app.sql', import.meta.url)]
]);
const server = http.createServer(async (request, response) => {
  if (request.method !== 'GET' || !allowed.has(request.url)) { response.writeHead(404).end(); return; }
  try { response.writeHead(200, { 'Content-Type': request.url === '/bundle' ? 'application/json' : 'text/plain', 'Cache-Control': 'no-store' }); response.end(await readFile(allowed.get(request.url))); }
  catch { response.writeHead(503).end(); }
});
server.listen(9187, '127.0.0.1', () => console.log('Read-only MCP artifact bridge on loopback port 9187 (10-minute limit).'));
setTimeout(() => server.close(), 600000);
