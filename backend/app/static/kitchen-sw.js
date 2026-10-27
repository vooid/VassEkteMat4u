// Kitchen tablet: keeps the last copy of each kitchen page and the stylesheet, and shows it when the network is down
// (US-29). Always asks the server first, so the screen is never older than it has to be. Registered only for kitchen
// staff (_offline.html); logging out clears it (Clear-Site-Data in account.logout).
const CACHE = "ektemat-kitchen-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Not redirects (e.g. to the login page when the session has run out) or errors.
        if (response.ok && response.type === "basic" && !response.redirected) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE).then((cache) => cache.put(request, copy)));
        }
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached || Response.error())),
  );
});
