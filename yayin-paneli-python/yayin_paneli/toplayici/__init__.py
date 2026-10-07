"""Otomatik veri toplama: WoS ve Scopus.

İki yol var, `ayarlar["toplama_yolu"]` ile seçilir:
  "api"       → resmi API istemcileri (önerilen, sağlayıcı şartlarına uygun)
  "tarayici"  → kullanıcının kendi makinesindeki oturumla arayüzden dışa aktarma

Her senkron `senk_gunlugu` tablosuna yazılır; arayüz son durumu buradan okur.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..eslesme import kuyrugu_tazele
from .api import ApiHatasi, ScopusApi, WosApi

KAYNAKLAR = ("WoS", "Scopus")


def _yillar(ayarlar: dict) -> list[int]:
    ilk = int(ayarlar.get("ilk_yil") or 2022)
    simdi = datetime.now(timezone.utc).year
    return list(range(ilk, simdi + 2))


def _istemci(kaynak: str, ayarlar: dict):
    if kaynak == "WoS":
        return WosApi(kurum=ayarlar.get("wos_kurum") or ayarlar.get("kurum_sorgusu", ""))
    return ScopusApi(kurum_kimligi=ayarlar.get("scopus_kurum_kimligi", ""),
                     kurum=ayarlar.get("kurum_sorgusu", ""))


def _tarayiciyla_cek(kaynak: str, ayarlar: dict, yil: int) -> list[dict]:
    from . import scopus as scopus_mod
    from . import wos as wos_mod
    if kaynak == "WoS":
        return wos_mod.kayitlari_cek(ayarlar.get("wos_kurum") or ayarlar.get("kurum_sorgusu", ""), yil)
    return scopus_mod.kayitlari_cek(ayarlar.get("scopus_kurum_kimligi", ""),
                                    ayarlar.get("kurum_sorgusu", ""), yil)


def eksik_issnler(depo, kaynak: str) -> list[str]:
    """O kaynakta çeyrekliği henüz bilinmeyen ISSN'ler."""
    bilinen = {s["issn"] for s in depo.dergi_metrikleri()
               if s["kaynak"] == kaynak and s["issn"] and s["q"]}
    eksik: list[str] = []
    for kayit in depo.kayitlar():
        for alan in ("issn", "eissn"):
            issn = kayit.get(alan)
            if issn and issn not in bilinen and issn not in eksik:
                eksik.append(issn)
    return eksik


def yazar_kimlikleri(depo, kaynak: str) -> list[str]:
    kimlikler: list[str] = []
    for kayit in depo.kayitlar(kaynak):
        for kimlik in kayit.get("yazar_kimlikleri") or []:
            if kimlik and kimlik not in kimlikler:
                kimlikler.append(kimlik)
    return kimlikler


def kaynak_senkronu(depo, kaynak: str, azami_dergi: int = 200) -> dict:
    """Tek kaynağı tazeler: kayıtlar, dergi çeyreklikleri, yazar metrikleri."""
    ayarlar = depo.ayarlar()
    gunluk = depo.senk_basla(kaynak)
    once = len(depo.kayitlar(kaynak))
    try:
        istemci = _istemci(kaynak, ayarlar) if ayarlar.get("toplama_yolu") == "api" else None
        toplam = 0
        for yil in _yillar(ayarlar):
            kayitlar = (istemci.kayitlar(yil) if istemci
                        else _tarayiciyla_cek(kaynak, ayarlar, yil))
            if kayitlar:
                depo.kayitlari_ekle(kayitlar, kaynak, yil)
                toplam += len(kayitlar)

        dergi_sayisi = 0
        if istemci:
            issnler = eksik_issnler(depo, kaynak)[:azami_dergi]
            for yil in sorted(_yillar(ayarlar), reverse=True)[:3]:
                satirlar = istemci.dergi_metrikleri(issnler, yil)
                if satirlar:
                    depo.dergi_metrik_ekle(satirlar)
                    dergi_sayisi += len(satirlar)

            metrikler = (istemci.yazar_metrikleri(yazar_kimlikleri(depo, kaynak))
                         if kaynak == "Scopus" else
                         istemci.yazar_metrikleri(_wos_yazar_adlari(depo)))
            if metrikler:
                depo.kisi_metrik_ekle(metrikler)

        kuyruk = kuyrugu_tazele(depo)
        yeni = max(0, len(depo.kayitlar(kaynak)) - once)
        depo.senk_bitir(gunluk, "tamam", yeni,
                        f"{toplam} kayıt işlendi, {dergi_sayisi} dergi metriği, "
                        f"{kuyruk['bekleyen']} onay bekliyor.")
        return {"kaynak": kaynak, "durum": "tamam", "yeni": yeni, "toplam": toplam, **kuyruk}
    except Exception as hata:  # toplama hatası senkronu bitirmeli, paneli düşürmemeli
        depo.senk_bitir(gunluk, "hata", 0, f"{type(hata).__name__}: {hata}")
        return {"kaynak": kaynak, "durum": "hata", "mesaj": str(hata)}


def _wos_yazar_adlari(depo, azami: int = 400) -> list[str]:
    adlar: list[str] = []
    for kisi in depo.oku("personel"):
        ad = f"{kisi.get('soyad', '')}, {kisi.get('ad', '')}".strip(", ")
        if ad and ad not in adlar:
            adlar.append(ad)
    return adlar[:azami]


def senkronize(depo, kaynaklar: tuple[str, ...] = KAYNAKLAR) -> list[dict]:
    return [kaynak_senkronu(depo, kaynak) for kaynak in kaynaklar]


__all__ = ["ApiHatasi", "ScopusApi", "WosApi", "senkronize", "kaynak_senkronu",
           "eksik_issnler", "yazar_kimlikleri"]
