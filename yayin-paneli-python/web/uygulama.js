/* Panel arayüzü: durum, veri çekme, sekme çizimi.
   Sunucu tarafı tabloları hazır verir; burada yalnızca sunum ve grafik var. */

const DURUM = {
  kaynak: "hepsi",
  senaryo: "A",
  bildiri: "1",
  yil: "tumu",
  arama: "",
  sekme: "ozet",
  veri: null,
  durum: null,
  kuyruk: [],
  secilenKisi: null,
};

const SEKMELER = [
  { kod: "ozet", ad: "Özet" },
  { kod: "yillar", ad: "Yıl bazlı" },
  { kod: "quartile", ad: "Çeyreklik" },
  { kod: "karsilastirma", ad: "WoS ↔ Scopus" },
  { kod: "indeks", ad: "İndeks" },
  { kod: "oa", ad: "Açık erişim" },
  { kod: "fakulte", ad: "Fakülte" },
  { kod: "kisiler", ad: "Kişiler" },
  { kod: "kisi", ad: "Kişi analizi" },
  { kod: "dergi", ad: "Dergiler" },
  { kod: "onay", ad: "Onay kuyruğu", rozet: () => (DURUM.durum?.bekleyen_onay || 0) },
  { kod: "veri", ad: "Veri çek" },
  { kod: "senk", ad: "Senkron" },
];

const $ = (secici) => document.querySelector(secici);
const govde = () => $("#govde");

