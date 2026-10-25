import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const out = path.join(root, '.mcp-deploy');
await mkdir(out, { recursive: true });
await build({ entryPoints: [path.join(root, 'worker/index.ts')], outfile: path.join(out, 'worker.mjs'), bundle: true, format: 'esm', target: 'es2022', external: ['cloudflare:sockets'], minify: false });
const manifest = {}; const files = {};
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2', '.csv': 'text/csv; charset=utf-8' };
async function collect(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) await collect(full);
    else {
      const bytes = await readFile(full); const extension = path.extname(full);
      const hash = createHash('sha256').update(bytes.toString('base64') + extension.slice(1)).digest('hex').slice(0, 32);
      manifest['/' + path.relative(path.join(root, 'dist'), full).replaceAll('\\', '/')] = { hash, size: bytes.length };
      files[hash] = { base64: bytes.toString('base64'), type: types[extension] || 'application/octet-stream' };
    }
  }
}
await collect(path.join(root, 'dist'));
await writeFile(path.join(out, 'bundle.json'), JSON.stringify({ manifest, files, worker: await readFile(path.join(out, 'worker.mjs'), 'utf8') }));
console.log(`MCP artifact prepared: ${Object.keys(manifest).length} public assets. No secrets included.`);
