const CACHE_NAME = "reverse-geocode-tile-cache-v1";

const shouldCacheRequest = (request) => {
  if (request.method !== "GET") return false;
  try {
    const url = new URL(request.url);
    return (
      url.pathname.startsWith("/tiles/") || url.pathname.startsWith("/fonts/")
    );
  } catch (err) {
    return false;
  }
};

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  if (!shouldCacheRequest(event.request)) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(event.request);
      if (cached) {
        return cached;
      }

      try {
        const response = await fetch(event.request);
        if (response.ok) {
          cache.put(event.request, response.clone());
        }
        return response;
      } catch (err) {
        return cached || Response.error();
      }
    }),
  );
});
