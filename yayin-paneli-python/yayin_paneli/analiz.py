"""Kurum yayın analizi: kaynak birleştirme, kişi eşleştirme, çeyreklik ve tablolar."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .ayristirma import INDEKS_ACIKLAMALARI, INDEKS_ADLARI
from .metin import ad_eslesiyor_mu, sade, yazar_adi_coz

Q_SIRASI = ["Q1", "Q2", "Q3", "Q4", "Sınıflandırılamayan", "Bildiri"]

UNVAN_KALIPLARI = [
    (re.compile(r"profes", re.I), "Profesör"),
    (re.compile(r"doç", re.I), "Doçent"),
    (re.compile(r"dr\.?\s*ö[gğ]r|doktor ö[gğ]retim", re.I), "Doktor Öğretim Üyesi"),
    (re.compile(r"ö[gğ]r\.?\s*gör\.?\s*dr", re.I), "Öğretim Görevlisi (Dr.)"),
    (re.compile(r"ö[gğ]r\.?\s*gör|ö[gğ]retim görevlisi", re.I), "Öğretim Görevlisi"),
    (re.compile(r"ar[şs]\.?\s*gör|ara[şs]t[ıi]rma görevlisi", re.I), "Araştırma Görevlisi"),
    (re.compile(r"okutman", re.I), "Okutman"),
    (re.compile(r"uzman", re.I), "Uzman"),
]


def unvan_sadele(ham: str) -> str:
    metin = str(ham or "").strip()
    for kalip, ad in UNVAN_KALIPLARI:
        if kalip.search(metin):
            return ad
    return metin or "Belirtilmemiş"


def bildiri_mi(kayit: dict) -> bool:
    """Bildiriler (proceedings paper / conference paper) analiz dışıdır."""
    return bool(re.search(r"proceedings\s*paper|conference paper|bildiri",
                          f"{kayit.get('belge_turu_ham', '')} {kayit.get('belge_turu', '')}", re.I))


@dataclass
class Kisi:
    ad: str
    soyad: str
    unvan: str
    fakulte: str
    birim: str = ""
    tip: str = ""
    aktif: bool = True
    akademik: bool = True
    anahtar: object = None

    @property
    def tam_ad(self) -> str:
        return f"{self.ad} {self.soyad}"


@dataclass
class Adjunct:
    etiket: str
    kaynak: str = "hepsi"
    takmalar: list[str] = field(default_factory=list)
    anahtar: object = None


def personel_dizini(personel: list[dict]) -> list[Kisi]:
    kisiler = []
    for kayit in personel:
        kisiler.append(Kisi(
            ad=kayit["ad"], soyad=kayit["soyad"], unvan=unvan_sadele(kayit.get("unvan")),
            fakulte=kayit.get("fakulte") or "Belirtilmemiş", birim=kayit.get("birim", ""),
            tip=kayit.get("tip", ""), aktif=not str(kayit.get("cikis") or "").strip(),
            akademik=bool(re.search("akademik", str(kayit.get("tip") or ""), re.I))
            or not str(kayit.get("tip") or "").strip(),
            anahtar=yazar_adi_coz(f"{kayit['soyad']}, {kayit['ad']}"),
        ))
    return kisiler


def adjunct_satiri_coz(satir: str) -> Adjunct | None:
    """"M. I. Sayyed = Abualsayed | WoS" satırını çözer."""
    ad_bolumu, _, kaynak_kismi = str(satir or "").partition("|")
    parcalar = ad_bolumu.split("=")
    anahtar = yazar_adi_coz(parcalar[0])
    if not anahtar:
        return None
    duz = sade(kaynak_kismi)
    if "scopus" in duz and "wos" in duz:
        kaynak = "hepsi"
    elif "scopus" in duz:
        kaynak = "Scopus"
    elif "wos" in duz or "web of science" in duz:
        kaynak = "WoS"
    else:
        kaynak = "hepsi"
    return Adjunct(etiket=parcalar[0].strip(), kaynak=kaynak,
                   takmalar=[p.strip() for p in parcalar[1:] if p.strip()], anahtar=anahtar)


class AdayDizini:
    """Soyad ve fonetik kökten aday personel kovaları; eşleştirmeyi hızlandırır."""

    def __init__(self, kisiler: list[Kisi]):
        self.kisiler = kisiler
        self.kovalar: dict[str, list[Kisi]] = {}
        self.bellek: dict[str, Kisi | None] = {}
        for kisi in kisiler:
            anahtar = kisi.anahtar
            if not anahtar:
                continue
            for etiket in {anahtar.soyad, anahtar.fsoyad, *anahtar.ftokenlar}:
                if etiket:
                    self.kovalar.setdefault(etiket, []).append(kisi)

    def bul(self, yazar) -> Kisi | None:
        if yazar.ham in self.bellek:
            return self.bellek[yazar.ham]
        adaylar: list[Kisi] = []
        gorulen: set[int] = set()
        for etiket in {yazar.soyad, yazar.fsoyad, *yazar.ftokenlar}:
            for kisi in self.kovalar.get(etiket, []):
                if id(kisi) not in gorulen:
                    gorulen.add(id(kisi))
                    adaylar.append(kisi)
        bulunan = next((k for k in adaylar if ad_eslesiyor_mu(yazar, k.anahtar)), None)
        if bulunan is None and len(yazar.soyad) >= 4:
            yakinlar = [k for k in self.kisiler
                        if k.anahtar and abs(len(k.anahtar.soyad) - len(yazar.soyad)) <= 1
                        and (k.anahtar.soyad[:1] == yazar.soyad[:1]
                             or k.anahtar.soyad[-1:] == yazar.soyad[-1:])]
            bulunan = next((k for k in yakinlar if ad_eslesiyor_mu(yazar, k.anahtar)), None)
        self.bellek[yazar.ham] = bulunan
        return bulunan


@dataclass
class Panel:
    """Yüklü tüm veriyi tutar ve analiz tablolarını üretir."""

    kayitlar: list[dict] = field(default_factory=list)
    personel: list[dict] = field(default_factory=list)
    adjunct: list[str] = field(default_factory=list)
    ad_esleme: dict[str, str] = field(default_factory=dict)
    quartiller: dict[int, dict[str, str]] = field(default_factory=dict)
    metrikler: list[dict] = field(default_factory=list)
    kaynak_secimi: str = "hepsi"

    # --- yardımcılar -------------------------------------------------
    def _esleme_haritasi(self) -> dict[str, str]:
        harita = {sade(k): v for k, v in self.ad_esleme.items()}
        for satir in self.adjunct:
            cozum = adjunct_satiri_coz(satir)
            if cozum:
                for takma in cozum.takmalar:
                    harita[sade(takma)] = cozum.etiket
        return harita

    def _ad_coz(self, ham: str, harita: dict[str, str], kayitlar: dict):
        if ham in kayitlar:
            return kayitlar[ham]
        yazar = yazar_adi_coz(harita.get(sade(ham), ham))
        if yazar and sade(ham) not in harita:
            for yazilan, hedef in harita.items():
                aday = yazar_adi_coz(yazilan)
                if aday and ad_eslesiyor_mu(yazar, aday):
                    yazar = yazar_adi_coz(hedef)
                    break
        kayitlar[ham] = yazar
        return yazar

    def quartile_haritasi(self, yil: int) -> dict[str, str] | None:
        """O yılın SJR listesi; yoksa en yakın önceki yıl kullanılır."""
        if not self.quartiller:
            return None
        if yil in self.quartiller:
            return self.quartiller[yil]
        yillar = sorted(self.quartiller)
        oncekiler = [y for y in yillar if y <= yil]
        return self.quartiller[oncekiler[-1] if oncekiler else yillar[0]]

    def quartile_yili(self, yil: int) -> int | None:
        if not self.quartiller:
            return None
        if yil in self.quartiller:
            return yil
        yillar = sorted(self.quartiller)
        oncekiler = [y for y in yillar if y <= yil]
        return oncekiler[-1] if oncekiler else yillar[0]

    def _kayit_quartile(self, kayit: dict) -> str:
        if bildiri_mi(kayit) or any("CPCI" in i for i in kayit.get("indeksler", [])):
            return "Bildiri"
        harita = self.quartile_haritasi(kayit.get("yil") or 0)
        if harita:
            for issn in (kayit.get("issn"), kayit.get("eissn")):
                if issn and issn in harita:
                    return harita[issn]
        return "Sınıflandırılamayan"

    # --- çekirdek ----------------------------------------------------
    def zenginlestir(self) -> tuple[list[dict], int]:
        """Kayıtları tekilleştirir, kişi eşleşmesi ve çeyreklik ekler."""
        kisiler = personel_dizini(self.personel)
        adjunctlar = [a for a in (adjunct_satiri_coz(s) for s in self.adjunct) if a]
        dizin = AdayDizini(kisiler)
        harita = self._esleme_haritasi()
        ad_bellegi: dict = {}

        birlesik: dict[str, dict] = {}
        bildiri = 0
        for ham in self.kayitlar:
            if bildiri_mi(ham):
                bildiri += 1
                continue
            kaynak = ham.get("kaynak") or "WoS"
            anahtar = (f"d:{sade(ham.get('doi'))}" if ham.get("doi")
                       else f"t:{sade(ham.get('baslik'))[:70]}|{ham.get('yil')}")
            mevcut = birlesik.get(anahtar)
            if not mevcut:
                birlesik[anahtar] = {**ham, "kaynak": kaynak, "kaynaklar": [kaynak]}
                continue
            kaynaklar = mevcut["kaynaklar"] if kaynak in mevcut["kaynaklar"] else [*mevcut["kaynaklar"], kaynak]
            taban = mevcut if mevcut["kaynak"] == "WoS" else {**ham, "kaynak": kaynak}
            yedek = ham if mevcut["kaynak"] == "WoS" else mevcut
            birlesik[anahtar] = {
                **taban, "kaynaklar": kaynaklar,
                "issn": taban.get("issn") or yedek.get("issn"),
                "eissn": taban.get("eissn") or yedek.get("eissn"),
                "doi": taban.get("doi") or yedek.get("doi"),
                "oa": taban.get("oa") or yedek.get("oa"),
                "atif": max(taban.get("atif", 0), yedek.get("atif", 0)),
                "indeksler": list(dict.fromkeys([*taban.get("indeksler", []), *yedek.get("indeksler", [])])),
            }

        secim = self.kaynak_secimi
        liste = list(birlesik.values())
        if secim == "ortak":
            liste = [k for k in liste if len(k["kaynaklar"]) > 1]
        elif secim in ("WoS", "Scopus"):
            liste = [k for k in liste if secim in k["kaynaklar"]]

        zengin = []
        for kayit in liste:
            eslesen, kurum_adlari, adjunct_var = [], [], False
            for ham_ad in kayit.get("kurum_yazarlari", []):
                yazar = self._ad_coz(ham_ad, harita, ad_bellegi)
                if not yazar or not yazar.soyad:
                    continue
                adjunct = next((a for a in adjunctlar if ad_eslesiyor_mu(yazar, a.anahtar)), None)
                if adjunct:
                    kaynaklar = kayit.get("kaynaklar") or [kayit.get("kaynak", "WoS")]
                    if adjunct.kaynak == "hepsi" or adjunct.kaynak in kaynaklar:
                        adjunct_var = True
                        kurum_adlari.append(yazar.ham)
                    continue
                kisi = dizin.bul(yazar)
                if kisi:
                    eslesen.append(kisi)
                    kurum_adlari.append(yazar.ham)
            zengin.append({
                **kayit, "eslesen": eslesen, "adjunct_var": adjunct_var,
                "q": self._kayit_quartile(kayit),
                "kurum_yazarlari": kurum_adlari if kayit.get("adres_yok") else kayit.get("kurum_yazarlari", []),
                "oa_var": bool(str(kayit.get("oa") or "").strip()),
            })

        # ISSN'i olmayan kayıtlar için dergi adından çeyreklik
        dergi_q = {sade(k["dergi"]): k["q"] for k in zengin if k["q"] in Q_SIRASI[:4] and k.get("dergi")}
        for kayit in zengin:
            if kayit["q"] == "Sınıflandırılamayan" and dergi_q.get(sade(kayit.get("dergi"))):
                kayit["q"] = dergi_q[sade(kayit["dergi"])]
                kayit["q_dergiden"] = True
        return zengin, bildiri

    def suzulmus(self, senaryo: str = "A", yil: str = "tumu") -> list[dict]:
        zengin, _ = self.zenginlestir()
        secili = [k for k in zengin
                  if (yil == "tumu" or str(k.get("yil")) == str(yil))
                  and not (senaryo == "B" and k.get("adjunct_var"))]
        return secili

    def personel_sayisi(self, senaryo: str = "A") -> int:
        aktif = [k for k in personel_dizini(self.personel) if k.aktif and k.akademik]
        return len(aktif) + (len(self.adjunct) if senaryo == "A" else 0)

    # --- tablolar ----------------------------------------------------
    def ozet(self, yil: str = "tumu") -> pd.DataFrame:
        a, b = self.suzulmus("A", yil), self.suzulmus("B", yil)

        def sayim(liste, senaryo):
            personel = self.personel_sayisi(senaryo)
            return {
                "yayin": len(liste),
                "personel": personel,
                "oa": sum(1 for k in liste if k["oa_var"]),
                "eslesen": sum(1 for k in liste if k["eslesen"]),
                "kisi_basi": len(liste) / personel if personel else 0,
            }

        A, B = sayim(a, "A"), sayim(b, "B")
        satirlar = [
            ("Yayın sayısı", A["yayin"], B["yayin"]),
            ("Akademik personel", A["personel"], B["personel"]),
            ("Yayın / kişi", round(A["kisi_basi"], 2), round(B["kisi_basi"], 2)),
            ("Açık erişimli yayın", A["oa"], B["oa"]),
            ("Personel listesiyle eşleşen yayın", A["eslesen"], B["eslesen"]),
        ]
        for ad, _ in INDEKS_ADLARI:
            sa = sum(1 for k in a if ad in k["indeksler"])
            sb = sum(1 for k in b if ad in k["indeksler"])
            if sa or sb:
                satirlar.append((ad, sa, sb))
        return pd.DataFrame(satirlar, columns=["Gösterge", "A: adjunct dahil", "B: hariç"])

    def yil_bazli(self) -> pd.DataFrame:
        zengin, _ = self.zenginlestir()
        satirlar = []
        for yil in sorted({k["yil"] for k in zengin if k["yil"]}):
            a = [k for k in zengin if k["yil"] == yil]
            b = [k for k in a if not k["adjunct_var"]]
            oa = sum(1 for k in a if k["oa_var"])
            satirlar.append({
                "Yıl": yil, "A": len(a), "B": len(b), "Adjunct": len(a) - len(b),
                "Adjunct %": round(100 * (len(a) - len(b)) / len(a), 1) if a else 0,
                "Açık erişim (A)": oa,
                "OA % (A)": round(100 * oa / len(a), 1) if a else 0,
            })
        return pd.DataFrame(satirlar)

    def quartile(self, yil: str = "tumu") -> tuple[pd.DataFrame, str]:
        a, b = self.suzulmus("A", yil), self.suzulmus("B", yil)
        satirlar = []
        for q in Q_SIRASI:
            sa = sum(1 for k in a if k["q"] == q)
            sb = sum(1 for k in b if k["q"] == q)
            satirlar.append({
                "Çeyreklik": q, "A: dahil": sa,
                "A payı": f"%{100 * sa / len(a):.1f}".replace(".", ",") if a else "·",
                "B: hariç": sb,
                "B payı": f"%{100 * sb / len(b):.1f}".replace(".", ",") if b else "·",
            })
        siniflanan_a = sum(1 for k in a if k["q"] in Q_SIRASI[:4])
        siniflanan_b = sum(1 for k in b if k["q"] in Q_SIRASI[:4])
        q1a = sum(1 for k in a if k["q"] == "Q1")
        q1b = sum(1 for k in b if k["q"] == "Q1")
        eslemeler = ", ".join(f"{y} → {self.quartile_yili(y)}"
                              for y in sorted({k["yil"] for k in a if k["yil"]}))
        not_metni = (
            f"Sınıflandırılabilen yayınlarda Q1 payı — A: %{100 * q1a / siniflanan_a:.1f}"
            f", B: %{100 * q1b / siniflanan_b:.1f}. " if siniflanan_a and siniflanan_b else ""
        ).replace(".", ",") + (f"Yayın yılı → liste yılı: {eslemeler}." if eslemeler else "")
        return pd.DataFrame(satirlar), not_metni

    def indeks(self, yil: str = "tumu") -> pd.DataFrame:
        a, b = self.suzulmus("A", yil), self.suzulmus("B", yil)
        satirlar = []
        for ad, _ in INDEKS_ADLARI:
            sa = sum(1 for k in a if ad in k["indeksler"])
            sb = sum(1 for k in b if ad in k["indeksler"])
            if sa or sb:
                satirlar.append({"İndeks": ad, "Açılımı": INDEKS_ACIKLAMALARI.get(ad, ""),
                                 "A": sa, "B": sb})
        return pd.DataFrame(satirlar)

    def acik_erisim(self) -> pd.DataFrame:
        zengin, _ = self.zenginlestir()
        satirlar = []
        for yil in sorted({k["yil"] for k in zengin if k["yil"]}):
            a = [k for k in zengin if k["yil"] == yil]
            b = [k for k in a if not k["adjunct_var"]]
            oa_a = sum(1 for k in a if k["oa_var"])
            oa_b = sum(1 for k in b if k["oa_var"])
            satirlar.append({
                "Yıl": yil, "A: yayın": len(a), "A: açık erişim": oa_a,
                "A: oran": f"%{100 * oa_a / len(a):.1f}".replace(".", ",") if a else "·",
                "B: yayın": len(b), "B: açık erişim": oa_b,
                "B: oran": f"%{100 * oa_b / len(b):.1f}".replace(".", ",") if b else "·",
            })
        return pd.DataFrame(satirlar)

    def fakulte(self, senaryo: str = "A", yil: str = "tumu") -> tuple[pd.DataFrame, str]:
        kisiler = [k for k in personel_dizini(self.personel) if k.aktif and k.akademik]
        kayitlar = self.suzulmus(senaryo, yil)
        adjunct_birim = next((f.fakulte for f in kisiler if re.search("muhendis", sade(f.fakulte))),
                             "Mühendislik Fakültesi")
        adjunct_sayisi = len(self.adjunct) if senaryo == "A" else 0
        satirlar = []
        for fakulte in sorted({k.fakulte for k in kisiler} | {adjunct_birim}):
            adjunctlu = fakulte == adjunct_birim
            personel = sum(1 for k in kisiler if k.fakulte == fakulte) + (adjunct_sayisi if adjunctlu else 0)
            yayinlar = [k for k in kayitlar
                        if any(e.fakulte == fakulte for e in k["eslesen"])
                        or (adjunctlu and senaryo == "A" and k["adjunct_var"])]
            oa = sum(1 for k in yayinlar if k["oa_var"])
            satirlar.append({
                "Fakülte / birim": fakulte, "Personel": personel, "Yayın": len(yayinlar),
                "Yayın/kişi": round(len(yayinlar) / personel, 2) if personel else 0,
                "Açık erişim": oa,
            })
        cerceve = pd.DataFrame(satirlar).sort_values("Yayın/kişi", ascending=False, ignore_index=True)
        eslesmeyen = sum(1 for k in kayitlar if not k["eslesen"] and not (senaryo == "A" and k["adjunct_var"]))
        not_metni = ("Ortak yazarlık nedeniyle bir yayın birden fazla fakülteye sayılabilir. "
                     f"A senaryosunda {len(self.adjunct)} adjunct ve yayınları {adjunct_birim} satırına eklenir. "
                     f"{eslesmeyen} yayın hiçbir personel kaydıyla eşleşmedi.")
        return cerceve, not_metni

    def metrik_dizini(self) -> dict[str, dict]:
        """OpenAlex profillerini kişilere bağlar; atıflar toplanır, h'nin en büyüğü alınır."""
        kisiler = personel_dizini(self.personel)
        adjunctlar = [a for a in (adjunct_satiri_coz(s) for s in self.adjunct) if a]
        dizin = AdayDizini(kisiler)
        harita = self._esleme_haritasi()
        ad_bellegi: dict = {}
        sonuc: dict[str, dict] = {}
        for kayit in self.metrikler:
            yazar = self._ad_coz(kayit["ad"], harita, ad_bellegi)
            if not yazar or not yazar.soyad:
                continue
            adjunct = next((a for a in adjunctlar if ad_eslesiyor_mu(yazar, a.anahtar)), None)
            if adjunct:
                anahtar = f"a:{sade(adjunct.etiket)}"
            else:
                kisi = dizin.bul(yazar)
                if not kisi:
                    continue
                anahtar = f"p:{sade(kisi.ad)} {sade(kisi.soyad)}"
            mevcut = sonuc.setdefault(anahtar, {"atif": 0, "h": 0, "profil": 0})
            mevcut["atif"] += kayit["atif"]
            mevcut["h"] = max(mevcut["h"], kayit["h"])
            mevcut["profil"] += 1
        return sonuc

    def kisi_bazli(self, senaryo: str = "A", yil: str = "tumu") -> tuple[pd.DataFrame, str]:
        kisiler = personel_dizini(self.personel)
        adjunctlar = [a for a in (adjunct_satiri_coz(s) for s in self.adjunct) if a]
        dizin = AdayDizini(kisiler)
        harita = self._esleme_haritasi()
        ad_bellegi: dict = {}
        kayitlar = self.suzulmus(senaryo, yil)
        yillar = sorted({k["yil"] for k in kayitlar if k["yil"]})
        metrikler = self.metrik_dizini() if self.metrikler else {}
        gruplar: dict[str, dict] = {}

        for kayit in kayitlar:
            gorulen = set()
            for ham_ad in kayit.get("kurum_yazarlari", []):
                yazar = self._ad_coz(ham_ad, harita, ad_bellegi)
                if not yazar or not yazar.soyad:
                    continue
                adjunct = next((a for a in adjunctlar if ad_eslesiyor_mu(yazar, a.anahtar)), None)
                kisi = None if adjunct else dizin.bul(yazar)
                if adjunct:
                    anahtar = f"a:{sade(adjunct.etiket)}"
                    bilgi = {"Kişi": adjunct.etiket, "Durum": "Adjunct",
                             "Unvan": "—" if adjunct.kaynak == "hepsi" else f"{adjunct.kaynak} sözleşmesi",
                             "Fakülte": "—"}
                elif kisi:
                    anahtar = f"p:{sade(kisi.ad)} {sade(kisi.soyad)}"
                    bilgi = {"Kişi": kisi.tam_ad,
                             "Durum": "Personel" if kisi.aktif else "Ayrılmış personel",
                             "Unvan": kisi.unvan, "Fakülte": kisi.fakulte}
                else:
                    anahtar = f"x:{yazar.soyad} {' '.join(yazar.adlar)}"
                    bilgi = {"Kişi": yazar.ham, "Durum": "Listede yok", "Unvan": "—", "Fakülte": "—"}
                grup = gruplar.setdefault(anahtar, {**bilgi, "Yayın": 0, "Açık erişim": 0,
                                                    "yillar": {}})
                if anahtar in gorulen:
                    continue
                gorulen.add(anahtar)
                grup["Yayın"] += 1
                grup["Açık erişim"] += 1 if kayit["oa_var"] else 0
                grup["yillar"][kayit["yil"]] = grup["yillar"].get(kayit["yil"], 0) + 1

        satirlar = []
        for anahtar, grup in gruplar.items():
            satir = {k: v for k, v in grup.items() if k != "yillar"}
            for y in yillar:
                satir[str(y)] = grup["yillar"].get(y, 0)
            if metrikler:
                metrik = metrikler.get(anahtar)
                satir["Atıf (OpenAlex)"] = metrik["atif"] if metrik else None
                satir["h (OpenAlex)"] = metrik["h"] if metrik else None
            satirlar.append(satir)

        sutunlar = ["Kişi", "Durum", "Unvan", "Fakülte", *[str(y) for y in yillar],
                    "Yayın", "Açık erişim"]
        if metrikler:
            sutunlar += ["Atıf (OpenAlex)", "h (OpenAlex)"]
        cerceve = (pd.DataFrame(satirlar)[sutunlar]
                   .sort_values("Yayın", ascending=False, ignore_index=True)) if satirlar \
            else pd.DataFrame(columns=sutunlar)
        eksik = [s for s in satirlar if s["Durum"] == "Listede yok"]
        aktif = [k for k in kisiler if k.aktif and k.akademik]
        not_metni = (f"{len(satirlar)} farklı kurum adresli yazar: "
                     f"{sum(1 for s in satirlar if 'Personel' in s['Durum'])} personel listesinde, "
                     f"{sum(1 for s in satirlar if s['Durum'] == 'Adjunct')} adjunct, "
                     f"{len(eksik)} listede yok. Aktif akademik personel {len(aktif)} kişi. "
                     "Bir yayın, yayındaki her kurum yazarı için ayrı sayılır.")
        return cerceve, not_metni

    def dergi(self, senaryo: str = "A", yil: str = "tumu") -> pd.DataFrame:
        kayitlar = self.suzulmus(senaryo, yil)
        gruplar: dict[str, list[dict]] = {}
        for kayit in kayitlar:
            gruplar.setdefault(kayit.get("dergi") or "(boş)", []).append(kayit)
        satirlar = [{
            "Dergi": ad, "Yayın": len(grup),
            "Q1": sum(1 for k in grup if k["q"] == "Q1"),
            "Açık erişim": sum(1 for k in grup if k["oa_var"]),
        } for ad, grup in gruplar.items()]
        return pd.DataFrame(satirlar).sort_values("Yayın", ascending=False, ignore_index=True)
