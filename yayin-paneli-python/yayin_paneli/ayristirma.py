"""WoS ve Scopus dosyalarını okuma: kayıtlar, dergi çeyreklikleri, yazar metrikleri."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

from .metin import doviz_coz, sade, sayiya_cevir, temiz_ad

KURUM_KALIBI = re.compile(r"dogus|doğuş", re.I)


def satirlari_oku(kaynak, ad: str | None = None) -> list[list]:
    """Excel ya da CSV dosyasını başlıksız satır listesine çevirir."""
    ad = ad or getattr(kaynak, "name", "") or str(kaynak)
    if str(ad).lower().endswith(".csv"):
        metin = kaynak.read() if hasattr(kaynak, "read") else Path(kaynak).read_bytes()
        if isinstance(metin, bytes):
            metin = metin.decode("utf-8-sig", errors="replace")
        ayrac = ";" if metin.splitlines()[0].count(";") > metin.splitlines()[0].count(",") else ","
        return [list(satir) for satir in csv.reader(io.StringIO(metin), delimiter=ayrac)]
    cerceve = pd.read_excel(kaynak, header=None, dtype=object)
    return cerceve.where(pd.notna(cerceve), None).values.tolist()


def _harf_sade(deger) -> str:
    return sade(deger)


def _sutun_haritasi(basliklar: list, sutunlar: dict[str, list[str]]) -> dict[str, int]:
    harita: dict[str, int] = {}
    duzler = [_harf_sade(b) for b in basliklar]
    for alan, adaylar in sutunlar.items():
        for i, duz in enumerate(duzler):
            if duz and any(duz == _harf_sade(a) for a in adaylar):
                harita.setdefault(alan, i)
                break
    for alan, adaylar in sutunlar.items():
        if alan in harita:
            continue
        for i, duz in enumerate(duzler):
            if duz and any(_harf_sade(a) in duz for a in adaylar):
                harita.setdefault(alan, i)
                break
    return harita


WOS_SUTUNLARI = {
    "yazarlar": ["authors"], "yazar_tam": ["author full names"], "baslik": ["article title", "title"],
    "dergi": ["source title"], "belge_turu": ["document type"], "adresler": ["addresses"],
    "issn": ["issn"], "eissn": ["eissn"], "doi": ["doi"], "yil": ["publication year"],
    "erken_tarih": ["early access date"], "indeks": ["web of science index"],
    "kategori": ["wos categories"], "alan": ["research areas"],
    "oa": ["open access designations"], "atif": ["times cited, all databases", "times cited, wos core"],
    "ut": ["ut (unique wos id)"],
}

INDEKS_ADLARI = [
    ("SCI-EXPANDED", re.compile(r"science citation index expanded|sci-expanded", re.I)),
    ("SSCI", re.compile(r"social scien\w* citation index|ssci", re.I)),
    ("A&HCI", re.compile(r"arts\s*&?\s*humanities|a&hci", re.I)),
    ("ESCI", re.compile(r"emerging sources|esci", re.I)),
    ("CPCI-S", re.compile(r"conference proceedings citation index\s*-?\s*scien|cpci-s", re.I)),
    ("CPCI-SSH", re.compile(r"conference proceedings citation index\s*-?\s*social|cpci-ssh", re.I)),
    ("BKCI", re.compile(r"book citation index|bkci", re.I)),
    ("Scopus", re.compile(r"^scopus$", re.I)),
]

INDEKS_ACIKLAMALARI = {
    "SCI-EXPANDED": "Science Citation Index Expanded — fen ve mühendislik dergileri",
    "SSCI": "Social Sciences Citation Index — sosyal bilimler dergileri",
    "A&HCI": "Arts & Humanities Citation Index — sanat ve beşerî bilimler dergileri",
    "ESCI": "Emerging Sources Citation Index — yükselen dergiler",
    "CPCI-S": "Conference Proceedings Citation Index – Science — fen bilimleri bildirileri",
    "CPCI-SSH": "Conference Proceedings Citation Index – SSH — sosyal bilimler bildirileri",
    "BKCI": "Book Citation Index — kitap ve kitap bölümleri",
    "Scopus": "Scopus veritabanı kaydı",
}


def indeksleri_coz(metin: str) -> list[str]:
    return [ad for ad, kalip in INDEKS_ADLARI if kalip.search(str(metin or ""))]


def issn_sade(deger) -> str:
    """ISSN'i yalnızca rakam ve X'e indirger (metrik tablolarıyla aynı biçim)."""
    return re.sub(r"[^0-9X]", "", str(deger or "").upper())


def kurum_yazarlari(adres_metni, kurum_kalibi=KURUM_KALIBI) -> tuple[list[str], bool]:
    """Addresses alanından kurum adresine bağlı yazarları çıkarır."""
    metin = str(adres_metni or "")
    if not metin.strip():
        return [], False
    yazarlar: list[str] = []
    kurum_var = False
    for parca in re.findall(r"\[([^\]]*)\]([^\[]*)", metin):
        adlar, adres = parca
        if kurum_kalibi.search(adres):
            kurum_var = True
            yazarlar.extend(temiz_ad(a) for a in adlar.split(";") if temiz_ad(a))
    if not yazarlar and kurum_kalibi.search(metin):
        kurum_var = True
    return list(dict.fromkeys(yazarlar)), kurum_var


def wos_ayristir(satirlar: list[list], dosya_adi: str = "") -> dict:
    """WoS "Full Record" dışa aktarımını kayıtlara çevirir."""
    baslik_satiri = 0
    for i, satir in enumerate(satirlar[:10]):
        duz = [_harf_sade(h) for h in (satir or [])]
        if "article title" in duz or "authors" in duz or "source title" in duz:
            baslik_satiri = i
            break
    basliklar = satirlar[baslik_satiri] if satirlar else []
    harita = _sutun_haritasi(basliklar, WOS_SUTUNLARI)
    if "baslik" not in harita and "dergi" not in harita:
        raise ValueError('WoS sütunları tanınamadı; dosyanın "Full Record" dışa aktarımı olduğundan emin olun.')

    def al(satir, alan):
        i = harita.get(alan)
        if i is None or i >= len(satir) or satir[i] is None:
            return ""
        return str(satir[i]).strip()

    kayitlar, uyarilar = [], []
    for satir in satirlar[baslik_satiri + 1:]:
        if not satir or not any(str(h).strip() for h in satir if h is not None):
            continue
        baslik, dergi = al(satir, "baslik"), al(satir, "dergi")
        if not baslik and not dergi:
            continue
        erken = re.search(r"(20\d{2})", al(satir, "erken_tarih"))
        yayin = re.search(r"(20\d{2})", al(satir, "yil"))
        belge = al(satir, "belge_turu")
        adres_yazarlari, kurum_var = kurum_yazarlari(al(satir, "adresler"))
        kayitlar.append({
            "id": al(satir, "ut") or f"{sade(baslik)[:40]}|{al(satir, 'doi')}",
            "baslik": baslik, "dergi": dergi,
            "issn": issn_sade(al(satir, "issn")), "eissn": issn_sade(al(satir, "eissn")),
            "doi": al(satir, "doi"),
            "yil": int(erken.group(1)) if erken else (int(yayin.group(1)) if yayin else 0),
            "basim_yili": int(yayin.group(1)) if yayin else 0,
            "belge_turu": belge.split(";")[0].strip(), "belge_turu_ham": belge,
            "indeksler": indeksleri_coz(al(satir, "indeks")),
            "oa": al(satir, "oa"), "kategoriler": al(satir, "kategori"), "alanlar": al(satir, "alan"),
            "atif": int(sayiya_cevir(al(satir, "atif")) or 0),
            "kurum_yazarlari": adres_yazarlari, "kurum_var": kurum_var, "adres_yok": False,
            "kaynak": "WoS", "tum_yazarlar": al(satir, "yazar_tam") or al(satir, "yazarlar"),
        })
    if not kayitlar:
        uyarilar.append("Dosyada kayıt bulunamadı.")
    adressiz = sum(1 for k in kayitlar if not k["kurum_var"])
    if adressiz:
        uyarilar.append(f"{adressiz} kayıtta kurum adresi bulunamadı; bunlar kişi eşleştirmesine girmez.")
    return {"kayitlar": kayitlar, "uyarilar": uyarilar, "dosya": dosya_adi}


SCOPUS_SUTUNLARI = {
    "yazarlar": ["authors"], "yazar_tam": ["author full names"], "baslik": ["title"],
    "dergi": ["source title"], "yil": ["year"], "atif": ["cited by"], "doi": ["doi"],
    "belge_turu": ["document type"], "oa": ["open access"], "ut": ["eid"],
    "issn": ["issn"], "eissn": ["eissn", "e-issn"],
    "adresler": ["affiliations"], "yazar_adresleri": ["authors with affiliations"],
}


def _scopus_yazarlari(metin: str) -> list[str]:
    return [temiz_ad(re.sub(r"\(\d[\d\s]*\)", "", p)) for p in str(metin or "").split(";")
            if temiz_ad(re.sub(r"\(\d[\d\s]*\)", "", p))]


def _scopus_oa(metin: str) -> str:
    duz = str(metin or "").lower()
    if not duz.strip():
        return ""
    if "gold" in duz:
        return "hybrid gold" if "hybrid" in duz else "gold"
    if "green" in duz:
        return "green"
    if "bronze" in duz:
        return "bronze"
    return "open access"


def scopus_ayristir(satirlar: list[list], dosya_adi: str = "") -> dict:
    basliklar = satirlar[0] if satirlar else []
    harita = _sutun_haritasi(basliklar, SCOPUS_SUTUNLARI)
    if "baslik" not in harita or "yil" not in harita:
        raise ValueError("Scopus sütunları tanınamadı (Title / Year bulunamadı).")

    def al(satir, alan):
        i = harita.get(alan)
        if i is None or i >= len(satir) or satir[i] is None:
            return ""
        return str(satir[i]).strip()

    adres_var = "yazar_adresleri" in harita or "adresler" in harita
    kayitlar, uyarilar = [], []
    for satir in satirlar[1:]:
        if not satir or not any(str(h).strip() for h in satir if h is not None):
            continue
        baslik = al(satir, "baslik")
        if not baslik:
            continue
        adres_yazarlari, kurum_var = ([], True)
        if "yazar_adresleri" in harita:
            adres_yazarlari, kurum_var = kurum_yazarlari(al(satir, "yazar_adresleri"))
        yazarlar = adres_yazarlari or _scopus_yazarlari(al(satir, "yazar_tam") or al(satir, "yazarlar"))
        belge = al(satir, "belge_turu")
        yil = re.search(r"(20\d{2})", al(satir, "yil"))
        kayitlar.append({
            "id": al(satir, "ut") or f"scopus|{sade(baslik)[:40]}|{al(satir, 'doi')}",
            "baslik": baslik, "dergi": al(satir, "dergi"),
            "issn": issn_sade(al(satir, "issn")), "eissn": issn_sade(al(satir, "eissn")),
            "doi": al(satir, "doi"),
            "yil": int(yil.group(1)) if yil else 0, "basim_yili": int(yil.group(1)) if yil else 0,
            "belge_turu": belge.split(";")[0].strip(), "belge_turu_ham": belge,
            "indeksler": ["Scopus"], "oa": _scopus_oa(al(satir, "oa")),
            "kategoriler": "", "alanlar": "",
            "atif": int(sayiya_cevir(al(satir, "atif")) or 0),
            "kurum_yazarlari": yazarlar, "kurum_var": kurum_var, "adres_yok": not adres_var,
            "kaynak": "Scopus", "tum_yazarlar": al(satir, "yazar_tam") or al(satir, "yazarlar"),
        })
    if not adres_var:
        uyarilar.append('Dosyada adres sütunu yok: kurum yazarları personel listesiyle eşleşen '
                        'adlardan bulunur. Scopus dışa aktarımında "Bibliographical information" '
                        "alanını da seçerseniz adres ve ISSN gelir.")
    if "issn" not in harita:
        uyarilar.append("ISSN sütunu yok: bu kayıtların çeyrekliği dergi adından eşleştirilir.")
    return {"kayitlar": kayitlar, "uyarilar": uyarilar, "dosya": dosya_adi}


PERSONEL_SUTUNLARI = {
    "ad": ["adi", "ad", "first name"], "soyad": ["soyadi", "soyad", "last name"],
    "tip": ["personel tipi", "tip", "kadro"], "unvan": ["unvani", "unvan", "title"],
    "fakulte": ["fakulte", "fakültesi", "birim adi", "faculty"],
    "birim": ["bolum", "bölümü", "birim"], "cikis": ["cikis tarihi", "ayrilis"],
}


def personel_ayristir(satirlar: list[list]) -> list[dict]:
    baslik_satiri = 0
    for i, satir in enumerate(satirlar[:15]):
        duz = [_harf_sade(h) for h in (satir or [])]
        if any(d in ("adi", "ad") for d in duz) and any(d.startswith("soyad") for d in duz):
            baslik_satiri = i
            break
    harita = _sutun_haritasi(satirlar[baslik_satiri] if satirlar else [], PERSONEL_SUTUNLARI)
    if "ad" not in harita or "soyad" not in harita:
        raise ValueError("Personel listesinde ad ve soyad sütunları bulunamadı.")

    def al(satir, alan):
        i = harita.get(alan)
        if i is None or i >= len(satir) or satir[i] is None:
            return ""
        return str(satir[i]).strip()

    kisiler = []
    for satir in satirlar[baslik_satiri + 1:]:
        if not satir:
            continue
        ad, soyad = temiz_ad(al(satir, "ad")), temiz_ad(al(satir, "soyad"))
        if not ad or not soyad:
            continue
        kisiler.append({
            "ad": ad, "soyad": soyad, "tip": al(satir, "tip"), "unvan": al(satir, "unvan"),
            "fakulte": al(satir, "fakulte") or "Belirtilmemiş", "birim": al(satir, "birim"),
            "cikis": al(satir, "cikis"),
        })
    return kisiler


Q_KALIBI = re.compile(r"Q\s*([1-4])", re.I)


def q_coz(deger) -> str | None:
    """"Q1", "Q 2", "1. çeyrek" gibi değerleri Q1..Q4'e indirger."""
    metin = str(deger or "").strip()
    eslesme = Q_KALIBI.search(metin)
    if eslesme:
        return f"Q{eslesme.group(1)}"
    if re.fullmatch(r"[1-4]", metin):
        return f"Q{metin}"
    return None


