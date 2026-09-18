"""Ad ve sayı normalleştirme; web panelindeki kurallarla aynı davranır."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

TURKCE_KARSILIK = str.maketrans({
    "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    "â": "a", "Â": "a", "î": "i", "û": "u",
})


@lru_cache(maxsize=100_000)
def sade(deger) -> str:
    """Küçük harfe indirir, Türkçe ve yabancı aksanları kök harfe çevirir."""
    if deger is None:
        return ""
    metin = str(deger).translate(TURKCE_KARSILIK).lower()
    metin = unicodedata.normalize("NFD", metin)
    metin = "".join(h for h in metin if unicodedata.category(h) != "Mn")
    metin = metin.replace("đ", "d").replace("ø", "o").replace("ß", "ss").replace("æ", "ae")
    return re.sub(r"[^a-z0-9]+", " ", metin).strip()


def temiz_ad(deger) -> str:
    return re.sub(r"\s+", " ", str(deger or "")).strip()


def sayiya_cevir(deger):
    """"2.500,50" ve "2,500.50" gibi yazımları sayıya çevirir."""
    if deger is None or deger == "":
        return None
    if isinstance(deger, (int, float)) and not isinstance(deger, bool):
        return float(deger)
    metin = str(deger).strip()
    metin = re.sub(r"(tl|try|₺|\$|eur|€|usd|cny|¥|gbp|£)", "", metin, flags=re.I)
    metin = re.sub(r"[^\d,.\-]", "", metin)
    if not re.search(r"\d", metin):
        return None
    if "," in metin and "." in metin:
        # Son ayraç ondalık kabul edilir
        metin = metin.replace(",", "") if metin.rfind(".") > metin.rfind(",") \
            else metin.replace(".", "").replace(",", ".")
    elif "," in metin:
        metin = metin.replace(",", ".") if len(metin.split(",")[-1]) != 3 else metin.replace(",", "")
    elif metin.count(".") == 1 and len(metin.split(".")[-1]) == 3:
        metin = metin.replace(".", "")
    elif metin.count(".") > 1:
        metin = metin.replace(".", "")
    try:
        return float(metin)
    except ValueError:
        return None


DOVIZ_KALIPLARI = [
    (re.compile(r"cny|yuan|rmb|çin|cin", re.I), "CNY"),
    (re.compile(r"eur|euro|avro|€", re.I), "EUR"),
    (re.compile(r"usd|dolar|dollar|\$", re.I), "USD"),
    (re.compile(r"\b(tl|try)\b|lira|₺", re.I), "TRY"),
    (re.compile(r"gbp|sterlin|£", re.I), "GBP"),
]


def doviz_coz(deger):
    metin = str(deger or "")
    for kalip, ad in DOVIZ_KALIPLARI:
        if kalip.search(metin):
            return ad
    return None


DIGRAFLAR = [("sch", "s"), ("sh", "s"), ("ch", "c"), ("gh", "g"), ("kh", "h"),
             ("ph", "f"), ("th", "t"), ("ck", "k")]


@lru_cache(maxsize=100_000)
def fonetik(metin: str) -> str:
    """Türkçe/İngilizce yazım farklarını tek köke indirir: Shahram ≈ Şahram."""
    s = sade(metin)
    s = re.sub(r"[^a-z ]", "", s)
    if not s:
        return ""
    for eski, yeni in DIGRAFLAR:
        s = s.replace(eski, yeni)
    s = s.replace("q", "k").replace("w", "v").replace("x", "ks").replace("j", "c")
    s = s.replace("y", "i")
    s = re.sub(r"(.)\1+", r"\1", s)
    s = re.sub(r"[aeiou]{2,}", lambda e: e.group(0)[0], s)
    return s


@dataclass
class Yazar:
    """Bir yazar adının çözümlenmiş hâli."""

    ham: str
    soyad: str
    adlar: list[str] = field(default_factory=list)
    tokenlar: list[str] = field(default_factory=list)
    fsoyad: str = ""
    fadlar: list[str] = field(default_factory=list)
    ftokenlar: list[str] = field(default_factory=list)


@lru_cache(maxsize=100_000)
def yazar_adi_coz(ham: str):
    """"Soyad, Ad" ya da "Ad Soyad" yazımını çözer."""
    metin = temiz_ad(ham)
    if not metin:
        return None
    if "," in metin:
        soyad, _, ad_kismi = metin.partition(",")
        soyad = sade(soyad)
        adlar = [p for p in sade(ad_kismi).split(" ") if p]
    else:
        parcalar = [p for p in sade(metin).split(" ") if p]
        if not parcalar:
            return None
        soyad = parcalar[-1] if len(parcalar) > 1 else parcalar[0]
        adlar = parcalar[:-1] if len(parcalar) > 1 else []
    tokenlar = [p for p in " ".join([soyad, *adlar]).split(" ") if p]
    return Yazar(
        ham=metin, soyad=soyad, adlar=adlar, tokenlar=tokenlar,
        fsoyad=fonetik(soyad), fadlar=[f for f in (fonetik(a) for a in adlar) if f],
        ftokenlar=[f for f in (fonetik(t) for t in tokenlar) if f],
    )


def bir_harf_farki(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return True
    i = j = fark = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        fark += 1
        if fark > 1:
            return False
        if len(a) > len(b):
            i += 1
        elif len(a) < len(b):
            j += 1
        else:
            i += 1
            j += 1
    if i < len(a) or j < len(b):
        fark += 1
    return fark <= 1


def adlar_uyuyor(adlar_a: list[str], adlar_b: list[str], kati: bool = False) -> bool:
    """Baş harfli yazımları ve eksik ikinci adları kabul eder, farklı adları reddeder."""
    if not adlar_a or not adlar_b:
        return True
    uzun_a = [t for t in adlar_a if len(t) > 1]
    uzun_b = [t for t in adlar_b if len(t) > 1]
    if not uzun_a or not uzun_b:
        bas_a = "".join(t[0] for t in adlar_a)
        bas_b = "".join(t[0] for t in adlar_b)
        return bas_a.startswith(bas_b) or bas_b.startswith(bas_a)
    kucuk, buyuk = (uzun_a, uzun_b) if len(uzun_a) <= len(uzun_b) else (uzun_b, uzun_a)
    return all(
        any(t == d
            or (not kati and bir_harf_farki(t, d))
            or (len(t) >= 4 and d.startswith(t))
            or (len(d) >= 4 and t.startswith(d))
            for d in buyuk)
        for t in kucuk
    )


def token_uyumu(a: list[str], b: list[str]) -> bool:
    """Birleşik soyadlar: "Alan, Alev Kocak" ↔ "ALEV KOÇAK ALAN"."""
    uzun_a = list(dict.fromkeys(t for t in a if len(t) > 1))
    uzun_b = list(dict.fromkeys(t for t in b if len(t) > 1))
    if len(uzun_a) < 2 or len(uzun_b) < 2:
        return False
    kucuk, buyuk = (uzun_a, uzun_b) if len(uzun_a) <= len(uzun_b) else (uzun_b, uzun_a)
    return all(t in buyuk for t in kucuk)


def y_duzelt(metin: str) -> str:
    """WoS kayıtlarında ı harfi y olarak bozulabiliyor."""
    return metin.replace("y", "i")


def ad_eslesiyor_mu(yazar: Yazar | None, kisi: Yazar | None) -> bool:
    if not yazar or not kisi:
        return False
    if yazar.soyad == kisi.soyad and adlar_uyuyor(yazar.adlar, kisi.adlar):
        return True
    if token_uyumu(yazar.tokenlar, kisi.tokenlar):
        return True
    if y_duzelt(" ".join(sorted(yazar.tokenlar))) == y_duzelt(" ".join(sorted(kisi.tokenlar))):
        return True
    sa = y_duzelt(f"{yazar.soyad} {yazar.adlar[0] if yazar.adlar else ''}".strip())
    sb = y_duzelt(f"{kisi.soyad} {kisi.adlar[0] if kisi.adlar else ''}".strip())
    if len(sa) >= 9 and bir_harf_farki(sa, sb):
        return True
    if yazar.fsoyad and len(yazar.fsoyad) >= 3 and yazar.fsoyad == kisi.fsoyad \
            and adlar_uyuyor(yazar.fadlar, kisi.fadlar, kati=True):
        return True
    return token_uyumu(yazar.ftokenlar, kisi.ftokenlar)
