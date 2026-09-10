"""Cekirdek katman testleri:  python test_core.py"""

import os
import tempfile
from datetime import date

import core
import ornek_veri


def esit(bulunan, beklenen, mesaj):
    assert bulunan == beklenen, f"{mesaj}: beklenen {beklenen!r}, bulunan {bulunan!r}"


def test_sayi():
    esit(core.sayiya_cevir("1.234,56 TL"), 1234.56, "TR bicimi")
    esit(core.sayiya_cevir("1,234.56"), 1234.56, "EN bicimi")
    esit(core.sayiya_cevir("(120,50)"), -120.5, "parantezli negatif")
    esit(core.sayiya_cevir(None), 0.0, "bos")
    esit(core.sayiya_cevir("2.500"), 2500.0, "binlik ayraci")
    esit(core.sayiya_cevir(12), 12.0, "sayi")


def test_tarih():
    esit(core.tarihe_cevir("2026-03-15"), (2026, 3, "2026-03-15"), "iso")
    esit(core.tarihe_cevir("15.03.2026"), (2026, 3, "2026-03-15"), "tr tarih")
    esit(core.tarihe_cevir("Mart 2026"), (2026, 3, None), "ay adi")
    esit(core.tarihe_cevir("03.2026"), (2026, 3, None), "ay/yil")
    esit(core.tarihe_cevir(202603), (2026, 3, None), "sayisal donem")
    esit(core.tarihe_cevir(date(2026, 3, 1)), (2026, 3, "2026-03-01"), "date nesnesi")
    esit(core.tarihe_cevir("abc"), None, "cozumsuz")


def test_esleme_ve_aktarim():
    klasor = tempfile.mkdtemp()
    excel = ornek_veri.uret(os.path.join(klasor, "ornek.xlsx"))
    basliklar, satirlar = core.excel_oku(excel)
    esit(core.baslik_satiri_bul(excel), 1, "baslik satiri")
    esleme = core.otomatik_esle(basliklar)
    for alan in ("kisi", "tarih", "odeme_turu", "net", "brut", "kesinti", "kanal", "eser", "adet"):
        assert alan in esleme, f"{alan} eslenmedi ({basliklar})"
    kayitlar, hatalar = core.satirlari_donustur(basliklar, satirlar, esleme, "ornek.xlsx")
    esit(len(hatalar), 0, "hatali satir")
    esit(len(kayitlar), len(satirlar), "kayit sayisi")

    db = core.Veritabani(os.path.join(klasor, "test.db"))
    sonuc = db.aktar(kayitlar, "atla", excel, "Yayinlar")
    esit(sonuc["eklenen"], len(kayitlar), "ilk aktarim")

    # Ayni dosya tekrar aktarilirsa mukerrer kayit olusmamali.
    tekrar = db.aktar(kayitlar, "atla", excel, "Yayinlar")
    esit(tekrar["eklenen"], 0, "mukerrer eklenmemeli")
    esit(db.genel_ozet()["kayit"], len(kayitlar), "toplam kayit sabit")

    # Donem degistirme modu ilgili aylari sifirlayip yeniden yazmali.
    mart = [k for k in kayitlar if (k.yil, k.ay) == (2026, 3)]
    sonuc3 = db.aktar(mart, "donem_degistir", excel, "Yayinlar")
    esit(sonuc3["eklenen"], len(mart), "donem degistir ekleme")
    esit(db.genel_ozet(yil=2026, ay=3)["kayit"], len(mart), "donem degistir sonucu")

    # Ozetler toplamlari korumali.
    toplam_net = round(sum(k.net for k in kayitlar), 2)
    esit(round(db.genel_ozet()["net"], 2), toplam_net, "genel net")
    esit(round(sum(v["net"] for v in db.kisi_ozet()), 2), toplam_net, "kisi ozet toplami")
    esit(round(sum(v["net"] for v in db.odeme_ozet()), 2), toplam_net, "odeme ozet toplami")
    esit(round(sum(a["net"] for a in db.aylik_seri()), 2), toplam_net, "aylik seri toplami")
    esit(sorted(db.yillar(), reverse=True), db.yillar(), "yillar sirali")

    # Pivot: satir toplamlari ve yil filtresi.
    kolonlar, pivot_satirlari = db.pivot("kisi", yil=2026)
    esit(len(kolonlar), 14, "pivot kolon sayisi")
    net_2026 = round(db.genel_ozet(yil=2026)["net"], 2)
    esit(round(sum(s[-1] for s in pivot_satirlari), 2), net_2026, "pivot toplami")
    for satir in pivot_satirlari:
        esit(round(sum(satir[1:-1]), 2), round(satir[-1], 2), "pivot satir toplami")

    kolonlar2, pivot2 = db.pivot("odeme_turu")
    assert kolonlar2[0] == "Odeme turu" and len(pivot2) > 0, "odeme pivotu"

    # Kisi detayi.
    kisi = db.kisiler()[0]
    yillik, turler = db.kisi_yillik(kisi)
    esit(round(sum(y["net"] for y in yillik), 2),
         round(sum(t["net"] for t in turler), 2), "kisi detay tutarliligi")

    # Excel disa aktarim.
    cikti = core.excel_yaz(os.path.join(klasor, "rapor.xlsx"), kolonlar, pivot_satirlari,
                           "Kisi x Ay", para_kolonlari=range(1, 14), baslik_notu="Test raporu")
    assert os.path.getsize(cikti) > 0, "rapor yazilamadi"
    geri_basliklar, geri_satirlar = core.excel_oku(cikti, baslik_satiri=3)
    esit(geri_basliklar, kolonlar, "rapor basliklari")
    esit(len(geri_satirlar), len(pivot_satirlari), "rapor satir sayisi")

    # Profil kaydi.
    db.profil_kaydet("varsayilan", esleme, 1)
    esit(db.profiller()["varsayilan"][0], esleme, "profil")
    db.kapat()


def test_zorunlu_alan():
    try:
        core.satirlari_donustur(["A"], [["x"]], {"kisi": 0})
    except ValueError:
        return
    raise AssertionError("Zorunlu alan kontrolu calismadi")


if __name__ == "__main__":
    for ad, islev in sorted(globals().items()):
        if ad.startswith("test_"):
            islev()
            print("OK", ad)
    print("Tum testler gecti.")
