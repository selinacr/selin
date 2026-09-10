"""Cekirdek testleri:  python test_core.py"""

import os
import tempfile

from openpyxl import Workbook

import core
import ornek_veri

BASLIK = ["Sıra", "Article Title", "Journal / Conference", "Authors", "DOI",
          "Quartile", "Date", "Index Link", "Kontrol", "Payments"]
PARITE = "500/1.1595 (EUR/USD Paraitesi 1.1595)"


def esit(bulunan, beklenen, mesaj):
    assert bulunan == beklenen, f"{mesaj}: beklenen {beklenen!r}, bulunan {bulunan!r}"


def zor_dosya(yol):
    """Gercek dosyadaki tuhafliklari tasiyan ornek: satir sonlu ad, bos odeme,
    yanlis bolum toplami, farkli tarih bicimleri, EUR paritesi, Yuan notu."""
    kitap = Workbook()
    s = kitap.active
    s.append(["AĞUSTOS 2026 Yayınları"])
    s.append([])
    s.append(["Ghodrat Mahmoudi"])
    s.append(BASLIK)
    for i in range(1, 4):
        s.append([i, f"Makale {i}", "Materials Today", "A, B", f"10.1/{i}", "Q1",
                  "July 2026", "scopus", PARITE, 431])
    s.append(["", "", "", "", "", "", "", "Toplam", "", 1293])
    s.append([])
    s.append(["\nKarem Abdelazeem"])          # basinda satir sonu
    s.append(BASLIK)
    s.append([1, "Makale A", "Ceramics", "C", "10.2/1", "Q1", "2026-08-01 00:00:00",
              "wos", "", 500])
    s.append([2, "Makale B", "Array", "D", "10.2/2", "Q3", "August", "wos", "ESCI", None])
    s.append(["", "", "", "", "", "", "", "Toplam", "", 500])
    s.append([])
    s.append(["Amir Jalili"])
    s.append(BASLIK)
    s.append([1, "Makale C", "Optics", "E", "10.3/1", "Q2", "August", "wos",
              "Çin Yuanı olarak odendi", 500])
    s.append([])
    s.append(["", "ÖZET / SUMMARY"])
    s.append(["", "Adjunct", "Toplam Ödeme"])
    s.append(["", "Ghodrat Mahmoudi", 1293])
    s.append(["", "Karem Abdelazeem", 431])   # dosyadaki hatali ozet
    s.append(["", "Amir Jalili", 500])
    kitap.save(yol)
    return yol


def test_yardimcilar():
    esit(core.sayiya_cevir("1.234,56"), 1234.56, "TR sayi")
    esit(core.sayiya_cevir("2.500"), 2500.0, "binlik ayraci")
    esit(core.sayiya_cevir(""), None, "bos sayi")
    esit(core.temiz_ad("\nKarem  Abdelazeem "), "Karem Abdelazeem", "ad temizleme")
    esit(core.donem_coz("AĞUSTOS 2026 Yayınları"), (2026, 8), "baslikta donem")
    esit(core.donem_coz("Ağustos Yayınları_Adjunct (3).xlsx"), None, "yilsiz baslik")
    esit(core.donem_coz("2026-05 raporu"), (2026, 5), "sayisal donem")
    esit(core.donem_etiketi(2026, 8), "Agustos 2026", "donem etiketi")


def test_para_birimi():
    esit(core.para_birimi_coz(PARITE)[0], "EUR", "parite notu EUR")
    esit(core.para_birimi_coz(PARITE)[1], 500.0, "USD karsiligi")
    esit(core.para_birimi_coz("Çin Yuanı talebi")[0], "CNY", "yuan notu")
    esit(core.para_birimi_coz("")[0], "USD", "notsuz USD")
    esit(core.para_birimi_coz("", {"Amir Jalili": "CNY"}, "Amir Jalili")[0], "CNY",
         "kisi kurali")


def test_ayristirma():
    klasor = tempfile.mkdtemp()
    dosya = zor_dosya(os.path.join(klasor, "agustos.xlsx"))
    donem, yayinlar, ozet, uyarilar = core.dosyayi_ayristir(dosya)
    esit(donem, (2026, 8), "donem")
    esit(len(yayinlar), 6, "kayit sayisi")
    esit(sum(y.onayli for y in yayinlar), 5, "odemeli kayit")
    esit(sorted({y.kisi for y in yayinlar}),
         ["Amir Jalili", "Ghodrat Mahmoudi", "Karem Abdelazeem"], "kisiler")
    esit([y.para_birimi for y in yayinlar if y.kisi == "Ghodrat Mahmoudi"],
         ["EUR"] * 3, "EUR tespiti")
    esit([y.para_birimi for y in yayinlar if y.kisi == "Amir Jalili"], ["CNY"], "CNY tespiti")
    esit([y.tutar for y in yayinlar if y.kisi == "Karem Abdelazeem"], [500.0, None],
         "bos odeme None kalir")
    esit(ozet["Ghodrat Mahmoudi"], 1293.0, "dosya ozeti")
    assert any("Karem" in u for u in uyarilar), f"ozet tutarsizligi uyarisi yok: {uyarilar}"
    esit(sum(y.usd_karsiligi or 0 for y in yayinlar if y.kisi == "Ghodrat Mahmoudi"),
         1500.0, "USD karsiligi")

    # Donem elle verilince baslik yok sayilir.
    donem2, _, _, _ = core.dosyayi_ayristir(dosya, donem=(2025, 5))
    esit(donem2, (2025, 5), "elle donem")


