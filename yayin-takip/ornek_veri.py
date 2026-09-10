"""Denemek icin ornek aylik yayin Excel'i uretir:  python ornek_veri.py [dosya.xlsx]"""

import random
import sys
from datetime import date

from openpyxl import Workbook

KISILER = ["Ayse Yilmaz", "Mehmet Demir", "Selin Arslan", "Kerem Ozturk", "Zeynep Kaya"]
TURLER = ["Telif", "Yayin geliri", "Dijital platform", "Konser", "Lisans"]
KANALLAR = ["TRT 1", "Radyo X", "Spotify", "YouTube", "Netflix"]
ESERLER = ["Uzak Yol", "Gece Yarisi", "Mavi Sehir", "Yankı", "Sonbahar"]


def uret(dosya="ornek_yayin.xlsx", yillar=(2025, 2026), tohum=7):
    random.seed(tohum)
    kitap = Workbook()
    sayfa = kitap.active
    sayfa.title = "Yayinlar"
    sayfa.append(["Tarih", "Ad Soyad", "Eser Adi", "Kanal", "Odeme Turu",
                  "Yayin Sayisi", "Brut Tutar", "Kesinti", "Net Tutar"])
    for yil in yillar:
        son_ay = 12 if yil != 2026 else 9
        for ay in range(1, son_ay + 1):
            for kisi in KISILER:
                for _ in range(random.randint(1, 4)):
                    adet = random.randint(1, 60)
                    brut = round(adet * random.uniform(15, 120), 2)
                    kesinti = round(brut * random.choice([0.0, 0.1, 0.2]), 2)
                    sayfa.append([
                        date(yil, ay, random.randint(1, 28)), kisi,
                        random.choice(ESERLER), random.choice(KANALLAR),
                        random.choice(TURLER), adet, brut, kesinti, round(brut - kesinti, 2)])
    for kolon, genislik in zip("ABCDEFGHI", (12, 18, 16, 14, 18, 14, 14, 12, 14)):
        sayfa.column_dimensions[kolon].width = genislik
    kitap.save(dosya)
    return dosya


if __name__ == "__main__":
    print("Olusturuldu:", uret(sys.argv[1] if len(sys.argv) > 1 else "ornek_yayin.xlsx"))
