import { build } from 'esbuild';
import { copyFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = new URL('.', import.meta.url);
const output = new URL('../../../examples/walkthrough/resources/mixed-use/', root);
await mkdir(output, { recursive: true });
await build({
  entryPoints: [fileURLToPath(new URL('viewer.js', root))],
  outfile: fileURLToPath(new URL('viewer.js', output)),
  bundle: true, format: 'esm', minify: true, target: 'es2022',
  legalComments: 'linked',
});
await copyFile(new URL('viewer.html', root), new URL('viewer.html', output));
await copyFile(new URL('SPECKLE-LICENSE', root), new URL('SPECKLE-LICENSE', output));
