// Service worker minimal : juste requis pour l'installabilité de la PWA.
// Pas de cache offline pour l'instant (la bibliothèque a besoin du réseau
// de toute façon pour être à jour).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
