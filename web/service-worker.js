const CACHE = 'memoria-v2';
const ASSETS = [
  './',
  './index.html',
  './web/memories.html',
  './web/agenda.html',
  './web/backup.html',
  './web/settings.html',
  './web/js/api.js',
  './web/js/ui.js',
  './web/js/dictation.js',
  './manifest.json',
  './service-worker.js'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;
  e.respondWith(
    caches.match(request).then(cached => cached || fetch(request).catch(() => caches.match('./index.html')))
  );
});