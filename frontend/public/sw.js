// Muragala service worker: receives files/text shared from the Android share sheet.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method === 'POST' && url.pathname === '/share-target') {
    event.respondWith(
      (async () => {
        const form = await event.request.formData();
        const cache = await caches.open('shared');
        await cache.put('/shared-form', new Response(form));
        return Response.redirect('/?shared=1', 303);
      })()
    );
  }
});
