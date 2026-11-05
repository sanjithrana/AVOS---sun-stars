import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './styles.css';
import { startI18n } from './i18n.ts';
createRoot(document.getElementById('root')!).render(<App />);
startI18n();

// A tab left open across a rebuild keeps running the old bundle: check once a minute and offer a refresh.
// (Built pages only — the dev server's index.html has no hashed bundle, so this never fires there.)
const bundle = () => document.querySelector('script[src*="/assets/index-"]')?.getAttribute('src');
if (bundle()) setInterval(async () => {
  if (document.querySelector('.update-pill')) return;
  try {
    const html = await fetch('/', { cache: 'no-store' }).then((r) => r.text());
    const next = html.match(/\/assets\/index-[\w-]+\.js/)?.[0];
    if (!next || bundle()?.endsWith(next)) return;
    const b = document.createElement('button');
    b.className = 'update-pill'; b.textContent = '網站已更新，點這裡重新整理';
    b.onclick = () => location.reload();
    document.body.appendChild(b);
  } catch {}
}, 60000);
