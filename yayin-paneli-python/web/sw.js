/* Hizmet işçisi: uygulama kabuğu önbellekten, veri her zaman ağdan.
   Ağ yoksa son başarılı API yanıtı gösterilir ki panel çevrimdışı da açılsın. */
const KABUK = "yayin-paneli-kabuk-v2";
const VERI = "yayin-paneli-veri-v2";
const DOSYALAR = ["./", "./index.html", "./stil.css", "./grafik.js", "./uygulama.js",
                  "./simge.svg", "./manifest.webmanifest"];

self.addEventListener("install", (olay) => {
  olay.waitUntil(caches.open(KABUK).then((k) => k.addAll(DOSYALAR)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (olay) => {
  olay.waitUntil(caches.keys().then((adlar) => Promise.all(
    adlar.filter((a) => a !== KABUK && a !== VERI).map((a) => caches.delete(a))
  )).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (olay) => {
  const istek = olay.request;
  if (istek.method !== "GET") return;
  const adres = new URL(istek.url);
  if (adres.origin !== self.location.origin) return;

  if (adres.pathname.startsWith("/api/")) {
    olay.respondWith((async () => {
      try {
        const yanit = await fetch(istek);
        if (yanit.ok) {
          const kopya = yanit.clone();
          olay.waitUntil(caches.open(VERI).then((k) => k.put(istek, kopya)));
        }
        return yanit;
      } catch (hata) {
        const eski = await caches.match(istek, { cacheName: VERI });
        return eski || new Response(
          JSON.stringify({ hata: "Çevrimdışı ve önbellekte bu veri yok." }),
          { status: 503, headers: { "Content-Type": "application/json" } });
      }
    })());
    return;
  }

  olay.respondWith(caches.match(istek).then((eski) => eski || fetch(istek)));
});
