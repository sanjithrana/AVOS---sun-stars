// Loads optional settings/API keys from ~/.reelmimic/secrets.json (outside the repo, never committed) into process.env,
// so every agent and script the server launches sees them. Real environment variables win.
//   { "YATING_KEY": "...", "PIXABAY_KEY": "...", "FREESOUND_KEY": "...", "FFMPEG_DIR": "...", "CODEX_BIN": "...", "BUILDERS": "5" }
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

// ~/.clone-studio/ is the pre-rename location, still read if the new one doesn't exist.
const legacy = join(homedir(), '.clone-studio', 'secrets.json');
export const SECRETS_PATH = process.env.REELMIMIC_SECRETS || process.env.CLONE_STUDIO_SECRETS
  || (existsSync(join(homedir(), '.reelmimic', 'secrets.json')) || !existsSync(legacy) ? join(homedir(), '.reelmimic', 'secrets.json') : legacy);
try {
  const s = JSON.parse(readFileSync(SECRETS_PATH, 'utf8'));
  for (const [k, v] of Object.entries(s)) if (process.env[k] === undefined && v != null) process.env[k] = String(v);
} catch {}
if (process.env.FFMPEG_DIR) process.env.PATH = `${process.env.FFMPEG_DIR}${process.platform === 'win32' ? ';' : ':'}${process.env.PATH}`;

// Python: macOS/Linux often have only `python3`; Windows may have a Store stub named `python3`. Use the first command
// that really runs Python 3.10+, and export it so every script, agent prompt and child process uses the same one.
if (!process.env.PYTHON) {
  for (const c of process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python']) {
    const r = spawnSync(c, ['-c', 'import sys; print(sys.version_info >= (3, 10))'], { encoding: 'utf8', timeout: 15000 });
    if ((r.stdout || '').trim() === 'True') { process.env.PYTHON = c; break; }
  }
}
