const CACHE_NAME = 'voltku-pwa-v4';
const PRECACHE_ASSETS = [
  '/offline.html',
  '/manifest.webmanifest?v=4',
  '/pwa-192.png?v=4',
  '/pwa-512.png?v=4',
  '/apple-touch-icon.png?v=4',
  '/favicon.svg?v=4',
  '/brand/voltku-icon.svg?v=4',
  '/brand/voltku-logo-light.svg?v=4',
  '/brand/voltku-logo-dark.svg?v=4',
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

  // Jangan pernah cache endpoint API atau healthz (harus selalu live)
  if (url.pathname.startsWith('/api/') || url.pathname === '/healthz') {
    return;
  }

  // Navigasi HTML: Network-first, fallback ke cache lalu offline.html
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          return cached || caches.match('/offline.html');
        })
    );
    return;
  }

  // Aset ikon/logo/manifest: Network-first agar perubahan logo/ikon langsung muncul
  if (
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.webmanifest')
  ) {
    event.respondWith(
      fetch(request)
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

  // Aset JS/CSS hash Vite (/assets/*) & font: Stale-While-Revalidate
  if (
    url.pathname.startsWith('/assets/') ||
    url.pathname.endsWith('.woff2')
  ) {
    event.respondWith(
      caches.match(request, { ignoreSearch: true }).then((cached) => {
        const net = fetch(request)
          .then((res) => {
            if (res && res.status === 200) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            }
            return res;
          })
          .catch(() => null);
        return cached || net;
      })
    );
  }
});
