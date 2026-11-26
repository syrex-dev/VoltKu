const CACHE_NAME = 'voltku-pwa-v6';
const PRECACHE_ASSETS = [
  '/offline.html',
  '/manifest.webmanifest?v=6',
  '/pwa-192.png?v=6',
  '/pwa-512.png?v=6',
  '/apple-touch-icon.png?v=6',
  '/favicon.svg?v=6',
  '/brand/voltku-icon.svg?v=6',
  '/brand/voltku-logo-light.svg?v=6',
  '/brand/voltku-logo-dark.svg?v=6',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names.map((name) => {
            if (name !== CACHE_NAME) return caches.delete(name);
            return null;
          })
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Jangan pernah cache endpoint API atau healthz
  if (url.pathname.startsWith('/api/') || url.pathname === '/healthz') {
    return;
  }

  // Navigasi HTML: selalu network no-store, fallback ke offline.html saja bila terputus
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request, { cache: 'no-store' }).catch(async () => {
        const offline = await caches.match('/offline.html');
        return offline || Response.error();
      })
    );
    return;
  }

  // Aset ikon/logo/manifest: selalu ambil versi terbaru dari jaringan
  if (
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.webmanifest')
  ) {
    event.respondWith(
      fetch(request, { cache: 'no-store' })
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return res;
        })
        .catch(() => caches.match(request, { ignoreSearch: true }))
    );
    return;
  }

  // Aset JS/CSS ber-hash Vite (/assets/*) & font: Cache-First karena nama file unik per build
  if (url.pathname.startsWith('/assets/') || url.pathname.endsWith('.woff2')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return res;
        });
      })
    );
  }
});
