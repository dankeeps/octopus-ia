// Instala o Chromium que o Spy usa, em spy/browsers dentro da pasta de dados do aplicativo (não mexe no navegador da pessoa).
import { spawn } from 'node:child_process';
import { mkdir, chmod } from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pasta = path.join(process.env.OCTOPUS_DADOS || path.join(raiz, '.local'), 'spy');
await mkdir(pasta, { recursive: true, mode: 0o700 });
await chmod(pasta, 0o700).catch(() => {});      // no Windows não muda nada, e não pode travar a instalação
const require = createRequire(import.meta.url);
const cli = path.join(path.dirname(require.resolve('playwright/package.json')), 'cli.js');
const filho = spawn(process.execPath, [cli, 'install', 'chromium', '--no-shell'], {
  cwd: raiz, stdio: 'inherit',
  env: { ...process.env, PLAYWRIGHT_BROWSERS_PATH: path.join(pasta, 'browsers') },
});
filho.on('error', () => { console.error('Não deu para instalar o navegador do Spy.'); process.exitCode = 1; });
filho.on('exit', (c) => { process.exitCode = c ?? 1; });
