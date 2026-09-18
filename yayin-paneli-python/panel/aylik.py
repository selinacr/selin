"""Adjunct yayın teşviki: aylık ödeme Excel'lerini okuma ve özetleme."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pandas as pd

from .metin import doviz_coz, sade, sayiya_cevir, temiz_ad

AY_ADLARI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

AY_ANAHTAR = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6, "temmuz": 7,
    "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

KISI_ETIKETLERI = {"staff", "adjunct", "kisi", "personel", "ad soyad", "isim", "hoca",
                   "name", "ogretim uyesi"}

BASLIK_ALANLARI = {
    "sira": ["#", "no", "sira"],
    "baslik": ["makale adi", "yayin adi", "baslik", "title", "article title", "publication"],
    "dergi": ["dergi", "dergi adi", "journal", "source"],
    "yazarlar": ["yazarlar", "yazar", "authors"],
    "doi": ["doi"],
    "quartile": ["q", "quartile", "ceyreklik", "kategori"],
    "tarih": ["tarih", "yayin tarihi", "date"],
    "index_link": ["index", "link", "url"],
    "kontrol": ["kontrol", "not", "aciklama", "durum"],
    "odeme": ["odeme", "tutar", "ucret", "payment", "odenecek", "miktar"],
}


def donem_coz(metin) -> tuple[int, int] | None:
    """"AĞUSTOS 2026 Yayınları" gibi bir metinden (yıl, ay) çıkarır."""
    duz = sade(metin)
    if not duz:
        return None
    yil = re.search(r"\b(20\d{2})\b", duz)
    for anahtar, ay in AY_ANAHTAR.items():
        if yil and re.search(rf"\b{anahtar}", duz):
            return int(yil.group(1)), ay
    sayisal = re.search(r"\b(20\d{2})\s?(0[1-9]|1[0-2])\b", duz)
    if sayisal:
        return int(sayisal.group(1)), int(sayisal.group(2))
    return None


def donem_anahtari(yil: int, ay: int) -> str:
    return f"{yil}-{ay:02d}"


def donem_adi(anahtar: str) -> str:
    yil, ay = anahtar.split("-")
    return f"{AY_ADLARI[int(ay) - 1]} {yil}"


def quartile_coz(deger) -> str:
    metin = re.sub(r"\s+", "", str(deger or "")).upper()
    eslesme = re.match(r"^Q?([1-4])$", metin)
    return f"Q{eslesme.group(1)}" if eslesme else ""


def _baslik_alani(hucre) -> str | None:
    metin = str(hucre or "").strip()
    if not metin or len(metin) > 30:
        return None
    if metin == "#":
        return "sira"
    duz = sade(metin)
    for alan, adaylar in BASLIK_ALANLARI.items():
        if any(duz == sade(a) for a in adaylar):
            return alan
    for alan, adaylar in BASLIK_ALANLARI.items():
        if any(sade(a) in duz for a in adaylar):
            return alan
    return None


def _baslik_satiri_mi(metinler: list[str]) -> bool:
    ilk_dolu = next((m for m in metinler if m), "")
    if ilk_dolu and ilk_dolu.strip().isdigit():
        return False
    alanlar = {a for a in (_baslik_alani(m) for m in metinler) if a}
    return len(alanlar) >= 3


def _sutun_haritasi(metinler: list[str]) -> dict[str, int]:
    harita: dict[str, int] = {}
    for i, metin in enumerate(metinler):
        alan = _baslik_alani(metin)
        if alan and alan not in harita:
            harita[alan] = i
    return harita


def _odemeyi_bul(satir: list, harita: dict[str, int]) -> tuple[float | None, str]:
    if "odeme" in harita and harita["odeme"] < len(satir):
        ham = satir[harita["odeme"]]
        return sayiya_cevir(ham), "" if ham is None else str(ham)
    for hucre in reversed(satir):
        if hucre is None or not str(hucre).strip():
            continue
        metin = str(hucre).strip()
        if re.fullmatch(r"[\d.,\s]*\d[\d.,\s]*(usd|eur|cny|try|tl|₺|\$|€|¥)?", metin, re.I):
            return sayiya_cevir(metin), metin
        break
    return None, ""


def kimlik_uret(donem: str, kisi: str, doi: str, baslik: str) -> str:
    ham = f"{donem}|{sade(kisi)}|{sade(doi) or sade(baslik)[:60]}"
    return f"{donem}-{hashlib.blake2s(ham.encode(), digest_size=8).hexdigest()}"


def _hucre_metni(satir: list, harita: dict[str, int], alan: str) -> str:
    i = harita.get(alan)
    if i is None or i >= len(satir) or satir[i] is None:
        return ""
    return re.sub(r"\s+", " ", str(satir[i])).strip()


def ay_ayristir(satirlar: list[list], dosya_adi: str = "", secilen_donem: str | None = None) -> dict:
    """Bir ayın yayın/ödeme tablosunu kayıtlara çevirir."""
    donem = None
    if secilen_donem:
        yil, ay = secilen_donem.split("-")
        donem = (int(yil), int(ay))
    baslik_hucresi = ""
    for satir in (satirlar or [])[:6]:
        for hucre in satir or []:
            if donem_coz(hucre):
                baslik_hucresi = str(hucre)
                break
        if baslik_hucresi:
            break
    donem = donem or donem_coz(baslik_hucresi) or donem_coz(dosya_adi)
    if not donem:
        raise ValueError('Dosyanın dönemi bulunamadı; başlıkta "AĞUSTOS 2026 Yayınları" gibi '
                         "bir ifade yoksa dönemi elle seçin.")
    anahtar = donem_anahtari(*donem)

    kayitlar: list[dict] = []
    uyarilar: list[str] = []
    para_tercihleri: dict[str, str] = {}
    harita: dict[str, int] = {}
    kisi = ""
    ozet_bolumu = False

    for satir in satirlar or []:
        satir = list(satir or [])
        metinler = ["" if h is None else str(h).strip() for h in satir]
        dolu = [m for m in metinler if m]
        if not dolu:
            continue
        birlesik = sade(" ".join(dolu))

        if "ozet" in birlesik or "summary" in birlesik or (
                "ad soyad" in birlesik and ("doviz" in birlesik or "toplam" in birlesik)):
            ozet_bolumu = True
            continue
        if ozet_bolumu:
            atlanacak = {"adjunct", "toplam odeme", "toplam miktar", "doviz cinsi", "ad soyad"}
            ad = next((m for m in dolu
                       if re.search(r"[^\W\d_]", m) and sade(m) not in atlanacak and not doviz_coz(m)), None)
            if ad:
                doviz = next((doviz_coz(m) for m in dolu if doviz_coz(m)), None)
                if doviz:
                    para_tercihleri[temiz_ad(ad)] = doviz
            continue

        if _baslik_satiri_mi(metinler):
            harita = _sutun_haritasi(metinler)
            continue
        if "toplam" in birlesik and len(dolu) <= 3:
            continue
        if not re.search(r"[^\W\d_]", "".join(dolu)):
            continue

        harfli = [m for m in dolu if re.search(r"[^\W\d_]", m)]
        if len(dolu) == 1 and len(harfli) == 1 and len(dolu[0]) >= 3:
            if donem_coz(dolu[0]) or "yayin" in sade(dolu[0]) or "publication" in sade(dolu[0]):
                continue
            kisi = temiz_ad(dolu[0])
            continue
        if len(dolu) == 2 and sade(dolu[0]) in KISI_ETIKETLERI:
            kisi = temiz_ad(dolu[1])
            continue
        if not kisi or not harita:
            continue

        baslik = _hucre_metni(satir, harita, "baslik")
        doi = _hucre_metni(satir, harita, "doi")
        if not baslik and not doi:
            continue
        tutar, odeme_metni = _odemeyi_bul(satir, harita)
        kayitlar.append({
            "id": kimlik_uret(anahtar, kisi, doi, baslik), "donem": anahtar, "kisi": kisi,
            "baslik": baslik, "dergi": _hucre_metni(satir, harita, "dergi"),
            "yazarlar": _hucre_metni(satir, harita, "yazarlar"), "doi": doi,
            "quartile": quartile_coz(_hucre_metni(satir, harita, "quartile")),
            "tarih": _hucre_metni(satir, harita, "tarih"),
            "kontrol": _hucre_metni(satir, harita, "kontrol"),
            "tutar": tutar, "odeme_metni": odeme_metni,
        })

    gorulen: dict[str, int] = {}
    for kayit in kayitlar:
        adet = gorulen.get(kayit["id"], 0) + 1
        gorulen[kayit["id"]] = adet
        if adet > 1:
            kayit["id"] = f"{kayit['id']}x{adet}"

    if not kayitlar:
        uyarilar.append("Dosyada kayıt bulunamadı; sayfa seçimini kontrol edin.")
    elif not any(k["tutar"] for k in kayitlar):
        uyarilar.append("Bu dosyada tutar yok: yayınlar sayılır, ödeme sütunları boş kalır.")
    return {"donem": anahtar, "kayitlar": kayitlar, "uyarilar": uyarilar,
            "para_tercihleri": para_tercihleri, "dosya": dosya_adi}


def para_birimi_coz(kontrol: str, kisi_kurali: str | None, odeme_metni: str) -> str:
    """Para birimi: kontrol notu > ödeme hücresi > kişi kuralı > USD."""
    not_duz = sade(kontrol)
    if re.search(r"\b(cny|yuan|rmb|cin)\b", not_duz):
        return "CNY"
    if "eur" in not_duz or "parite" in not_duz:
        return "EUR"
    return doviz_coz(kontrol) or doviz_coz(odeme_metni) or kisi_kurali or "USD"


@dataclass
class AdjunctPanel:
    """Aylık kayıtlar üzerinden kişi ve ödeme tabloları."""

    kayitlar: list[dict] = field(default_factory=list)
    kurallar: dict[str, str] = field(default_factory=dict)

    def zengin(self) -> list[dict]:
        cikti = []
        for kayit in self.kayitlar:
            birim = kayit.get("para_birimi_elle") or para_birimi_coz(
                kayit.get("kontrol", ""), self.kurallar.get(temiz_ad(kayit.get("kisi", ""))),
                kayit.get("odeme_metni", ""))
            cikti.append({**kayit, "para_birimi": birim,
                          "yil": int(str(kayit["donem"])[:4]),
                          "q_goster": kayit.get("quartile") or "—"})
        return cikti

    def donemler(self) -> list[str]:
        return sorted({k["donem"] for k in self.kayitlar})

    def kisi_ay(self, olcu: str = "tutar") -> pd.DataFrame:
        """Kişi × ay tablosu; tutar ölçüsünde her kişi kendi para biriminde ayrı satırdadır."""
        kayitlar = self.zengin()
        donemler = self.donemler()
        gruplar: dict[str, dict] = {}
        for kayit in kayitlar:
            etiket = f"{kayit['kisi']} · {kayit['para_birimi']}" if olcu == "tutar" else kayit["kisi"]
            grup = gruplar.setdefault(etiket, {"Kişi": etiket, **{donem_adi(d): 0 for d in donemler}})
            deger = (kayit["tutar"] or 0) if olcu == "tutar" else 1
            grup[donem_adi(kayit["donem"])] += deger
        satirlar = []
        for grup in gruplar.values():
            toplam = sum(v for k, v in grup.items() if k != "Kişi")
            if olcu == "tutar" and not toplam:
                continue
            satirlar.append({**grup, "Toplam": toplam})
        return pd.DataFrame(satirlar).sort_values("Toplam", ascending=False, ignore_index=True) \
            if satirlar else pd.DataFrame(columns=["Kişi", *[donem_adi(d) for d in donemler], "Toplam"])

    def kisi_ozeti(self) -> pd.DataFrame:
        kayitlar = self.zengin()
        birimler = sorted({k["para_birimi"] for k in kayitlar if k["tutar"]})
        gruplar: dict[str, list[dict]] = {}
        for kayit in kayitlar:
            gruplar.setdefault(kayit["kisi"], []).append(kayit)
        satirlar = []
        for ad, grup in gruplar.items():
            satir = {"Kişi": ad, "Yayın": len(grup)}
            for birim in birimler:
                satir[f"{birim} ödeme"] = sum(k["tutar"] or 0 for k in grup if k["para_birimi"] == birim)
            satirlar.append(satir)
        return pd.DataFrame(satirlar).sort_values("Yayın", ascending=False, ignore_index=True)

    def kisi_quartile(self) -> pd.DataFrame:
        kayitlar = self.zengin()
        sutunlar = ["Q1", "Q2", "Q3", "Q4", "—"]
        gruplar: dict[str, list[dict]] = {}
        for kayit in kayitlar:
            gruplar.setdefault(kayit["kisi"], []).append(kayit)
        satirlar = [{"Kişi": ad, **{q: sum(1 for k in grup if k["q_goster"] == q) for q in sutunlar},
                     "Toplam": len(grup)} for ad, grup in gruplar.items()]
        return pd.DataFrame(satirlar).sort_values("Toplam", ascending=False, ignore_index=True)

    def dergi(self) -> pd.DataFrame:
        kayitlar = self.zengin()
        birimler = sorted({k["para_birimi"] for k in kayitlar if k["tutar"]})
        gruplar: dict[str, list[dict]] = {}
        for kayit in kayitlar:
            gruplar.setdefault(kayit.get("dergi") or "(boş)", []).append(kayit)
        satirlar = []
        for ad, grup in gruplar.items():
            satir = {"Dergi": ad, "Yayın": len(grup), "Kişi": len({k["kisi"] for k in grup})}
            for birim in birimler:
                satir[f"{birim} ödeme"] = sum(k["tutar"] or 0 for k in grup if k["para_birimi"] == birim)
            satirlar.append(satir)
        return pd.DataFrame(satirlar).sort_values("Yayın", ascending=False, ignore_index=True)

    def kutular(self) -> dict[str, str]:
        kayitlar = self.zengin()
        kutular = {"yayın": str(len(kayitlar)), "kişi": str(len({k["kisi"] for k in kayitlar}))}
        for birim in sorted({k["para_birimi"] for k in kayitlar if k["tutar"]}):
            toplam = sum(k["tutar"] or 0 for k in kayitlar if k["para_birimi"] == birim)
            kutular[f"{birim} ödeme"] = f"{toplam:,.0f}".replace(",", ".")
        return kutular
