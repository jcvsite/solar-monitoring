// static/sw.js
// Service worker: offline shell + cached static assets for the dashboard PWA

const CACHE_NAME = 'solar-dashboard-v14';
const SHELL_URLS = [
  '/',
  '/static/css/dashboard.css',
  '/static/js/app.js',
  '/static/js/config.js',
  '/static/js/utils.js',
  '/static/js/ui/dashboard-chrome.js',
  '/static/js/ui/themes.js',
  '/static/js/ui/flow-board.js',
  '/static/js/ui/charts.js',
  '/static/js/ui/weather.js',
  '/static/sw.js',
  '/static/manifest.json',
  '/static/vendor/socket.io.min.js',
  '/static/vendor/chart.umd.min.js',
  '/static/vendor/date-fns.min.js',
  '/static/vendor/chartjs-adapter-date-fns.bundle.min.js',
  '/static/vendor/chartjs-plugin-datalabels.min.js',
  '/static/vendor/chartjs-plugin-zoom.min.js',
  '/static/vendor/leaflet.css',
  '/static/vendor/leaflet.js',
  '/static/vendor/fonts.css',
  '/static/vendor/fonts-fallback.css',
  '/static/icons/icon-192x192.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        SHELL_URLS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn('SW precache skip', url, err);
          })
        )
      )
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Live API / socket traffic — never cache
  if (url.pathname.startsWith('/socket.io')) return;

  // Navigation / HTML shell: network first, cache fallback
  if (req.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() =>
          caches.match(req).then((cached) => cached || caches.match('/'))
        )
    );
    return;
  }

  // Static assets: cache first, then network
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});