def test_veritabani():
    klasor = tempfile.mkdtemp()
    db = core.Veritabani(os.path.join(klasor, "t.db"))
    agustos = zor_dosya(os.path.join(klasor, "agustos.xlsx"))
    temmuz = ornek_veri.uret(os.path.join(klasor, "temmuz.xlsx"), 2026, 7)

    for dosya in (agustos, temmuz):
        (yil, ay), yayinlar, _, _ = core.dosyayi_ayristir(dosya)
        db.aktar(yayinlar, yil, ay, dosya)
    esit(db.donemler(), [(2026, 7), (2026, 8)], "donemler")

    # Ayni ay yeniden yuklenirse o ay silinip yeniden yazilir (mukerrer olmaz).
    (yil, ay), yayinlar, _, _ = core.dosyayi_ayristir(agustos)
    onceki = db.genel_ozet()["kayit"]
    sonuc = db.aktar(yayinlar, yil, ay, agustos)
    esit(sonuc["silinen"], 6, "eski ay silindi")
    esit(db.genel_ozet()["kayit"], onceki, "toplam kayit degismedi")
    esit(db.genel_ozet(yil=2026, ay=8)["kayit"], 6, "agustos kayitlari")

    ozet = db.genel_ozet(yil=2026, ay=8)
    esit(round(ozet["para"]["EUR"], 2), 1293.0, "agustos EUR")
    esit(round(ozet["para"]["USD"], 2), 500.0, "agustos USD")
    esit(round(ozet["para"]["CNY"], 2), 500.0, "agustos CNY")
    esit(ozet["onayli"], 5, "agustos odemeli")

    birimler, kisiler = db.kisi_ozet(yil=2026, ay=8)
    esit(sorted(birimler), ["CNY", "EUR", "USD"], "kullanilan birimler")
    kayit = {k["kisi"]: k for k in kisiler}
    esit(kayit["Ghodrat Mahmoudi"]["EUR"], 1293.0, "kisi EUR toplami")
    esit(kayit["Karem Abdelazeem"]["kayit"], 2, "kisi kayit sayisi")
    esit(kayit["Karem Abdelazeem"]["onayli"], 1, "kisi odemeli sayisi")

    # Pivot: donem sutunlari + yil toplami + genel toplam
    basliklar, satirlar, donem_sayisi = db.pivot("kisi", olcu="tutar")
    esit(donem_sayisi, 2, "pivot donem sayisi")
    esit(len(basliklar), 2 + 1 + 1 + 1, "pivot kolonlari")   # ad + 2 ay + 1 yil + toplam
    for satir in satirlar:
        esit(round(sum(satir[1:1 + donem_sayisi]), 2), round(satir[-1], 2), "pivot satir")

    _, sayim, _ = db.pivot("kisi", olcu="onayli")
    esit(sum(s[-1] for s in sayim), db.genel_ozet()["onayli"], "onayli pivot toplami")

    # Filtreler
    esit(db.genel_ozet(para_birimi="EUR", yil=2026, ay=8)["kayit"], 3, "EUR filtresi")
    esit(db.genel_ozet(sadece_onayli=True)["kayit"], db.genel_ozet()["onayli"],
         "sadece odemeli filtresi")
    esit(db.genel_ozet(arama="Ghodrat")["kayit"], 3, "arama")
    esit(len(db.kayitlar(kisi="Amir Jalili")), 1, "kayit filtresi")

    # Kisi bazli para birimi kurali gecmise de uygulanabilir.
    db.kural_kaydet("Karem Abdelazeem", "EUR")
    esit(db.kurallar()["Karem Abdelazeem"], "EUR", "kural kaydi")
    esit(db.kural_uygula("Karem Abdelazeem", "EUR"), 2, "kural gecmise uygulandi")
    esit(db.genel_ozet(yil=2026, ay=8)["para"].get("USD", 0), 0, "USD kalmadi")

    # Kirilimlar ve donem ozeti
    quartile = {k["anahtar"]: k["kayit"] for k in db.kirilim("quartile", yil=2026, ay=8)}
    esit(quartile["Q1"], 4, "Q1 sayisi")
    birimler2, aylik = db.donem_ozet()
    esit(len(aylik), 2, "aylik seri")
    esit(sum(a["kayit"] for a in aylik), db.genel_ozet()["kayit"], "aylik toplam")

    # Silme ve Excel cikti
    basliklar, satirlar, _ = db.pivot("kisi", olcu="tutar")
    cikti = core.excel_yaz(os.path.join(klasor, "rapor.xlsx"), basliklar, satirlar,
                           "Kisi x Ay", range(1, len(basliklar)), "Test")
    assert os.path.getsize(cikti) > 0, "rapor yazilamadi"
    esit(db.donem_sil(2026, 8), 6, "donem silme")
    esit(db.genel_ozet(yil=2026, ay=8)["kayit"], 0, "silindi")
    db.kapat()


if __name__ == "__main__":
    for ad, islev in sorted(globals().items()):
        if ad.startswith("test_"):
            islev()
            print("OK", ad)
    print("Tum testler gecti.")
