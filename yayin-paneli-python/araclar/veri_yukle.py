"""Komut satırından toplu veri yükleme:

    python araclar/veri_yukle.py --wos savedrecs*.xls --scopus scopus.csv \
        --personel akademik.xlsx --jcr "JCR 2025.csv" --scopus-kaynak citescore_2025.csv \
        --wos-yazar researchers.csv --scopus-yazar authors.csv --aylik "Agustos 2026.xlsx"

Senkronu elle tetiklemek için:  python araclar/veri_yukle.py --senk
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yayin_paneli.aylik import ay_ayristir, donem_adi  # noqa: E402
from yayin_paneli.ayristirma import (jcr_ayristir, personel_ayristir,  # noqa: E402
                                     satirlari_oku, scopus_ayristir, scopus_kaynak_ayristir,
                                     wos_ayristir, yazar_metrik_ayristir)
from yayin_paneli.eslesme import kuyrugu_tazele  # noqa: E402
from yayin_paneli.depo import Depo  # noqa: E402


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Panel veritabanını dosyalardan doldurur.")
    for ad in ("wos", "scopus", "jcr", "scopus-kaynak", "wos-yazar", "scopus-yazar", "aylik"):
        ayristirici.add_argument(f"--{ad}", nargs="*", default=[])
    ayristirici.add_argument("--personel")
    ayristirici.add_argument("--adjunct", help="Her satırda bir ad bulunan metin dosyası")
    ayristirici.add_argument("--veritabani", default=None)
    ayristirici.add_argument("--senk", action="store_true",
                             help="WoS ve Scopus senkronunu hemen çalıştır")
    ayristirici.add_argument("--kuyruk", action="store_true",
                             help="Onay kuyruğunu yeniden hesapla")
    secenekler = ayristirici.parse_args()
    depo = Depo(secenekler.veritabani) if secenekler.veritabani else Depo()

    for yol in secenekler.wos:
        sonuc = wos_ayristir(satirlari_oku(yol), Path(yol).name)
        toplam = depo.kayitlari_ekle(sonuc["kayitlar"], "WoS")
        print(f"WoS {Path(yol).name}: {len(sonuc['kayitlar'])} kayıt (toplam {toplam})")

    for yol in secenekler.scopus:
        sonuc = scopus_ayristir(satirlari_oku(yol), Path(yol).name)
        toplam = depo.kayitlari_ekle(sonuc["kayitlar"], "Scopus")
        print(f"Scopus {Path(yol).name}: {len(sonuc['kayitlar'])} kayıt (toplam {toplam})")

    if secenekler.personel:
        kisiler = personel_ayristir(satirlari_oku(secenekler.personel))
        depo.yaz("personel", kisiler)
        print(f"Personel: {len(kisiler)} satır")

    def _yil(yol: str) -> int | None:
        eslesme = re.search(r"(20\d{2})", Path(yol).name)
        return int(eslesme.group(1)) if eslesme else None

    for yol in secenekler.jcr:
        satirlar = jcr_ayristir(satirlari_oku(yol), _yil(yol))
        depo.dergi_metrik_ekle(satirlar)
        print(f"JCR {Path(yol).name}: {len(satirlar)} dergi satırı (WoS)")

    for yol in getattr(secenekler, "scopus_kaynak"):
        satirlar = scopus_kaynak_ayristir(satirlari_oku(yol), _yil(yol))
        depo.dergi_metrik_ekle(satirlar)
        print(f"Scopus Sources {Path(yol).name}: {len(satirlar)} dergi satırı")

    for kaynak, alan in (("WoS", "wos_yazar"), ("Scopus", "scopus_yazar")):
        for yol in getattr(secenekler, alan):
            satirlar = yazar_metrik_ayristir(satirlari_oku(yol), kaynak)
            depo.kisi_metrik_ekle(satirlar)
            print(f"{kaynak} yazar metrikleri {Path(yol).name}: {len(satirlar)} kişi")

    for yol in secenekler.aylik:
        sonuc = ay_ayristir(satirlari_oku(yol), Path(yol).name)
        depo.ay_ekle(sonuc["donem"], sonuc["kayitlar"])
        print(f"{donem_adi(sonuc['donem'])}: {len(sonuc['kayitlar'])} kayıt")

    if secenekler.adjunct:
        adlar = [s.strip() for s in Path(secenekler.adjunct).read_text(encoding="utf-8").splitlines()
                 if s.strip()]
        depo.yaz("adjunct", adlar)
        print(f"Adjunct listesi: {len(adlar)} ad")

    if secenekler.senk:
        from yayin_paneli.toplayici import senkronize
        for sonuc in senkronize(depo):
            print(f"Senkron {sonuc['kaynak']}: {sonuc['durum']} "
                  f"{sonuc.get('mesaj') or sonuc.get('yeni', 0)}")

    if secenekler.kuyruk or secenekler.wos or secenekler.scopus:
        ozet = kuyrugu_tazele(depo)
        print(f"Eşleşme: {ozet['kesin']} kesin, {ozet['bekleyen']} onay bekliyor, "
              f"{ozet['eslesmeyen']} aday bulunamadı")


if __name__ == "__main__":
    main()
