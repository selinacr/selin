"""İsim eşleştirme: kesin eşleşmeler otomatik, şüpheliler onay kuyruğuna.

Kesin eşleşme `ad_eslesiyor_mu` ile bulunur ve doğrudan bağlanır. Soyadı tutup adı
belirsiz kalan ya da yalnızca fonetik olarak benzeyen adlar otomatik bağlanmaz; adayları
ve benzerlik puanıyla birlikte onay kuyruğuna düşer. Onaylanan karar takma ad tablosuna
yazılır ve bir daha sorulmaz.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analiz import AdayDizini, adjunct_satiri_coz, personel_dizini
from .metin import Yazar, ad_eslesiyor_mu, adlar_uyuyor, bir_harf_farki, sade, yazar_adi_coz

ESIK_SUPHELI = 0.45   # bu puanın altındaki adaylar kuyruğa bile girmez


def _benzerlik(yazar: Yazar, aday: Yazar) -> float:
    """0–1 arası kaba benzerlik: soyad, fonetik soyad ve ad uyumunun ağırlıklı toplamı."""
    if not yazar or not aday:
        return 0.0
    puan = 0.0
    if yazar.soyad == aday.soyad:
        puan += 0.55
    elif yazar.fsoyad and yazar.fsoyad == aday.fsoyad:
        puan += 0.40
    elif len(yazar.soyad) >= 4 and bir_harf_farki(yazar.soyad, aday.soyad):
        puan += 0.30
    if adlar_uyuyor(yazar.adlar, aday.adlar):
        puan += 0.30
    elif adlar_uyuyor(yazar.fadlar, aday.fadlar, kati=True):
        puan += 0.20
    elif yazar.adlar and aday.adlar and yazar.adlar[0][:1] == aday.adlar[0][:1]:
        puan += 0.10
    ortak = set(yazar.ftokenlar) & set(aday.ftokenlar)
    if ortak:
        puan += min(0.15, 0.05 * len(ortak))
    return round(min(puan, 1.0), 3)


@dataclass
class EslesmeSonucu:
    kesin: dict[str, str]          # ham ad → hedef etiket
    kuyruk: list[dict]             # onay bekleyen kayıtlar
    eslesmeyen: list[str]          # aday bile bulunamayanlar


def kuyruk_hazirla(ham_adlar: list[str], personel: list[dict], adjunct: list[str],
                   takma_adlar: dict[str, str] | None = None,
                   kaynak: str = "") -> EslesmeSonucu:
    """Kurum adresli ham yazar adlarını kesin / şüpheli / eşleşmeyen olarak ayırır."""
    takma_adlar = takma_adlar or {}
    bilinen = {sade(k): v for k, v in takma_adlar.items()}
    kisiler = personel_dizini(personel)
    adjunctlar = [a for a in (adjunct_satiri_coz(s) for s in adjunct) if a]
    dizin = AdayDizini(kisiler)

    kesin: dict[str, str] = {}
    kuyruk: list[dict] = []
    eslesmeyen: list[str] = []
    gorulen: set[str] = set()

    for ham in ham_adlar:
        duz = sade(ham)
        if not duz or duz in gorulen:
            continue
        gorulen.add(duz)
        if duz in bilinen:
            kesin[ham] = bilinen[duz]
            continue
        yazar = yazar_adi_coz(ham)
        if not yazar or not yazar.soyad:
            continue
        adjunct_eslesen = next((a for a in adjunctlar if ad_eslesiyor_mu(yazar, a.anahtar)), None)
        if adjunct_eslesen:
            kesin[ham] = adjunct_eslesen.etiket
            continue
        kisi = dizin.bul(yazar)
        if kisi:
            kesin[ham] = kisi.tam_ad
            continue

        adaylar = []
        for aday in kisiler:
            puan = _benzerlik(yazar, aday.anahtar)
            if puan >= ESIK_SUPHELI:
                adaylar.append({"hedef": aday.tam_ad, "tur": "personel",
                                "fakulte": aday.fakulte, "birim": aday.birim,
                                "unvan": aday.unvan, "puan": puan})
        for aday in adjunctlar:
            puan = _benzerlik(yazar, aday.anahtar)
            if puan >= ESIK_SUPHELI:
                adaylar.append({"hedef": aday.etiket, "tur": "adjunct",
                                "fakulte": "—", "birim": "—",
                                "unvan": f"{aday.kaynak} sözleşmesi", "puan": puan})
        adaylar.sort(key=lambda a: a["puan"], reverse=True)
        if adaylar:
            kuyruk.append({"ham": ham, "kaynak": kaynak, "adaylar": adaylar[:8],
                           "benzerlik": adaylar[0]["puan"]})
        else:
            eslesmeyen.append(ham)

    return EslesmeSonucu(kesin=kesin, kuyruk=kuyruk, eslesmeyen=eslesmeyen)


def kayitlardan_adlar(kayitlar: list[dict]) -> list[str]:
    """Tüm kayıtlardaki kurum adresli yazar adlarını tekilleştirir."""
    adlar: list[str] = []
    gorulen: set[str] = set()
    for kayit in kayitlar:
        for ham in kayit.get("kurum_yazarlari", []):
            duz = sade(ham)
            if duz and duz not in gorulen:
                gorulen.add(duz)
                adlar.append(ham)
    return adlar


def kuyrugu_tazele(depo, kaynak: str = "") -> dict:
    """Depodaki kayıtları tarar, onay kuyruğunu günceller ve özet döndürür."""
    kayitlar = depo.kayitlar(kaynak or None)
    sonuc = kuyruk_hazirla(kayitlardan_adlar(kayitlar), depo.oku("personel"),
                           depo.oku("adjunct"), depo.takma_adlar(), kaynak)
    kararlanmis = {k["ham"] for k in depo.kuyruk("onayli")} | {k["ham"] for k in depo.kuyruk("reddedildi")}
    yeniler = [k for k in sonuc.kuyruk if k["ham"] not in kararlanmis]
    bekleyen = depo.kuyruga_ekle(yeniler) if yeniler else len(depo.kuyruk())
    return {"kesin": len(sonuc.kesin), "bekleyen": bekleyen,
            "yeni_soru": len(yeniler), "eslesmeyen": len(sonuc.eslesmeyen)}


def adjunct_varyasyonlari(ham_adlar: list[str], adjunct: list[str]) -> dict[str, str]:
    """Adjunct profillerindeki tüm isim varyasyonlarını çatı etikete bağlar."""
    adjunctlar = [a for a in (adjunct_satiri_coz(s) for s in adjunct) if a]
    harita: dict[str, str] = {}
    for ham in ham_adlar:
        yazar = yazar_adi_coz(ham)
        if not yazar or not yazar.soyad:
            continue
        eslesen = next((a for a in adjunctlar if ad_eslesiyor_mu(yazar, a.anahtar)), None)
        if eslesen and sade(ham) != sade(eslesen.etiket):
            harita[ham] = eslesen.etiket
    return harita


def kuyruga_hazirla_yardimci(depo, ham_adlar: list[str], kaynak: str = "") -> EslesmeSonucu:
    """Depodaki personel, adjunct ve takma ad listeleriyle `kuyruk_hazirla` çağırır."""
    return kuyruk_hazirla(ham_adlar, depo.oku("personel"), depo.oku("adjunct"),
                          depo.takma_adlar(), kaynak)
