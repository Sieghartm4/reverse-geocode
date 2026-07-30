const CACHE_NAME = "reverse-geocode-tile-cache-v1";
const MAX_CACHE_ENTRIES = 300;

const shouldCacheRequest = (request) => {
  if (request.method !== "GET") return false;
  try {
    const url = new URL(request.url);
    return (
      url.origin === self.location.origin &&
      (url.pathname.startsWith("/tiles/") || url.pathname.startsWith("/fonts/"))
    );
  } catch (err) {
    return false;
  }
};

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME) {
              return caches.delete(cacheName);
            }
            return null;
          }),
        ),
      )
      .then(() => self.clients.claim()),
  );
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
          await cache.put(event.request, response.clone());
          trimCache(cache, MAX_CACHE_ENTRIES);
        }
        return response;
      } catch (err) {
        return cached || Response.error();
      }
    }),
  );
});

async function trimCache(cache, maxEntries) {
  const keys = await cache.keys();
  if (keys.length <= maxEntries) return;

  const deleteCount = keys.length - maxEntries;
  for (let i = 0; i < deleteCount; i += 1) {
    await cache.delete(keys[i]);
  }
}