JCR_SUTUNLARI = {
    "dergi": ["journal name", "journal title", "full journal title", "source title", "dergi"],
    "issn": ["issn", "print issn"],
    "eissn": ["eissn", "e-issn", "online issn"],
    "kategori": ["category", "jcr category", "wos category", "category name"],
    "q": ["jif quartile", "quartile", "jcr quartile", "category quartile"],
    "deger": ["jif", "journal impact factor", "2023 jif", "impact factor"],
    "yil": ["jcr year", "year", "jif year"],
}

SCOPUS_KAYNAK_SUTUNLARI = {
    "dergi": ["source title", "title", "journal", "dergi"],
    "issn": ["issn", "print issn"],
    "eissn": ["eissn", "e-issn", "online issn"],
    "kategori": ["asjc", "subject area", "scopus sub-subject area", "category"],
    "q": ["quartile", "citescore quartile", "sjr quartile", "highest percentile"],
    "deger": ["citescore", "sjr", "snip"],
    "yil": ["year", "citescore year"],
}


def _metrik_satirlari(satirlar: list[list], sutunlar: dict, kaynak: str,
                      varsayilan_yil: int | None = None) -> list[dict]:
    """Dergi metrik dosyasını ortak `dergi_metrik` satırlarına çevirir."""
    basliklar, veri = _baslik_bul(satirlar, sutunlar)
    harita = _sutun_haritasi(basliklar, sutunlar)
    if "q" not in harita and "deger" not in harita:
        raise ValueError("Dosyada çeyreklik (quartile) ya da metrik sütunu bulunamadı.")

    def al(satir, alan):
        i = harita.get(alan)
        return satir[i] if i is not None and i < len(satir) else None

    cikti: list[dict] = []
    for satir in veri:
        if not satir or not any(satir):
            continue
        q = q_coz(al(satir, "q"))
        yuzdelik = None
        if q is None:
            ham = str(al(satir, "q") or "")
            sayi = re.search(r"(\d{1,3})(?:[.,]\d+)?\s*%?", ham)
            if sayi and "percentile" in " ".join(str(b).lower() for b in basliklar):
                yuzdelik = float(sayi.group(1))
                q = ("Q1" if yuzdelik >= 75 else "Q2" if yuzdelik >= 50
                     else "Q3" if yuzdelik >= 25 else "Q4")
        if q is None:
            continue
        yil = sayiya_cevir(al(satir, "yil")) or varsayilan_yil or 0
        dergi = temiz_ad(al(satir, "dergi") or "")
        issnler = [issn_sade(al(satir, alan)) for alan in ("issn", "eissn")]
        deger = sayiya_cevir(al(satir, "deger")) or yuzdelik
        kategori = str(al(satir, "kategori") or "").strip()[:120]
        for issn in {i for i in issnler if len(i) >= 8} or {""}:
            cikti.append({"kaynak": kaynak, "yil": int(yil), "issn": issn, "dergi": dergi,
                          "kategori": kategori, "q": q, "deger": deger})
    if not cikti:
        raise ValueError("Dosyadan çeyreklik satırı çıkarılamadı.")
    return cikti


