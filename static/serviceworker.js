const CACHE_NAME = 'gametech-pwa-cache-v1';
const urlsToCache = [
  '/portal/',
  '/static/manifest.json',
  // You can add core CSS/JS files here to cache for offline use
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        return fetch(event.request).catch(
          // Optional: Return a generic offline page if fetch fails
          () => console.log('Fetch failed; returning offline page instead.')
        );
      }
    )
  );
});
