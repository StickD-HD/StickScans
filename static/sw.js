// Service worker : lancement instantané, même sans réseau.
// - La page de l'appli s'affiche tout de suite depuis le cache, et sa version à jour est récupérée en arrière-plan
//   (prise en compte au lancement suivant).
// - Scripts, styles et icônes versionnés (?v=…) et couvertures : jamais redemandés une fois en cache.
// - Les données (/api/…) passent toujours par le réseau ; l'appli garde elle-même la dernière bibliothèque connue.
const PAGE_CACHE = "stickscans-page";
const FILES_CACHE = "stickscans-files";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (req.mode === "navigate" && url.pathname === "/") {
    event.respondWith(pageFromCache(event, req));
  } else if ((url.pathname.startsWith("/static/") && url.searchParams.has("v")) || url.pathname.startsWith("/covers/")) {
    event.respondWith(fileFromCache(req, url));
  }
});

async function pageFromCache(event, req) {
  const cache = await caches.open(PAGE_CACHE);
  const cached = await cache.match("/");
  const network = fetch(req).then(async (res) => {
    if (res.ok && !res.redirected) {
      await cache.put("/", res.clone());
    } else if (res.redirected) {
      await cache.delete("/"); // session expirée : la page de connexion doit s'afficher au prochain lancement
    }
    return res;
  });
  if (cached) {
    event.waitUntil(network.catch(() => {}));
    return cached;
  }
  return network;
}

async function fileFromCache(req, url) {
  const cache = await caches.open(FILES_CACHE);
  const cached = await cache.match(req);
  if (cached) return cached;
  const res = await fetch(req);
  if (res.ok) {
    await cache.put(req, res.clone());
    if (url.searchParams.has("v")) {
      // Ménage : les anciennes versions du même fichier ne servent plus.
      for (const old of await cache.keys()) {
        const o = new URL(old.url);
        if (o.pathname === url.pathname && o.searchParams.get("v") !== url.searchParams.get("v")) await cache.delete(old);
      }
    }
  }
  return res;
}
