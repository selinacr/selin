/* Hizmet işçisi.
   Kabuk dosyaları (HTML/JS/CSS) önce ağdan alınır, ağ yoksa önbellekten: yeni sürüm
   kurulduğunda arayüz kendiliğinden tazelenir. Eskiden kabuk "önce önbellek" ile
   sunuluyordu ve uygulama güncellense bile tarayıcı eski arayüzü çalıştırıyordu.
   API yanıtları da önce ağdan, çevrimdışıyken son başarılı yanıttan gelir.

   SURUM değiştiğinde eski önbellekler silinir; arayüz dosyaları değişince artırın. */
const SURUM = "v3";
const KABUK = `yayin-paneli-kabuk-${SURUM}`;
const VERI = `yayin-paneli-veri-${SURUM}`;
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

  // Kabuk: önce ağ, olmazsa önbellek (bayat arayüz sorununu önler).
  olay.respondWith((async () => {
    try {
      const yanit = await fetch(istek);
      if (yanit.ok) {
        const kopya = yanit.clone();
        olay.waitUntil(caches.open(KABUK).then((k) => k.put(istek, kopya)));
      }
      return yanit;
    } catch (hata) {
      const eski = await caches.match(istek, { cacheName: KABUK });
      return eski || Response.error();
    }
  })());
});