/* --- yardımcılar ------------------------------------------------------- */
function kacis(metin) {
  return String(metin ?? "").replace(/[&<>"']/g, (k) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[k]));
}

function sayiMi(deger) {
  return typeof deger === "number" || (/^-?[\d.,]+%?$/.test(String(deger ?? "")) &&
    String(deger).trim() !== "");
}

function tabloHtml(tablo, { arama = "", azami = 0 } = {}) {
  if (!tablo || !tablo.sutunlar.length) return `<div class="bos">Veri yok.</div>`;
  let satirlar = tablo.satirlar;
  if (arama) {
    const kucuk = arama.toLocaleLowerCase("tr");
    satirlar = satirlar.filter((s) => Object.values(s).some(
      (v) => String(v ?? "").toLocaleLowerCase("tr").includes(kucuk)));
  }
  if (azami) satirlar = satirlar.slice(0, azami);
  const bas = tablo.sutunlar.map((s) => {
    const sayisal = satirlar.some((r) => typeof r[s] === "number");
    return `<th class="${sayisal ? "sayi" : ""}">${kacis(s)}</th>`;
  }).join("");
  const YIL_SUTUNLARI = new Set(["Yıl", "Yil", "Year", "JCR yılı"]);
  const govdeHtml = satirlar.map((satir) => "<tr>" + tablo.sutunlar.map((s) => {
    const deger = satir[s];
    const metin = deger === null || deger === undefined || deger === ""
      ? "·" : YIL_SUTUNLARI.has(s) ? kacis(deger)
      : typeof deger === "number" ? Grafik.sayiBicim(deger) : kacis(deger);
    return `<td class="${sayiMi(deger) ? "sayi" : ""}">${metin}</td>`;
  }).join("") + "</tr>").join("");
  return `<div class="tablo-sarmal"><table><thead><tr>${bas}</tr></thead>` +
         `<tbody>${govdeHtml}</tbody></table></div>` +
         (satirlar.length ? "" : `<div class="bos">Aramaya uyan satır yok.</div>`);
}

function kart(baslik, aciklama, icerik, notu = "") {
  return `<section class="kart"><h2>${kacis(baslik)}</h2>` +
    (aciklama ? `<p class="aciklama">${kacis(aciklama)}</p>` : "") + icerik +
    (notu ? `<p class="notu">${kacis(notu)}</p>` : "") + "</section>";
}

function sutun(tablo, ad) {
  return tablo.satirlar.map((s) => s[ad]);
}

/* --- veri ------------------------------------------------------------- */
async function getir(adres, secenekler) {
  const yanit = await fetch(adres, secenekler);
  if (!yanit.ok) {
    const govdeMetni = await yanit.text().catch(() => "");
    throw new Error(`${yanit.status}: ${govdeMetni.slice(0, 200)}`);
  }
  return yanit.json();
}

async function durumuYenile() {
  try {
    DURUM.durum = await getir("/api/durum");
  } catch (hata) {
    DURUM.durum = null;
  }
  const d = DURUM.durum;
  $("#altbilgi").textContent = d
    ? `${Grafik.sayiBicim(d.kayit)} kayıt · ${d.personel} personel · ${d.adjunct} adjunct · ` +
      `kaynaklar: ${d.kaynaklar.join(", ") || "yok"}`
    : "sunucuya ulaşılamadı";
  $("#altbilgi").title = d?.veritabani ? `Veritabanı: ${d.veritabani}` : "";
  $("#kapat-dugmesi").classList.toggle("gizli", !d?.paket);
  const cip = $("#senk-cipi");
  const son = d?.son_senk;
  cip.className = "durum-cipi " + (son?.durum === "tamam" ? "tamam"
    : son?.durum === "hata" ? "hata" : "bekler");
  cip.querySelector("span").textContent = son
    ? `${son.kaynak} · ${son.durum} · ${(son.bitis || son.baslangic || "").slice(0, 16).replace("T", " ")}`
    : "henüz senkron yok";
  sekmeleriCiz();
}

async function veriYenile() {
  const adres = `/api/analiz?kaynak=${encodeURIComponent(DURUM.kaynak)}` +
    `&senaryo=${DURUM.senaryo}&yil=${encodeURIComponent(DURUM.yil)}` +
    `&bildiri=${DURUM.bildiri === "1"}`;
  try {
    DURUM.veri = await getir(adres);
    yilSeciciyiDoldur();
  } catch (hata) {
    DURUM.veri = null;
    const cevrimdisi = !navigator.onLine || /503/.test(hata.message);
    const bos = /404/.test(hata.message);
    govde().innerHTML = `<div class="bos">${cevrimdisi
      ? "Çevrimdışısınız ve bu görünüm henüz önbelleğe alınmamış. " +
        "Bağlantı gelince panel kendiliğinden güncellenir."
      : bos
      ? "Veritabanı boş. <code>panel.db</code> dosyasını aşağıdaki yola koyup " +
        "servisi yeniden başlatın:<br><br><code>" +
        kacis(DURUM.durum?.veritabani || "veri/panel.db") + "</code><br><br>" +
        "Ya da Streamlit sürümünden (<code>python -m streamlit run app.py</code>) " +
        "WoS/Scopus dosyalarını yükleyin."
      : "Veri alınamadı."}<br><br>${kacis(hata.message)}</div>`;
    return;
  }
  ciz();
}

function yilSeciciyiDoldur() {
  const secici = $("#yil-secici");
  const yillar = DURUM.veri?.yillar || [];
  const mevcut = DURUM.yil;
  secici.innerHTML = `<option value="tumu">Tümü</option>` +
    yillar.map((y) => `<option value="${y}">${y}</option>`).join("");
  secici.value = mevcut;
}

/* --- sekmeler --------------------------------------------------------- */
function sekmeleriCiz() {
  $("#sekmeler").innerHTML = SEKMELER.map((s) => {
    const adet = s.rozet ? s.rozet() : 0;
    return `<button role="tab" data-kod="${s.kod}" aria-selected="${DURUM.sekme === s.kod}">` +
      `${kacis(s.ad)}${adet ? `<span class="rozet">${adet}</span>` : ""}</button>`;
  }).join("");
}

function kutularCiz() {
  const k = DURUM.veri.kutular;
  return `<div class="kutular">
    <div class="kutu"><div class="etiket">Yayın</div><div class="deger">${Grafik.sayiBicim(k.yayin)}</div>
      <div class="alt">${Grafik.sayiBicim(k.tekil)} tekil kayıt · ${k.bildiri} bildiri ${
        k.bildiri_dahil ? "dahil" : "analiz dışı"}</div></div>
    <div class="kutu"><div class="etiket">Akademik personel</div><div class="deger">${Grafik.sayiBicim(k.personel)}</div>
      <div class="alt">listedeki tüm akademik kayıtlar</div></div>
    <div class="kutu"><div class="etiket">Yayın / kişi</div><div class="deger">${Grafik.sayiBicim(k.kisi_basi)}</div>
      <div class="alt">${DURUM.senaryo === "A" ? "adjunct dahil" : "adjunct hariç"}</div></div>
    <div class="kutu"><div class="etiket">Açık erişim</div><div class="deger">${Grafik.sayiBicim(k.oa_orani)}%</div>
      <div class="alt">var / yok ayrımı</div></div>
    <div class="kutu"><div class="etiket">Q1 payı</div><div class="deger">${Grafik.sayiBicim(k.q1_payi)}%</div>
      <div class="alt">sınıflandırılabilen yayınlarda</div></div>
  </div>`;
}

const Q_RENKLERI = { Q1: "--q1", Q2: "--q2", Q3: "--q3", Q4: "--q4" };

function ciz() {
  if (!DURUM.veri) return;
  const v = DURUM.veri;
  const grafikler = [];

  const icerik = {
    ozet: () => kutularCiz() +
      kart("Özet göstergeler", "A senaryosu adjunct yayınlarını içerir, B içermez.",
        tabloHtml(v.ozet)) +
      kart("Yıllara göre yayın", "Her yıl için adjunct dahil ve hariç sayılar.",
        `<div class="grafik" id="g-yil"></div>`),

    yillar: () => kutularCiz() +
      `<div class="ikili">` +
      kart("Yayın sayısı", "Adjunct dahil (A) ve hariç (B).",
        `<div class="grafik" id="g-yil"></div>`) +
      kart("Açık erişim oranı", "A senaryosundaki yayınların yüzdesi.",
        `<div class="grafik" id="g-oa"></div>`) +
      `</div>` +
      kart("Yıl tablosu", "", tabloHtml(v.yil_bazli)),

    quartile: () => kart("Çeyreklik dağılımı",
      "Etkin kaynak seçimine göre; Q1 en koyu, Q4 en açık ton.",
      `<div class="grafik" id="g-q"></div>` + tabloHtml(v.quartile), v.quartile_notu),

    karsilastirma: () => kart("WoS ↔ Scopus çeyreklik karşılaştırması",
      "Aynı yayın kümesinin iki kaynaktaki çeyrekliği. WoS kolonu JCR, Scopus kolonu " +
      "CiteScore/SJR değerlerinden gelir. Bu kolonlar, Veri çek sekmesinden JCR ve " +
      "Scopus Sources listelerini indirene kadar boş kalır.",
      `<div class="grafik" id="g-karsilastirma"></div>` + tabloHtml(v.quartile_karsilastirma)),

    indeks: () => kart("İndeks dağılımı",
      "CPCI satırları konferans bildirisi indeksleridir; bildiriler analiz dışıdır.",
      tabloHtml(v.indeks)),

    oa: () => kart("Açık erişim", "Yalnızca var/yok olarak sayılır; gold, green ayrımı yok.",
      `<div class="grafik" id="g-oa"></div>` + tabloHtml(v.acik_erisim)),

    fakulte: () => kart("Fakülte / birim", "Kişi başına yayın sayısına göre sıralı.",
      `<div class="grafik" id="g-fakulte"></div>` + tabloHtml(v.fakulte, { arama: DURUM.arama }),
      v.fakulte_notu),

    kisiler: () => kart("Kişi bazlı yayınlar",
      "Bir yayın, yayındaki her kurum yazarı için ayrı sayılır.",
      tabloHtml(v.kisi, { arama: DURUM.arama }), v.kisi_notu),

    kisi: () => kisiEkrani(),

    dergi: () => kart("Dergiler", "En çok yayın yapılan ilk 200 dergi.",
      tabloHtml(v.dergi, { arama: DURUM.arama })),

    onay: () => onayEkrani(),
    veri: () => veriCekEkrani(),
    senk: () => senkEkrani(),
  };

  govde().innerHTML = (icerik[DURUM.sekme] || icerik.ozet)();

  /* grafikler DOM'a girdikten sonra çizilir */
  const yil = v.yil_bazli;
  if ($("#g-yil") && yil.satirlar.length) {
    Grafik.cubukCiz($("#g-yil"), {
      etiketler: sutun(yil, "Yıl").map(String),
      seriler: [
        { ad: "A: adjunct dahil", renk: Grafik.renk("--wos"), degerler: sutun(yil, "A") },
        { ad: "B: adjunct hariç", renk: Grafik.renk("--scopus"), degerler: sutun(yil, "B") },
      ],
      birim: "yayın",
    });
  }
  if ($("#g-oa") && yil.satirlar.length) {
    Grafik.cizgiCiz($("#g-oa"), {
      etiketler: sutun(yil, "Yıl").map(String),
      seriler: [{ ad: "Açık erişim oranı", renk: Grafik.renk("--q2"),
        degerler: sutun(yil, "OA % (A)") }],
      yuzde: true,
    });
  }
  if ($("#g-q") && v.quartile.satirlar.length) {
    const satir = (q) => v.quartile.satirlar.find((s) => s["Çeyreklik"] === q) || {};
    Grafik.cubukCiz($("#g-q"), {
      etiketler: ["A: adjunct dahil", "B: adjunct hariç"],
      yigili: true,
      seriler: ["Q1", "Q2", "Q3", "Q4", "Sınıflandırılamayan"].map((q) => ({
        ad: q, renk: Grafik.renk(Q_RENKLERI[q] || "--q-yok"),
        degerler: [satir(q)["A: dahil"] || 0, satir(q)["B: hariç"] || 0],
      })),
      birim: "yayın",
    });
  }
  if ($("#g-karsilastirma") && v.quartile_karsilastirma.satirlar.length) {
    const k = v.quartile_karsilastirma;
    Grafik.cubukCiz($("#g-karsilastirma"), {
      etiketler: sutun(k, "Çeyreklik"),
      seriler: [
        { ad: "WoS (JCR)", renk: Grafik.renk("--wos"), degerler: sutun(k, "WoS (JCR)") },
        { ad: "Scopus (CiteScore/SJR)", renk: Grafik.renk("--scopus"),
          degerler: sutun(k, "Scopus (CiteScore/SJR)") },
      ],
      birim: "yayın",
    });
  }
  if ($("#g-fakulte") && v.fakulte.satirlar.length) {
    Grafik.yatayCiz($("#g-fakulte"), {
      etiketler: sutun(v.fakulte, "Fakülte / birim"),
      degerler: sutun(v.fakulte, "Yayın/kişi"),
      renk: Grafik.renk("--wos"), birim: "yayın/kişi",
    });
  }
  if (DURUM.sekme === "kisi") kisiGrafikleri();
  return grafikler;
}

/* --- kişi analizi ----------------------------------------------------- */
function kisiEkrani() {
  const kisi = DURUM.veri.kisi;
  const kucuk = DURUM.arama.toLocaleLowerCase("tr");
  const adaylar = kisi.satirlar
    .filter((s) => !kucuk || String(s["Kişi"]).toLocaleLowerCase("tr").includes(kucuk))
    .slice(0, 24);
  const secilen = DURUM.secilenKisi
    && kisi.satirlar.find((s) => s["Kişi"] === DURUM.secilenKisi);

  const liste = `<section class="kart"><h2>Kişi seç</h2>
    <p class="aciklama">Üstteki arama kutusu bu listeyi daraltır. ${kisi.satirlar.length} kişi var.</p>
    <div class="kisi-liste">${adaylar.map((s) => (
      `<button class="kisi-dugme" data-kisi="${kacis(s["Kişi"])}">
        <b>${kacis(s["Kişi"])}</b>
        <span>${kacis(s["Unvan"])} · ${kacis(s["Fakülte"])} · ${s["Yayın"]} yayın</span>
      </button>`)).join("")}</div></section>`;

  if (!secilen) return liste;

  const q = DURUM.veri.kisi_q.satirlar.find((s) => s["Kişi"] === secilen["Kişi"]) || {};
  const hWos = secilen["h (WoS, profil)"] ?? secilen["h (WoS, veri seti)"];
  const hScopus = secilen["h (Scopus, profil)"] ?? secilen["h (Scopus, veri seti)"];
  const hKaynagi = secilen["h (WoS, profil)"] != null ? "yazar profilinden"
                                                      : "panelde yüklü yayınlardan";
  const kutular = `<div class="kutular">
    <div class="kutu"><div class="etiket">Yayın</div><div class="deger">${secilen["Yayın"]}</div>
      <div class="alt">${secilen["Durum"]}</div></div>
    <div class="kutu"><div class="etiket">h-indeksi (WoS)</div>
      <div class="deger">${hWos ?? "·"}</div><div class="alt">${hKaynagi}</div></div>
    <div class="kutu"><div class="etiket">h-indeksi (Scopus)</div>
      <div class="deger">${hScopus ?? "·"}</div><div class="alt">${hKaynagi}</div></div>
    <div class="kutu"><div class="etiket">Açık erişim</div>
      <div class="deger">${secilen["Açık erişim"]}</div><div class="alt">yayın sayısı</div></div>
    <div class="kutu"><div class="etiket">Atıf (WoS / Scopus)</div>
      <div class="deger">${secilen["Atıf (WoS, profil)"] ?? secilen["Atıf (WoS, veri seti)"] ?? "·"} / ${
        secilen["Atıf (Scopus, profil)"] ?? secilen["Atıf (Scopus, veri seti)"] ?? "·"}</div>
      <div class="alt">${hKaynagi}</div></div>
  </div>`;

  const Q_KAYNAKLARI = ["WoS", "Scopus"];
  const qTablo = {
    sutunlar: ["Kaynak", "Q1", "Q2", "Q3", "Q4"],
    satirlar: Q_KAYNAKLARI.map((kaynak) => ({
      Kaynak: kaynak,
      Q1: q[`${kaynak} Q1`] || 0, Q2: q[`${kaynak} Q2`] || 0,
      Q3: q[`${kaynak} Q3`] || 0, Q4: q[`${kaynak} Q4`] || 0,
    })),
  };

  const q_ad = encodeURIComponent(secilen["Kişi"]);
  const profil = `<p class="notu">Kariyer boyu h-indeksi için yazar profilini aç:
    <a href="https://www.webofscience.com/wos/author/search?authorName=${q_ad}"
       target="_blank" rel="noopener">WoS</a> ·
    <a href="https://www.scopus.com/results/authorNamesList.uri?st1=${q_ad}"
       target="_blank" rel="noopener">Scopus</a></p>`;

  return `<h2 style="margin:0 0 10px;font-size:18px">${kacis(secilen["Kişi"])}</h2>` + kutular + profil +
    `<div class="ikili">` +
    kart("Yıllara göre yayın", "", `<div class="grafik" id="g-kisi-yil"></div>`) +
    kart("Çeyreklik dağılımı", "WoS ve Scopus ayrı sayılır.",
      `<div class="grafik" id="g-kisi-q"></div>` + tabloHtml(qTablo)) +
    `</div>` + liste;
}

function kisiGrafikleri() {
  const satir = DURUM.veri.kisi.satirlar.find((s) => s["Kişi"] === DURUM.secilenKisi);
  if (satir && $("#g-kisi-yil")) {
    Grafik.cubukCiz($("#g-kisi-yil"), {
      etiketler: DURUM.veri.yillar.map(String),
      seriler: [{ ad: "Yayın", renk: Grafik.renk("--wos"),
        degerler: DURUM.veri.yillar.map((y) => satir[String(y)] || 0) }],
      birim: "yayın",
    });
  }
  const q = DURUM.veri.kisi_q.satirlar.find((s) => s["Kişi"] === DURUM.secilenKisi);
  if (q && $("#g-kisi-q")) {
    Grafik.cubukCiz($("#g-kisi-q"), {
      etiketler: ["Q1", "Q2", "Q3", "Q4"],
      seriler: [
        { ad: "WoS", renk: Grafik.renk("--wos"),
          degerler: ["Q1", "Q2", "Q3", "Q4"].map((x) => q[`WoS ${x}`] || 0) },
        { ad: "Scopus", renk: Grafik.renk("--scopus"),
          degerler: ["Q1", "Q2", "Q3", "Q4"].map((x) => q[`Scopus ${x}`] || 0) },
      ],
      birim: "yayın",
    });
  }
}

/* --- onay kuyruğu ----------------------------------------------------- */
function onayEkrani() {
  if (!DURUM.kuyruk.length) {
    return kart("Onay kuyruğu",
      "Eşleşmesi kesin olmayan isimler burada birikir; kesin eşleşmeler otomatik bağlanır.",
      `<div class="bos">Onay bekleyen isim yok.</div>` +
      `<button class="dugme vurgulu" id="kuyruk-tazele">Kuyruğu yeniden hesapla</button>`);
  }
  const satirlar = DURUM.kuyruk.map((k) => `
    <div class="onay-satir">
      <div><div class="ham">${kacis(k.ham)}</div>
        <div class="meta">${kacis(k.kaynak || "kaynak yok")} · benzerlik ${k.benzerlik}</div></div>
      <select data-ham="${kacis(k.ham)}" class="aday-secimi">
        ${k.adaylar.map((a, i) => `<option value="${i}">${kacis(a.hedef)} — ${kacis(a.unvan)}, ${kacis(a.fakulte)} (${a.puan})</option>`).join("")}
      </select>
      <button class="dugme vurgulu" data-onay="${kacis(k.ham)}">Onayla</button>
      <button class="dugme" data-ret="${kacis(k.ham)}">Listede yok</button>
    </div>`).join("");
  return kart("Onay kuyruğu",
    `${DURUM.kuyruk.length} isim bekliyor. Aday seçip onaylayın ya da «listede yok» olarak ` +
    "işaretleyin; karar takma ad tablosuna yazılır ve bir daha sorulmaz.",
    satirlar + `<p class="notu"></p>` +
    `<button class="dugme" id="kuyruk-tazele">Kuyruğu yeniden hesapla</button>`);
}

async function kuyrukYenile() {
  try {
    DURUM.kuyruk = (await getir("/api/onay")).kayitlar;
  } catch (hata) {
    DURUM.kuyruk = [];
  }
}

/* --- veri çekme ------------------------------------------------------- */
function veriCekEkrani() {
  const d = DURUM.durum;
  const iz = d?.izleyici;
  const bag = DURUM.baglantilar;
  if (!bag) {
    getir("/api/baglantilar").then((v) => { DURUM.baglantilar = v; ciz(); }).catch(() => {});
    return `<div class="bos">Bağlantılar hazırlanıyor…</div>`;
  }

  const satirlar = bag.yillar.map((y) => `
    <tr>
      <td>${y.yil}</td>
      <td><a class="dugme" href="${y.wos}" target="_blank" rel="noopener">WoS'ta aç</a></td>
      <td><a class="dugme" href="${y.scopus}" target="_blank" rel="noopener">Scopus'ta aç</a></td>
    </tr>`).join("");

  const gecmis = (iz?.gecmis || []).map((g) => `
    <tr><td>${kacis(g.dosya)}</td><td>${kacis(g.tur || "—")}</td>
        <td class="sayi">${g.adet ?? "·"}</td>
        <td>${kacis(g.durum)}${g.mesaj ? " — " + kacis(g.mesaj) : ""}</td></tr>`).join("");

  const metrikler = (bag.metrikler || []).map((k) => `
    <tr>
      <td><a class="dugme" href="${k.adres}" target="_blank" rel="noopener">${kacis(k.ad)}</a></td>
      <td>${kacis(k.nasil)}</td>
    </tr>`).join("");

  return kart("Veriyi kendi oturumunla çek",
    "Kütüphane girişin kendi tarayıcında açık. Aşağıdaki düğme doğru aramayı senin " +
    "tarayıcında açar; sen yalnızca sayfadaki Export düğmesine basarsın. İnen dosya " +
    "İndirilenler klasörüne düştüğü anda panel onu tanıyıp içeri alır — dosya seçmen, " +
    "yüklemen gerekmez.",
    `<div class="tablo-sarmal"><table>
       <thead><tr><th>Yıl</th><th>Web of Science</th><th>Scopus</th></tr></thead>
       <tbody>${satirlar}</tbody></table></div>`,
    "WoS'ta Export → Excel → Record Content: Full Record seçin ve belge türü filtresi " +
    "koymayın. Scopus'ta Export → CSV seçtikten sonra «Bibliographical information» " +
    "kutusunu da işaretleyin; aksi hâlde ISSN ve adres sütunları gelmez.") +

  kart("Çeyreklik ve h-indeksi listeleri",
    "Yayın dışa aktarımlarında çeyreklik ve h-indeksi bulunmaz; bunlar ayrı listelerden " +
    "gelir. Aşağıdaki sayfaları kendi oturumunla aç, listeyi indir — panel dosyayı yine " +
    "kendiliğinden tanır. Bu listeler yılda bir güncellenir, her seferinde indirmen gerekmez.",
    `<div class="tablo-sarmal"><table>
       <thead><tr><th>Kaynak</th><th>Nasıl indirilir</th></tr></thead>
       <tbody>${metrikler}</tbody></table></div>`,
    "Bu listeler gelmeden önce bile kişi bazlı tabloda «h (…, veri seti)» kolonları " +
    "doludur: panelde yüklü yayınların atıf sayılarından hesaplanır. Profil h-indeksi " +
    "(kariyer boyu) yalnızca yukarıdaki yazar listeleri yüklenince görünür.") +

  kart("İzlenen klasör",
    iz?.calisiyor ? "Panel bu klasörü izliyor; yeni inen dosya kendiliğinden alınır."
                  : "İzleme kapalı. Açarsanız inen dosyalar kendiliğinden alınır.",
    `<div class="filtreler" style="padding:0">
      <input type="text" id="izleme-klasoru" value="${kacis(iz?.klasor || "")}" style="min-width:320px">
      <button class="dugme" id="klasor-kaydet">Klasörü değiştir</button>
      <button class="dugme vurgulu" id="izleme-degistir">${
        iz?.calisiyor ? "İzlemeyi durdur" : "İzlemeyi başlat"}</button>
      <button class="dugme" id="simdi-tara">Şimdi tara</button>
    </div>` +
    (iz?.var ? "" : `<p class="notu">Bu klasör bulunamadı; doğru yolu yazıp kaydedin.</p>`)) +

  kart("Son alınan dosyalar", "",
    gecmis ? `<div class="tablo-sarmal"><table>
        <thead><tr><th>Dosya</th><th>Tür</th><th class="sayi">Kayıt</th><th>Durum</th></tr></thead>
        <tbody>${gecmis}</tbody></table></div>`
      : `<div class="bos">Henüz dosya alınmadı.</div>`);
}

/* --- senkron ---------------------------------------------------------- */
function senkEkrani() {
  const d = DURUM.durum;
  if (!d) return `<div class="bos">Sunucu durumu alınamadı.</div>`;
  const a = d.ayarlar;
  const gunluk = {
    sutunlar: ["Kaynak", "Başlangıç", "Bitiş", "Durum", "Yeni kayıt", "Mesaj"],
    satirlar: d.gunluk.map((s) => ({
      Kaynak: s.kaynak, Başlangıç: (s.baslangic || "").slice(0, 16).replace("T", " "),
      Bitiş: (s.bitis || "").slice(0, 16).replace("T", " "), Durum: s.durum,
      "Yeni kayıt": s.yeni_kayit, Mesaj: s.mesaj || "",
    })),
  };
  return kart("Toplama ayarları",
    "«api» yolu resmi WoS ve Scopus API anahtarlarını kullanır ve sağlayıcı şartlarına " +
    "uygun yoldur. «tarayici» yolu kendi makinenizdeki açık oturumu kullanır.",
    `<div class="filtreler" style="padding:0">
      <div class="segment" id="yol-secici" role="group" aria-label="Toplama yolu">
        <button data-deger="api" aria-pressed="${a.toplama_yolu === "api"}">API</button>
        <button data-deger="tarayici" aria-pressed="${a.toplama_yolu === "tarayici"}">Tarayıcı</button>
      </div>
      <label>Kurum sorgusu <input type="text" id="kurum" value="${kacis(a.kurum_sorgusu)}"></label>
      <label>Scopus AF-ID <input type="text" id="af-id" value="${kacis(a.scopus_kurum_kimligi)}"></label>
      <label>İlk yıl <input type="number" id="ilk-yil" value="${a.ilk_yil}" min="1990" max="2100"></label>
      <button class="dugme vurgulu" id="ayar-kaydet">Kaydet</button>
      <button class="dugme" id="zamanlayici-degistir">${d.zamanlayici ? "Saatlik toplamayı durdur" : "Saatlik toplamayı başlat"}</button>
    </div>`) +
    kart("Veri durumu", "",
      tabloHtml({
        sutunlar: ["Gösterge", "Değer"],
        satirlar: [
          { Gösterge: "Veritabanı dosyası", Değer: d.veritabani },
          { Gösterge: "Kayıt", Değer: d.kayit },
          { Gösterge: "Personel satırı", Değer: d.personel },
          { Gösterge: "Adjunct adı", Değer: d.adjunct },
          { Gösterge: "Dergi metrik satırı", Değer: d.dergi_metrik },
          ...Object.entries(d.metrik_kaynaklari || {}).map(([k, v]) => (
            { Gösterge: `  — ${k} çeyreklikleri`, Değer: v })),
          { Gösterge: "Yazar metrik profili", Değer: d.kisi_metrik },
          ...Object.entries(d.yazar_kaynaklari || {}).map(([k, v]) => (
            { Gösterge: `  — ${k} h-indeksi`, Değer: v })),
          { Gösterge: "Onay bekleyen isim", Değer: d.bekleyen_onay },
        ],
      })) +
    kart("Senkron günlüğü", "En son 10 tur.", tabloHtml(gunluk));
}

/* --- olaylar ---------------------------------------------------------- */
function segmentBagla(secici, alan, sonra) {
  $(secici)?.addEventListener("click", (olay) => {
    const dugme = olay.target.closest("button[data-deger]");
    if (!dugme) return;
    DURUM[alan] = dugme.dataset.deger;
    $(secici).querySelectorAll("button").forEach((b) => (
      b.setAttribute("aria-pressed", String(b === dugme))));
    sonra?.();
  });
}

function olaylariBagla() {
  segmentBagla("#kaynak-secici", "kaynak", veriYenile);
  segmentBagla("#senaryo-secici", "senaryo", veriYenile);
  segmentBagla("#bildiri-secici", "bildiri", veriYenile);

  $("#yil-secici").addEventListener("change", (olay) => {
    DURUM.yil = olay.target.value;
    veriYenile();
  });

  let zamanlayici;
  $("#arama").addEventListener("input", (olay) => {
    DURUM.arama = olay.target.value.trim();
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(ciz, 180);
  });

  $("#sekmeler").addEventListener("click", async (olay) => {
    const dugme = olay.target.closest("button[data-kod]");
    if (!dugme) return;
    DURUM.sekme = dugme.dataset.kod;
    sekmeleriCiz();
    if (DURUM.sekme === "onay") await kuyrukYenile();
    if (DURUM.sekme === "senk") await durumuYenile();
    ciz();
  });

  $("#tema-dugmesi").addEventListener("click", () => {
    const koyu = document.documentElement.dataset.theme === "dark"
      || (!document.documentElement.dataset.theme
          && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = koyu ? "light" : "dark";
    localStorage.setItem("tema", document.documentElement.dataset.theme);
    ciz();
  });

  $("#kapat-dugmesi").addEventListener("click", async () => {
    if (!confirm("Panel kapatılsın mı? Bu pencereyi de kapatabilirsiniz.")) return;
    await fetch("/api/kapat", { method: "POST" }).catch(() => {});
    document.body.innerHTML =
      '<div style="padding:60px;text-align:center;font:15px system-ui">' +
      "Panel kapatıldı. Bu sekmeyi kapatabilirsiniz.</div>";
  });

  $("#senk-dugmesi").addEventListener("click", async (olay) => {
    olay.target.disabled = true;
    olay.target.textContent = "Senkronize ediliyor…";
    try {
      await getir("/api/senk", { method: "POST" });
    } catch (hata) {
      /* durum çipi hatayı gösterir */
    }
    olay.target.disabled = false;
    olay.target.textContent = "Şimdi senkronize et";
    await durumuYenile();
    await veriYenile();
  });

  govde().addEventListener("click", async (olay) => {
    const kisi = olay.target.closest("button[data-kisi]");
    if (kisi) {
      DURUM.secilenKisi = kisi.dataset.kisi;
      DURUM.sekme = "kisi";
      sekmeleriCiz();
      ciz();
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    const onay = olay.target.closest("button[data-onay]");
    if (onay) {
      const ham = onay.dataset.onay;
      const secim = govde().querySelector(`select[data-ham="${CSS.escape(ham)}"]`);
      const kayit = DURUM.kuyruk.find((k) => k.ham === ham);
      const aday = kayit?.adaylar[Number(secim?.value || 0)];
      if (!aday) return;
      await getir("/api/onay", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ham, durum: "onayli", hedef: aday.hedef, tur: aday.tur }),
      });
      await kuyrukYenile(); await durumuYenile(); await veriYenile(); ciz();
      return;
    }

    const ret = olay.target.closest("button[data-ret]");
    if (ret) {
      await getir("/api/onay", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ham: ret.dataset.ret, durum: "reddedildi" }),
      });
      await kuyrukYenile(); await durumuYenile(); ciz();
      return;
    }

    if (olay.target.id === "kuyruk-tazele") {
      olay.target.disabled = true;
      await getir("/api/onay/tazele", { method: "POST" });
      await kuyrukYenile(); await durumuYenile(); ciz();
      return;
    }

    if (olay.target.id === "izleme-degistir") {
      const eylem = DURUM.durum?.izleyici?.calisiyor ? "dur" : "basla";
      await getir(`/api/izleyici/${eylem}`, { method: "POST" });
      await durumuYenile(); ciz();
      return;
    }

    if (olay.target.id === "simdi-tara") {
      olay.target.disabled = true;
      const sonuc = await getir("/api/izleyici/tara", { method: "POST" }).catch(() => null);
      await durumuYenile();
      if (sonuc?.alinan?.length) await veriYenile(); else ciz();
      return;
    }

    if (olay.target.id === "klasor-kaydet") {
      await getir("/api/izleyici/klasor", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ klasor: $("#izleme-klasoru").value }),
      }).catch((hata) => alert(hata.message));
      await durumuYenile(); ciz();
      return;
    }

    if (olay.target.id === "ayar-kaydet") {
      const yol = govde().querySelector('#yol-secici button[aria-pressed="true"]')?.dataset.deger;
      await getir("/api/ayarlar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          toplama_yolu: yol, kurum_sorgusu: $("#kurum").value, wos_kurum: $("#kurum").value,
          scopus_kurum_kimligi: $("#af-id").value, ilk_yil: Number($("#ilk-yil").value),
        }),
      });
      await durumuYenile(); ciz();
      return;
    }

    if (olay.target.id === "zamanlayici-degistir") {
      const eylem = DURUM.durum?.zamanlayici ? "dur" : "basla";
      await getir(`/api/zamanlayici/${eylem}`, { method: "POST" });
      await durumuYenile(); ciz();
      return;
    }

    const yolDugmesi = olay.target.closest("#yol-secici button[data-deger]");
    if (yolDugmesi) {
      govde().querySelectorAll("#yol-secici button").forEach((b) => (
        b.setAttribute("aria-pressed", String(b === yolDugmesi))));
    }
  });

  addEventListener("resize", () => {
    clearTimeout(zamanlayici);
    zamanlayici = setTimeout(ciz, 200);
  });
}

/* --- başlangıç -------------------------------------------------------- */
async function basla() {
  const tema = localStorage.getItem("tema");
  if (tema) document.documentElement.dataset.theme = tema;
  sekmeleriCiz();
  olaylariBagla();
  await durumuYenile();
  await kuyrukYenile();
  await veriYenile();
  // İzleyici yeni dosya aldıysa tabloları da tazele
  let sonGecmis = 0;
  setInterval(async () => {
    await durumuYenile();
    const adet = DURUM.durum?.izleyici?.gecmis?.length || 0;
    if (adet !== sonGecmis) {
      sonGecmis = adet;
      await veriYenile();
    }
  }, 10 * 1000);
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
}

basla();