def _baslik_bul(satirlar: list[list], sutunlar: dict) -> tuple[list, list[list]]:
    """Başlık satırı dosyanın ilk satırı olmayabilir; ilk 15 satırda aranır."""
    for i, satir in enumerate(satirlar[:15]):
        harita = _sutun_haritasi(satir or [], sutunlar)
        if len(harita) >= 2:
            return satir, satirlar[i + 1:]
    return (satirlar[0] if satirlar else []), satirlar[1:]


def jcr_ayristir(satirlar: list[list], yil: int | None = None) -> list[dict]:
    """JCR (Journal Citation Reports) dışa aktarımından WoS çeyreklikleri."""
    return _metrik_satirlari(satirlar, JCR_SUTUNLARI, "WoS", yil)


def scopus_kaynak_ayristir(satirlar: list[list], yil: int | None = None) -> list[dict]:
    """Scopus Sources / CiteScore dışa aktarımından Scopus çeyreklikleri."""
    return _metrik_satirlari(satirlar, SCOPUS_KAYNAK_SUTUNLARI, "Scopus", yil)


YAZAR_SUTUNLARI = {
    "ad": ["author name", "name", "full name", "author", "yazar"],
    "profil_kimlik": ["author id", "scopus author id", "researcher id", "orcid", "id"],
    "h": ["h-index", "h index", "hindex"],
    "atif": ["citations", "cited by", "times cited", "total citations"],
    "yayin": ["documents", "publications", "web of science documents", "document count"],
}


def yazar_metrik_ayristir(satirlar: list[list], kaynak: str) -> list[dict]:
    """WoS Researcher / Scopus Author dışa aktarımından kişi başına h ve atıf."""
    basliklar, veri = _baslik_bul(satirlar, YAZAR_SUTUNLARI)
    harita = _sutun_haritasi(basliklar, YAZAR_SUTUNLARI)
    if "ad" not in harita or "h" not in harita:
        raise ValueError("Dosyada yazar adı ve h-index sütunları bulunamadı.")

    def al(satir, alan):
        i = harita.get(alan)
        return satir[i] if i is not None and i < len(satir) else None

    cikti = []
    for satir in veri:
        ad = temiz_ad(al(satir, "ad") or "")
        if not ad:
            continue
        cikti.append({
            "kaynak": kaynak, "ad": ad,
            "profil_kimlik": str(al(satir, "profil_kimlik") or ad).strip(),
            "h": int(sayiya_cevir(al(satir, "h")) or 0),
            "atif": int(sayiya_cevir(al(satir, "atif")) or 0),
            "yayin": int(sayiya_cevir(al(satir, "yayin")) or 0),
        })
    if not cikti:
        raise ValueError("Dosyadan yazar metriği çıkarılamadı.")
    return cikti
