/* Bağımlılıksız SVG grafik katmanı.
   Üç biçim var: gruplu dikey çubuk, yığılmış çubuk ve çizgi. Hepsinde imleç + ipucu
   bulunur. Renkler CSS değişkenlerinden okunur, böylece koyu/açık tema tek yerden döner.
   Kural: tek eksen — iki farklı ölçekli ölçü asla aynı grafiğe konmaz. */

const AD_ALANI = "http://www.w3.org/2000/svg";

function ogeler(ad, ozellikler = {}, metin = null) {
  const oge = document.createElementNS(AD_ALANI, ad);
  for (const [k, v] of Object.entries(ozellikler)) {
    if (v !== null && v !== undefined) oge.setAttribute(k, String(v));
  }
  if (metin !== null) oge.textContent = metin;
  return oge;
}

function renk(degisken) {
  return getComputedStyle(document.body).getPropertyValue(degisken).trim() || "#2a78d6";
}

function sayiBicim(deger) {
  if (deger === null || deger === undefined || deger === "") return "·";
  const sayi = Number(deger);
  if (!Number.isFinite(sayi)) return String(deger);
  return sayi.toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function olcek(enBuyuk) {
  /* Okunabilir tavan ve 4-5 adımlı ızgara. */
  if (enBuyuk <= 0) return { tavan: 1, adimlar: [0, 1] };
  const buyukluk = Math.pow(10, Math.floor(Math.log10(enBuyuk)));
  const tavan = Math.ceil(enBuyuk / (buyukluk / 2)) * (buyukluk / 2);
  const adet = 4;
  return { tavan, adimlar: Array.from({ length: adet + 1 }, (_, i) => (tavan / adet) * i) };
}

function ipucuKur(sarmal) {
  let ipucu = sarmal.querySelector(".ipucu");
  if (!ipucu) {
    ipucu = document.createElement("div");
    ipucu.className = "ipucu";
    sarmal.appendChild(ipucu);
  }
  return ipucu;
}

function ipucuGoster(ipucu, x, y, baslik, satirlar) {
  ipucu.innerHTML = `<b>${baslik}</b>` + satirlar.map((s) => (
    `<div class="satir"><span class="ad">${s.renk
      ? `<i class="kare" style="background:${s.renk}"></i>` : ""}${s.ad}</span>` +
    `<span class="sayi">${s.deger}</span></div>`
  )).join("");
  ipucu.style.left = `${x}px`;
  ipucu.style.top = `${y}px`;
  ipucu.classList.add("acik");
}

function gostergeCiz(sarmal, seriler) {
  const eski = sarmal.querySelector(".gosterge");
  if (eski) eski.remove();
  if (seriler.length < 2) return;            // tek seride başlık adı taşır
  const kutu = document.createElement("div");
  kutu.className = "gosterge";
  kutu.innerHTML = seriler.map((s) => (
    `<span><i class="kare" style="background:${s.renk}"></i>${s.ad}</span>`
  )).join("");
  sarmal.appendChild(kutu);
}

/* --- gruplu / yığılmış çubuk ------------------------------------------- */
function cubukCiz(sarmal, { etiketler, seriler, yigili = false, birim = "", yuzde = false }) {
  sarmal.querySelectorAll("svg").forEach((s) => s.remove());
  const ipucu = ipucuKur(sarmal);
  const G = { ust: 14, sag: 10, alt: 34, sol: 46 };
  const W = Math.max(sarmal.clientWidth || 640, 320);
  const Y = Math.max(200, Math.min(320, 60 + etiketler.length * 26));
  const ic = { g: W - G.sol - G.sag, y: Y - G.ust - G.alt };

  const toplamlar = etiketler.map((_, i) => (
    yigili ? seriler.reduce((t, s) => t + (Number(s.degerler[i]) || 0), 0)
           : Math.max(...seriler.map((s) => Number(s.degerler[i]) || 0))
  ));
  const { tavan, adimlar } = yuzde ? { tavan: 100, adimlar: [0, 25, 50, 75, 100] }
                                   : olcek(Math.max(...toplamlar, 0));
  const svg = ogeler("svg", { viewBox: `0 0 ${W} ${Y}`, role: "img" });

  for (const adim of adimlar) {
    const y = G.ust + ic.y - (adim / tavan) * ic.y;
    svg.appendChild(ogeler("line", { x1: G.sol, x2: W - G.sag, y1: y, y2: y,
      class: adim === 0 ? "eksen-cizgi" : "izgara" }));
    svg.appendChild(ogeler("text", { x: G.sol - 8, y: y + 4, "text-anchor": "end" },
      sayiBicim(adim) + (yuzde ? "%" : "")));
  }

  const kutuG = ic.g / etiketler.length;
  /* az sayıda kategoride çubuklar fazla incelmesin, çokta birbirine yapışmasın */
  const grupG = Math.min(kutuG * 0.68, yigili ? 120 : 40 * seriler.length);
  const cubukG = yigili ? grupG : grupG / seriler.length;

  etiketler.forEach((etiket, i) => {
    const merkez = G.sol + kutuG * i + kutuG / 2;
    svg.appendChild(ogeler("text", { x: merkez, y: Y - G.alt + 18, "text-anchor": "middle" },
      etiket));

    let yigin = 0;
    seriler.forEach((seri, j) => {
      const deger = Number(seri.degerler[i]) || 0;
      if (deger <= 0) return;
      const yuksek = (deger / tavan) * ic.y;
      const x = yigili ? merkez - grupG / 2 : merkez - grupG / 2 + cubukG * j;
      const y = yigili ? G.ust + ic.y - yigin - yuksek : G.ust + ic.y - yuksek;
      /* veri ucu 4px yuvarlak, taban eksene oturur */
      svg.appendChild(ogeler("rect", {
        x: x + 1, y, width: Math.max(cubukG - 2, 2), height: Math.max(yuksek, 2),
        rx: 4, fill: seri.renk, class: "cubuk",
      }));
      if (yigili) yigin += yuksek;
    });

    /* geniş vuruş alanı: grup başına tek ipucu */
    const hedef = ogeler("rect", { x: G.sol + kutuG * i, y: G.ust, width: kutuG, height: ic.y,
      class: "hedef" });
    hedef.addEventListener("pointerenter", () => {
      ipucuGoster(ipucu, merkez, G.ust + ic.y * 0.45, etiket,
        seriler.map((s) => ({ ad: s.ad, renk: s.renk,
          deger: sayiBicim(s.degerler[i]) + (yuzde ? "%" : birim ? ` ${birim}` : "") })));
    });
    hedef.addEventListener("pointerleave", () => ipucu.classList.remove("acik"));
    svg.appendChild(hedef);
  });

  sarmal.insertBefore(svg, ipucu);
  gostergeCiz(sarmal, seriler);
}

/* --- çizgi -------------------------------------------------------------- */
function cizgiCiz(sarmal, { etiketler, seriler, yuzde = false }) {
  sarmal.querySelectorAll("svg").forEach((s) => s.remove());
  const ipucu = ipucuKur(sarmal);
  const G = { ust: 14, sag: 14, alt: 34, sol: 46 };
  const W = Math.max(sarmal.clientWidth || 640, 320);
  const Y = 240;
  const ic = { g: W - G.sol - G.sag, y: Y - G.ust - G.alt };
  const enBuyuk = Math.max(...seriler.flatMap((s) => s.degerler.map((d) => Number(d) || 0)), 0);
  const { tavan, adimlar } = yuzde ? { tavan: 100, adimlar: [0, 25, 50, 75, 100] }
                                   : olcek(enBuyuk);
  const svg = ogeler("svg", { viewBox: `0 0 ${W} ${Y}`, role: "img" });

  for (const adim of adimlar) {
    const y = G.ust + ic.y - (adim / tavan) * ic.y;
    svg.appendChild(ogeler("line", { x1: G.sol, x2: W - G.sag, y1: y, y2: y,
      class: adim === 0 ? "eksen-cizgi" : "izgara" }));
    svg.appendChild(ogeler("text", { x: G.sol - 8, y: y + 4, "text-anchor": "end" },
      sayiBicim(adim) + (yuzde ? "%" : "")));
  }

  const adim = etiketler.length > 1 ? ic.g / (etiketler.length - 1) : 0;
  const nokta = (i, deger) => ({
    x: G.sol + adim * i,
    y: G.ust + ic.y - ((Number(deger) || 0) / tavan) * ic.y,
  });

  etiketler.forEach((etiket, i) => {
    svg.appendChild(ogeler("text", { x: nokta(i, 0).x, y: Y - G.alt + 18,
      "text-anchor": "middle" }, etiket));
  });

  const imlec = ogeler("line", { y1: G.ust, y2: G.ust + ic.y, class: "imlec", opacity: 0 });
  svg.appendChild(imlec);

  for (const seri of seriler) {
    const yol = seri.degerler.map((d, i) => {
      const p = nokta(i, d);
      return `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
    }).join(" ");
    svg.appendChild(ogeler("path", { d: yol, stroke: seri.renk, class: "cizgi" }));
    seri.degerler.forEach((d, i) => {
      const p = nokta(i, d);
      svg.appendChild(ogeler("circle", { cx: p.x, cy: p.y, r: 4.5, fill: seri.renk,
        class: "nokta" }));
    });
  }

  etiketler.forEach((etiket, i) => {
    const p = nokta(i, 0);
    const hedef = ogeler("rect", { x: p.x - adim / 2 || G.sol, y: G.ust,
      width: adim || ic.g, height: ic.y, class: "hedef" });
    hedef.addEventListener("pointerenter", () => {
      imlec.setAttribute("x1", p.x); imlec.setAttribute("x2", p.x);
      imlec.setAttribute("opacity", 1);
      ipucuGoster(ipucu, p.x, G.ust + ic.y * 0.4, etiket,
        seriler.map((s) => ({ ad: s.ad, renk: s.renk,
          deger: sayiBicim(s.degerler[i]) + (yuzde ? "%" : "") })));
    });
    hedef.addEventListener("pointerleave", () => {
      imlec.setAttribute("opacity", 0);
      ipucu.classList.remove("acik");
    });
    svg.appendChild(hedef);
  });

  sarmal.insertBefore(svg, ipucu);
  gostergeCiz(sarmal, seriler);
}

/* --- yatay çubuk (sıralı listeler: fakülte, dergi) --------------------- */
function yatayCiz(sarmal, { etiketler, degerler, renk: tekRenk, birim = "" }) {
  sarmal.querySelectorAll("svg").forEach((s) => s.remove());
  const ipucu = ipucuKur(sarmal);
  const satirY = 26;
  const G = { ust: 6, sag: 56, alt: 6, sol: 190 };
  const W = Math.max(sarmal.clientWidth || 640, 320);
  const Y = G.ust + G.alt + satirY * etiketler.length;
  const ic = { g: Math.max(W - G.sol - G.sag, 60) };
  const tavan = Math.max(...degerler.map((d) => Number(d) || 0), 1);
  const svg = ogeler("svg", { viewBox: `0 0 ${W} ${Y}`, role: "img" });

  etiketler.forEach((etiket, i) => {
    const y = G.ust + satirY * i;
    const deger = Number(degerler[i]) || 0;
    const genislik = Math.max((deger / tavan) * ic.g, 2);
    svg.appendChild(ogeler("text", { x: G.sol - 10, y: y + satirY / 2 + 4,
      "text-anchor": "end" }, etiket.length > 28 ? etiket.slice(0, 27) + "…" : etiket));
    svg.appendChild(ogeler("rect", { x: G.sol, y: y + 5, width: genislik,
      height: satirY - 11, rx: 4, fill: tekRenk, class: "cubuk" }));
    svg.appendChild(ogeler("text", { x: G.sol + genislik + 8, y: y + satirY / 2 + 4,
      class: "deger" }, sayiBicim(deger) + (birim ? ` ${birim}` : "")));
    const hedef = ogeler("rect", { x: 0, y, width: W, height: satirY, class: "hedef" });
    hedef.addEventListener("pointerenter", () => ipucuGoster(
      ipucu, Math.min(G.sol + genislik, W - 90), y + satirY, etiket,
      [{ ad: birim || "Değer", deger: sayiBicim(deger) }]));
    hedef.addEventListener("pointerleave", () => ipucu.classList.remove("acik"));
    svg.appendChild(hedef);
  });

  sarmal.insertBefore(svg, ipucu);
}

window.Grafik = { cubukCiz, cizgiCiz, yatayCiz, renk, sayiBicim };
