"""WoS, Scopus, personel, SCImago ve OpenAlex dosyalarını okuma."""

from __future__ import annotations

import csv
import io
import json
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
    """ISSN'i yalnızca rakam ve X'e indirger (SJR listesiyle aynı biçim)."""
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


def sjr_ayristir(satirlar: list[list]) -> dict[str, str]:
    """SCImago CSV'sinden ISSN → çeyreklik haritası."""
    basliklar = [_harf_sade(b) for b in (satirlar[0] if satirlar else [])]
    issn_sutunu = next((i for i, b in enumerate(basliklar) if "issn" in b), None)
    q_sutunu = next((i for i, b in enumerate(basliklar) if "quartile" in b), None)
    if issn_sutunu is None or q_sutunu is None:
        raise ValueError("Çeyreklik dosyasında ISSN ve Quartile sütunları bulunamadı.")
    harita: dict[str, str] = {}
    for satir in satirlar[1:]:
        if not satir or q_sutunu >= len(satir):
            continue
        q = re.search(r"Q[1-4]", str(satir[q_sutunu] or "").upper())
        if not q:
            continue
        for parca in re.split(r"[,;\s]+", str(satir[issn_sutunu] or "")):
            issn = issn_sade(parca)
            if len(issn) >= 8:
                mevcut = harita.get(issn)
                if not mevcut or q.group(0) < mevcut:
                    harita[issn] = q.group(0)
    return harita


def openalex_ayristir(metin: str) -> list[dict]:
    """OpenAlex /authors çıktısından yazar başına atıf ve h indeksi."""
    veri = json.loads(metin)
    kayitlar = veri if isinstance(veri, list) else veri.get("results", [])
    if not kayitlar:
        raise ValueError("Dosyada yazar kaydı bulunamadı (results boş).")
    return [{
        "ad": temiz_ad(k.get("display_name", "")),
        "kimlik": str(k.get("id", "")).replace("https://openalex.org/", ""),
        "atif": int(k.get("cited_by_count") or 0),
        "yayin": int(k.get("works_count") or 0),
        "h": int((k.get("summary_stats") or {}).get("h_index") or 0),
    } for k in kayitlar if temiz_ad(k.get("display_name", ""))]
