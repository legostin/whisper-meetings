import { createRequire } from 'node:module';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const dir = dirname(fileURLToPath(import.meta.url));
const deps = process.env.WHISPER_BUILD_DEPS || dir;
const require = createRequire(resolve(deps, 'package.json'));
const { build } = require('esbuild');
const result = await build({ entryPoints: [resolve(dir, 'src/app.js')], bundle: true, minify: true,
  format: 'iife', target: ['chrome120', 'safari17'], write: false, nodePaths: [resolve(deps, 'node_modules')] });
const js = result.outputFiles[0].text.replaceAll('</script', '<\\/script');
const template = readFileSync(resolve(dir, 'src/index.html'), 'utf8');
const css = readFileSync(resolve(dir, 'src/style.css'), 'utf8');
mkdirSync(resolve(dir, 'dist'), {recursive: true});
writeFileSync(resolve(dir, 'dist/widget.html'), template.replace('/* WIDGET_STYLE */', () => css).replace('/* WIDGET_SCRIPT */', () => js));
console.log('Built self-contained widget.html');

const lock = JSON.parse(readFileSync(resolve(dir, 'package-lock.json'), 'utf8'));
const notices = ['# Third-party notices', '', 'The self-contained UI uses the following open-source packages. Build-only esbuild is not redistributed. Python dependencies and Whisper models are downloaded during explicit setup and retain their own licenses.', ''];
for (const [path, pkg] of Object.entries(lock.packages)) {
  if (!path || pkg.dev) continue;
  const license = ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'license', 'license.md', 'LICENSE-MIT', 'COPYING'].map(name => resolve(deps, path, name)).find(existsSync);
  if (!license) throw new Error(`Missing third-party license: ${path}`);
  notices.push(`## ${path.replace('node_modules/', '')} ${pkg.version}`, '', readFileSync(license, 'utf8').trim(), '');
}
writeFileSync(resolve(dir, '../THIRD_PARTY_NOTICES.md'), notices.join('\n'));
