"""Komut satırından toplu veri yükleme:

    python araclar/veri_yukle.py --wos savedrecs*.xls --scopus scopus.csv \
        --personel akademik.xlsx --sjr scimagojr_2025.csv --metrik authors*.json \
        --aylik "Agustos 2026.xlsx"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from panel.aylik import ay_ayristir, donem_adi  # noqa: E402
from panel.ayristirma import (openalex_ayristir, personel_ayristir, satirlari_oku,  # noqa: E402
                              scopus_ayristir, sjr_ayristir, wos_ayristir)
from panel.depo import Depo  # noqa: E402


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Panel veritabanını dosyalardan doldurur.")
    for ad in ("wos", "scopus", "sjr", "metrik", "aylik"):
        ayristirici.add_argument(f"--{ad}", nargs="*", default=[])
    ayristirici.add_argument("--personel")
    ayristirici.add_argument("--adjunct", help="Her satırda bir ad bulunan metin dosyası")
    ayristirici.add_argument("--veritabani", default=None)
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

    for yol in secenekler.sjr:
        yil = re.search(r"(20\d{2})", Path(yol).name)
        if not yil:
            print(f"{yol}: dosya adında yıl yok, atlandı")
            continue
        harita = sjr_ayristir(satirlari_oku(yol))
        depo.quartil_ekle(int(yil.group(1)), harita)
        print(f"SJR {yil.group(1)}: {len(harita)} ISSN")

    for yol in secenekler.metrik:
        toplam = depo.metrik_ekle(openalex_ayristir(Path(yol).read_text(encoding="utf-8")))
        print(f"OpenAlex {Path(yol).name}: toplam {toplam} profil")

    for yol in secenekler.aylik:
        sonuc = ay_ayristir(satirlari_oku(yol), Path(yol).name)
        depo.ay_ekle(sonuc["donem"], sonuc["kayitlar"])
        print(f"{donem_adi(sonuc['donem'])}: {len(sonuc['kayitlar'])} kayıt")

    if secenekler.adjunct:
        adlar = [s.strip() for s in Path(secenekler.adjunct).read_text(encoding="utf-8").splitlines()
                 if s.strip()]
        depo.yaz("adjunct", adlar)
        print(f"Adjunct listesi: {len(adlar)} ad")


if __name__ == "__main__":
    main()
