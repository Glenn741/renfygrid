// Service worker de RenfyGrid (Track D, D1.3): solo el ARMAZON de la app,
// para que la app del operador abra sin conexion. Nunca toca la API: los
// datos para trabajar sin red los guarda la propia app (foto del catalogo y
// cola de envios en IndexedDB, src/offline/outbox.ts).
//   - Navegacion: red primero; sin red, el index guardado (SPA).
//   - /assets/*: los archivos llevan hash en el nombre -> cache primero.
const SHELL = "renfygrid-shell-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/manifest.json", "/favicon.svg"])));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/plan/")) return;

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            const text = res.clone().text();
            caches.open(SHELL).then(async (c) => {
              await c.put("/", copy);
              // Borra los /assets/ de versiones anteriores (los que el index nuevo ya no nombra).
              const html = await text;
              for (const key of await c.keys()) {
                const path = new URL(key.url).pathname;
                if (path.startsWith("/assets/") && !html.includes(path)) await c.delete(key);
              }
            });
          }
          return res;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }

  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(req).then((hit) =>
        hit || fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        }),
      ),
    );
  }
});
