// static/sw.js
// Minimal service worker for PWA installability

self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  // Optional: Skip waiting phase to activate immediately
  // self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
  // Optional: Claim clients immediately
  // event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Cache static assets for better offline experience
  if (event.request.url.includes('/static/')) {
    event.respondWith(
      caches.open('solar-dashboard-v1').then(cache => {
        return cache.match(event.request).then(response => {
          return response || fetch(event.request).then(fetchResponse => {
            cache.put(event.request, fetchResponse.clone());
            return fetchResponse;
          });
        });
      })
    );
  }
});