"""Gercek dosya duzeninde ornek ay dosyasi uretir:

    python ornek_veri.py                 -> Temmuz_2026_Yayinlari.xlsx
    python ornek_veri.py dosya.xlsx 2026 5
"""

import random
import sys

from openpyxl import Workbook

import core

KISILER = ["Ada Yilmaz", "Bora Demir", "Cem Arslan", "Deniz Kaya"]
DERGILER = ["Materials Today Communications", "Applied Physics A", "Ceramics International",
            "Results in Optics", "Scientific Reports"]
TUTARLAR = {"Q1": 500, "Q2": 450, "Q3": 400}
BASLIKLAR = ["Nanostructured coatings for shielding", "Optical response of doped glasses",
             "Machine learning aided design", "Thermal stability of composites",
             "Charge transport in perovskites"]


def uret(dosya="Temmuz_2026_Yayinlari.xlsx", yil=2026, ay=7, tohum=3):
    random.seed(tohum)
    kitap = Workbook()
    sayfa = kitap.active
    sayfa.title = "Sayfa1"
    sayfa.append([f"{core.AY_ADLARI[ay - 1].upper()} {yil} Yayinlari"])
    sayfa.append([])
    ozet = []
    for kisi in KISILER:
        sayfa.append([kisi])
        sayfa.append(["Sıra", "Article Title", "Journal / Conference", "Authors", "DOI",
                      "Quartile", "Date", "Index Link", "Kontrol", "Payments"])
        toplam = 0
        euro_kisi = kisi == "Bora Demir"
        for sira in range(1, random.randint(2, 6)):
            quartile = random.choice(list(TUTARLAR))
            standart = TUTARLAR[quartile]
            odendi = random.random() > 0.15
            if euro_kisi:
                kontrol = f"{standart}/1.1595 (EUR/USD Paritesi 1.1595)"
                tutar = round(standart / 1.1595) if odendi else None
            else:
                kontrol = "" if odendi else "ESCI"
                tutar = standart if odendi else None
            toplam += tutar or 0
            sayfa.append([sira, f"{random.choice(BASLIKLAR)} {sira}",
                          random.choice(DERGILER), "A. Yazar, B. Yazar",
                          f"https://doi.org/10.1000/ornek.{yil}{ay:02d}{sira}",
                          quartile, f"{yil}-{ay:02d}-01 00:00:00",
                          "https://www.scopus.com/pages/publications/1", kontrol, tutar])
        sayfa.append(["", "", "", "", "", "", "", "Toplam", "", toplam])
        sayfa.append([])
        ozet.append((kisi, toplam))
    sayfa.append([])
    sayfa.append(["", "ÖZET / SUMMARY"])
    sayfa.append(["", "Adjunct", "Toplam Ödeme"])
    for kisi, toplam in ozet:
        sayfa.append(["", kisi, toplam])
    kitap.save(dosya)
    return dosya


if __name__ == "__main__":
    argumanlar = sys.argv[1:]
    dosya = argumanlar[0] if argumanlar else "Temmuz_2026_Yayinlari.xlsx"
    yil = int(argumanlar[1]) if len(argumanlar) > 1 else 2026
    ay = int(argumanlar[2]) if len(argumanlar) > 2 else 7
    print("Olusturuldu:", uret(dosya, yil, ay))
